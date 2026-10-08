#!/usr/bin/env python3
"""A/B harness: how does a coding agent behave with two versions of an instruction file?

Each run happens in a variant checkout (--a / --b) in plan-only mode; the agent's final
answer is scored against regex checks from prompts.yaml.

Claude isolation (from `claude --help`):
  --setting-sources project,local   "Comma-separated list of setting sources to load
                                     (user, project, local)." Drops user-level settings
                                     (~/.claude/settings.json, hooks, user CLAUDE.md).
                                     Project CLAUDE.md of the variant dir stays loaded:
                                     that is the thing under test.
  --strict-mcp-config               "Only use MCP servers from --mcp-config, ignoring all
                                     other MCP configurations" (none given -> no MCP).
  --disable-slash-commands          "Disable all skills".
  env CLAUDE_CODE_DISABLE_AUTO_MEMORY=1  turns off auto-memory (~/.claude/projects/*/memory).
Rejected: --bare ("skip ... CLAUDE.md auto-discovery", and OAuth/keychain never read, so it
needs an API key and would also drop the file under test).
Caveat: isolation is not perfect. Managed/policy settings still apply, the built-in system
prompt is unchanged, and whether --setting-sources user fully covers ~/.claude/CLAUDE.md
should be confirmed once with --measure-one before trusting a batch.

Codex: `codex exec --sandbox read-only <prompt>` (command builder only; codex is not installed here, UNTESTED).
"""
import argparse
import json
import os
import re
import subprocess
import sys

PREFIX = ("Plan only: describe what you would do and which repo rules apply. "
          "Do not edit files or run commands that change anything.")
# Read-only by construction: plan mode + deny every mutating/network tool. The variant's
# settings.local.json allow-rules (e.g. Bash(git push:*)) are loaded by --setting-sources
# project,local, so deny-rules (which win over allow) are what make this safe.
DENIED = "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch,mcp__*"
ENV = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}


def build_command(agent, prompt, model="sonnet", max_turns=4):
    full = f"{PREFIX}\n\n{prompt}"
    if agent == "claude":
        return ["claude", "-p", full, "--model", model, "--max-turns", str(max_turns),
                "--output-format", "json", "--setting-sources", "project,local",
                "--strict-mcp-config", "--disable-slash-commands",
                "--permission-mode", "plan",
                "--allowedTools", "Read,Grep,Glob",
                "--disallowedTools", DENIED]
    if agent == "codex":
        # UNTESTED. Read-only sandbox; exec is non-interactive so no approval flag is passed.
        return ["codex", "exec", "--sandbox", "read-only", full]
    raise ValueError(f"unknown agent: {agent}")


def load_prompts(path):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)["prompts"]


def subprocess_runner(cmd, cwd, env):
    """The only place that really spawns an agent."""
    r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **env}, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} exited {r.returncode}: {r.stderr.strip()[:300]}")
    return r.stdout


def parse_output(agent, stdout):
    """Normalise agent output to a dict with at least `result` (the final answer)."""
    if agent == "codex":  # UNTESTED: codex exec prints the final answer on stdout
        return {"result": stdout}
    return json.loads(stdout)


def score(prompts, raw, runs):
    """Per-check hit counts for A and B. FAIL when B trails A by more than 1 run."""
    rows = []
    for p in prompts:
        for c in p.get("checks", []):
            rx = [re.compile(x, re.I) for x in c["any"]]
            hits = {"A": 0, "B": 0}
            nfail = {"A": 0, "B": 0}
            for r in raw:
                if r["prompt_id"] != p["id"]:
                    continue
                nfail[r["variant"]] += bool(r.get("failed"))
                if not r.get("failed") and any(x.search(r["output"]) for x in rx):
                    hits[r["variant"]] += 1
            verdict = "FAIL" if hits["A"] - hits["B"] > 1 else "ok"
            rows.append({"rule": c["rule"], "A": hits["A"], "B": hits["B"], "verdict": verdict,
                         "failed_A": nfail["A"], "failed_B": nfail["B"]})
    return rows


def execute(runner, args, cmd, d, v, p, i):
    """One run -> one JSONL row. Never raises: errors become failed rows."""
    row = {"variant": v, "prompt_id": p["id"], "run": i + 1, "output": "", "failed": False,
           "error": None, "total_cost_usd": None, "usage": None}
    try:
        data = parse_output(args.agent, runner(cmd, str(d), ENV))
        row["total_cost_usd"], row["usage"] = data.get("total_cost_usd"), data.get("usage")
        if data.get("is_error") or str(data.get("subtype", "success")).startswith("error"):
            row.update(failed=True, error=f"{data.get('subtype', 'error')}: {str(data.get('result', ''))[:300]}")
        else:
            row["output"] = data.get("result", "")
    except Exception as e:  # noqa: BLE001 - a bad run must not abort the batch
        row.update(failed=True, error=str(e)[:500])
    return row


def plan(prompts, a, b, runs):
    """[(variant, dir, prompt_dict, run_index)] in execution order."""
    return [(v, d, p, i) for p in prompts for i in range(runs) for v, d in (("A", a), ("B", b))]


def _shell(cmd):
    return " ".join(repr(c) if re.search(r"[\s\"']", c) else c for c in cmd)


def main(argv=None, runner=subprocess_runner):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prompts", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--max-turns", type=int, default=4)
    ap.add_argument("--agent", choices=["claude", "codex"], default="claude")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--measure-one", action="store_true")
    ap.add_argument("--out", default="results.jsonl", help="JSONL, one line per run")
    ap.add_argument("--resume", action="store_true", help="skip runs already in --out")
    args = ap.parse_args(argv)
    prompts = load_prompts(args.prompts)
    jobs = plan(prompts, args.a, args.b, args.runs)

    def cmd_for(p):
        return build_command(args.agent, p["prompt"], args.model, args.max_turns)

    if args.dry_run:
        print(f"{len(jobs)} runs ({len(prompts)} prompts x {args.runs} runs x 2 variants)")
        for v, d, p, i in jobs:
            print(f"[{v} #{i + 1} {p['id']}] (cd {d}) {_shell(cmd_for(p))}")
        return 0
    if args.measure_one:
        v, d, p, _ = jobs[0]
        data = parse_output(args.agent, runner(cmd_for(p), str(d), ENV))
        cost = data.get("total_cost_usd") or 0.0
        print(f"total_cost_usd: {cost}")
        print(f"usage: {json.dumps(data.get('usage'))}")
        print(f"estimated full batch ({len(jobs)} runs): ${cost * len(jobs):.2f}")
        return 0
    done = {}
    if args.resume and os.path.exists(args.out):
        with open(args.out) as f:
            for line in f:
                r = json.loads(line)
                done[(r["variant"], r["prompt_id"], r["run"])] = r
    elif os.path.exists(args.out):
        os.remove(args.out)
    for v, d, p, i in jobs:
        if (v, p["id"], i + 1) in done:
            continue
        row = execute(runner, args, cmd_for(p), d, v, p, i)
        with open(args.out, "a") as f:
            f.write(json.dumps(row) + "\n")
        done[(v, p["id"], i + 1)] = row
    raw = [done[(v, p["id"], i + 1)] for v, d, p, i in jobs]
    rows = score(prompts, raw, args.runs)
    print("rule | A hits/N | B hits/N | failed | verdict")
    failed = False
    for r in rows:
        print(f"{r['rule']} | A {r['A']}/{args.runs} | B {r['B']}/{args.runs} | "
              f"failed A{r['failed_A']}/B{r['failed_B']} | {r['verdict']}")
        failed = failed or r["verdict"] == "FAIL"
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
