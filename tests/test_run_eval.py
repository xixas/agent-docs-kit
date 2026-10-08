import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills/agent-ab-eval"))
import run_eval  # noqa: E402

PROMPTS = """
prompts:
  - id: p1
    prompt: "Add a lambda"
    checks:
      - {rule: warm, any: ["warm_targets", "scheduler"]}
      - {rule: docs, any: ["RESOURCES\\\\.md"]}
"""


def test_claude_command_is_isolated_and_prefixed():
    cmd = run_eval.build_command("claude", "Add a lambda", "sonnet", 4)
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[2].startswith(run_eval.PREFIX) and cmd[2].endswith("Add a lambda")
    for flag in ["--model", "sonnet", "--max-turns", "4", "--output-format", "json",
                 "--setting-sources", "--strict-mcp-config", "--disable-slash-commands"]:
        assert flag in cmd
    assert cmd[cmd.index("--setting-sources") + 1] == "project,local"


def fake_runner(calls, answer="uses warm_targets", cost=0.05):
    def run(cmd, cwd, env):
        calls.append((cmd, cwd))
        return json.dumps({"result": answer, "total_cost_usd": cost,
                           "usage": {"input_tokens": 100, "output_tokens": 50}})
    return run


def setup(tmp_path):
    p = tmp_path / "p.yaml"
    p.write_text(PROMPTS)
    return p, tmp_path / "A", tmp_path / "B"


def test_dry_run_runs_nothing(tmp_path, capsys):
    p, a, b = setup(tmp_path)
    calls = []
    rc = run_eval.main(["--prompts", str(p), "--a", str(a), "--b", str(b), "--runs", "3", "--dry-run"],
                       runner=fake_runner(calls))
    out = capsys.readouterr().out
    assert rc == 0 and calls == []
    assert "6 runs" in out and out.count("claude -p") == 6 and str(a) in out


def test_measure_one_runs_once_and_estimates(tmp_path, capsys):
    p, a, b = setup(tmp_path)
    calls = []
    rc = run_eval.main(["--prompts", str(p), "--a", str(a), "--b", str(b), "--runs", "3", "--measure-one"],
                       runner=fake_runner(calls, cost=0.05))
    out = capsys.readouterr().out
    assert rc == 0 and len(calls) == 1 and calls[0][1] == str(a)
    assert "total_cost_usd: 0.05" in out and "input_tokens" in out
    assert "estimated full batch (6 runs): $0.30" in out


def test_full_mode_table_verdicts_and_exit(tmp_path, capsys):
    p, a, b = setup(tmp_path)

    def runner(cmd, cwd, env):
        txt = "warm_targets and RESOURCES.md" if cwd == str(a) else "warm_targets only"
        return json.dumps({"result": txt, "total_cost_usd": 0.01})
    out_file = tmp_path / "res.json"
    rc = run_eval.main(["--prompts", str(p), "--a", str(a), "--b", str(b), "--runs", "3",
                        "--out", str(out_file)], runner=runner)
    out = capsys.readouterr().out
    assert rc == 1
    assert "warm | A 3/3 | B 3/3 | failed A0/B0 | ok" in out
    assert "docs | A 3/3 | B 0/3 | failed A0/B0 | FAIL" in out
    raw = [json.loads(x) for x in out_file.read_text().splitlines()]
    assert len(raw) == 6 and raw[0]["variant"] == "A" and "output" in raw[0]


def test_one_run_drop_is_not_a_fail(tmp_path, capsys):
    p, a, b = setup(tmp_path)
    n = {"B": 0}

    def runner(cmd, cwd, env):
        if cwd == str(b):
            n["B"] += 1
            return json.dumps({"result": "scheduler" if n["B"] > 1 else "nothing"})
        return json.dumps({"result": "scheduler"})
    rc = run_eval.main(["--prompts", str(p), "--a", str(a), "--b", str(b), "--runs", "3",
                        "--out", str(tmp_path / "r.json")], runner=runner)
    assert "warm | A 3/3 | B 2/3 | failed A0/B0 | ok" in capsys.readouterr().out


def test_claude_command_is_read_only_by_construction():
    cmd = run_eval.build_command("claude", "x")
    assert cmd[cmd.index("--permission-mode") + 1] == "plan"
    denied = cmd[cmd.index("--disallowedTools") + 1].split(",")
    for t in ["Bash", "Edit", "Write", "NotebookEdit", "WebFetch", "WebSearch", "mcp__*"]:
        assert t in denied
    assert cmd[cmd.index("--allowedTools") + 1] == "Read,Grep,Glob"


def test_codex_command_read_only_sandbox():
    cmd = run_eval.build_command("codex", "x")
    assert cmd[:2] == ["codex", "exec"] and cmd[cmd.index("--sandbox") + 1] == "read-only"


ARGS = lambda p, a, b, out, *x: ["--prompts", str(p), "--a", str(a), "--b", str(b), "--runs", "2",
                                  "--out", str(out), *x]


def test_failures_recorded_and_batch_continues(tmp_path, capsys):
    p, a, b = setup(tmp_path)
    n = {"i": 0}

    def runner(cmd, cwd, env):
        n["i"] += 1
        if n["i"] == 1:
            raise RuntimeError("claude exited 1: boom")
        if n["i"] == 2:
            return json.dumps({"is_error": True, "subtype": "error_max_turns", "result": "warm_targets"})
        return json.dumps({"result": "warm_targets RESOURCES.md"})
    out = tmp_path / "o.jsonl"
    rc = run_eval.main(ARGS(p, a, b, out), runner=runner)
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    assert len(rows) == 4 and rows[0]["failed"] and "boom" in rows[0]["error"]
    assert rows[1]["failed"] and rows[1]["output"] == "" and "error_max_turns" in rows[1]["error"]
    t = capsys.readouterr().out
    assert "A 1/2 | B 1/2 | failed A1/B1" in t


def test_resume_skips_done_runs(tmp_path):
    p, a, b = setup(tmp_path)
    out = tmp_path / "o.jsonl"
    c1 = []
    run_eval.main(ARGS(p, a, b, out), runner=fake_runner(c1))
    assert len(c1) == 4
    lines = out.read_text().splitlines()
    out.write_text("\n".join(lines[:3]) + "\n")
    c2 = []
    run_eval.main(ARGS(p, a, b, out, "--resume"), runner=fake_runner(c2))
    assert len(c2) == 1 and len(out.read_text().splitlines()) == 4
    c3 = []
    run_eval.main(ARGS(p, a, b, out), runner=fake_runner(c3))  # no --resume: starts over
    assert len(c3) == 4 and len(out.read_text().splitlines()) == 4
