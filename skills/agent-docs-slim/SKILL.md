---
name: agent-docs-slim
description: Slim an agent instruction file (CLAUDE.md, AGENTS.md, GEMINI.md, Cursor rules) into a short index of rules and pointers, with reference moved to docs and copies of the code deleted, proven by an A/B eval. Use when such a file is long, stale or over budget, or when asked to restructure, audit or share one across coding agents.
---

# agent-docs-slim

The root instruction file loads into every session of every agent. It holds only what an agent must **do** (rules) plus one-line **pointers** to everything else. Anything that only copies the code goes. Facts that only some tasks need move to `docs/`. Read the `writing-for-agents` skill first if it is installed: its pointer wording and pruning rules apply line by line.

## Why this shape

| Mechanism | What happens | Use |
|---|---|---|
| Root file | Loaded every session | Rules + pointers only |
| Nested files / path-scoped rules | Load only on file touch. Timing differs per agent, and in a test their instructions were obeyed only some of the time | Never for rules |
| `@imports` | Expanded at launch, so they save nothing | No |
| `docs/*.md` behind a pointer | Read when the pointer's wording matches the task | Facts, never instructions |

Codex reads only the first 32 KiB of `AGENTS.md`, and Claude's target is ≤200 lines. To serve every agent from one file, make `AGENTS.md` the source and make `CLAUDE.md` contain `@AGENTS.md` plus any Claude-only lines.

## Steps

1. **Measure.** Run `python3 <this-skill-dir>/slim_check.py <file> --repo <repo>`. It reports sections by size, dead links and broken inbound anchors, plus budget warnings on the *effective* file, with `@imports` expanded (lines for CLAUDE.md, bytes for CLAUDE.md and AGENTS.md). Exit 2 means the file is missing.
2. **Sort every section** into one row: `Section | Kind | Destination | Stale claims`.
   - **ENFORCED**: a hook, skill, lint, CI check or local config already enforces it *at the moment of action* (hookify blocks on commit, `/deploy` defaults, git config, a docs-map rule). Delete it. Keep one line only for agents the mechanism can't reach (Claude hooks and skills don't run in Codex). If it could be enforced and isn't, propose the hook or skill in the table.
   - **RULE**: changes what the agent does (a gotcha, a must-do, a never-do that has no positive phrasing). If it is only caught later, at push or review, it still stays as one line, so the agent gets it right first time.
   - **POINTER**: names a doc. It stays, as one line led by its trigger words: `Auth flows, Cognito domains → docs/auth.md`.
   - **CACHE**: restates what the code, config, directory layout or `--help` already says. It is deleted. If finding the source is not obvious, leave a pointer to it.
   - **REFERENCE**: true facts that only some tasks need. They move to `docs/<topic>.md`, written as facts, with a pointer left behind.
   For each row, spot-check one or two concrete claims against the code (counts, names, paths) and record what is stale. Also grep the repo for inbound references to the file and its anchors (skills, README, hooks, scripts), since those break if you move their target. Done when every section has a row.
3. **Freeze the eval before editing.** Hand the RULE and ENFORCED rows to a separate subagent. It writes `prompts.yaml` for `agent-ab-eval`: one task prompt per rule, phrased as real work ("write a script that backfills X in staging"), never as a quiz, with a regex showing the rule was applied. Save the file outside the edit. It stays frozen from here on.
4. **Approval.** Show the table plus the target line count. Wait for the user's go before step 5.
5. **Apply** on a branch or in a git worktree: keep rules, write pointers, delete caches, move reference, fix every stale claim, and repair every inbound reference. Build each approved new enforcement too: a hook (a hookify rule file if the repo uses hookify, otherwise a `hooks` entry in `.claude/settings.json`), a skill for any multi-step procedure, or a `.docs-map.yaml` rule (set up with `docs-check`). Delete the text it replaces only once it exists.
6. **Verify.**
   - `slim_check.py` exits 0.
   - Every RULE row's content is still in the root file.
   - Run `agent-ab-eval` with the original file as A and the slim one as B. Use `--measure-one` first, show the user the cost, and run the full batch only on their OK.
   Eval runs have hooks and skills switched off, so ENFORCED rows are reported but excluded from the verdict. Done when all three hold. If the eval fails on a rule, move that content back into the root file, then rerun.
7. **Report**: lines before and after, the move table, the eval table, and what is left for the user (commit, push).
