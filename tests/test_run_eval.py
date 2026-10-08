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
    assert "warm | A 3/3 | B 3/3 | ok" in out
    assert "docs | A 3/3 | B 0/3 | FAIL" in out
    raw = json.loads(out_file.read_text())
    assert len(raw["runs"]) == 6 and raw["runs"][0]["variant"] == "A" and "output" in raw["runs"][0]


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
    assert "warm | A 3/3 | B 2/3 | ok" in capsys.readouterr().out
