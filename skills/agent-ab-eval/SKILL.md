---
name: agent-ab-eval
description: A/B-test a change to an agent instruction file or skill (CLAUDE.md, AGENTS.md, SKILL.md) by running frozen task prompts against the old and new version through headless claude or codex and comparing, rule by rule, whether the agent still applied each one. Use before shipping such a change, or when asked to prove a slimmed or rewritten instruction file still works.
---

# agent-ab-eval

Proves an instruction change kept its behaviour. Each run is a real headless agent session, so it spends the user's usage: measure first, and keep runs few and short.

## Steps

1. **Two checkouts.** A = the current version (usually the main checkout). B = the changed version (`git worktree add <dir> <branch>`). Both must be complete repos, because the agent reads them.
2. **Prompts.** You need a `prompts.yaml` written *before* the change, ideally by a different agent than the one that made it, so the checks can't be tuned to the result:
   ```yaml
   prompts:
     - id: shared-neptune
       prompt: "Write a script that backfills Account display names in staging."
       checks:
         - rule: shared-neptune
           any: ["shared", "production (too|as well)", "visible in prod"]
   ```
   Use one task prompt per rule, phrased as real work. A check passes when any of its regexes matches the final answer. The harness adds a plan-only prefix, and every run is read-only by construction: plan mode, Read/Grep/Glob only, with Bash, Edit, Write, web and MCP tools disallowed. A repo's own allow-rules cannot open them back up. Prompts are therefore scored on what the agent *says* it would do.
3. **Dry run.** Run `python3 <this-skill-dir>/run_eval.py --prompts P --a A --b B --dry-run` and confirm the run count (prompts × runs × 2).
4. **Measure one.** Run `--measure-one` and show the user the cost of one run and the estimate for the batch. Continue only on their OK.
5. **Full run.** The defaults are `--runs 3 --max-turns 4 --model sonnet`. Each run is appended to `--out` (JSONL) as it finishes. A run that errors or hits the turn limit counts as a miss and is shown in the `failed` column. After an interruption, rerun with `--resume`. The run exits 1 when any rule scores more than one run lower on B than on A. `--agent codex` (with `--sandbox read-only`) is untested: say so if you use it.
6. **Report** the table `rule | A | B | verdict`. For each FAIL, quote what B said instead, and name the content whose move likely caused it.

Three runs per cell catch a rule that broke, not a subtle drift. Say so in the report rather than claiming more.
