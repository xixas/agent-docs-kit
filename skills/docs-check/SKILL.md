---
name: docs-check
description: Find docs a code change made stale before it ships: run on a branch or commit, judge each candidate doc, update or dismiss it. Use before pushing or opening a PR, when asked "did I miss any docs", or to set up a repo's .docs-map.yaml.
---

# docs-check

A script turns the git diff into **candidates**, docs that may now say something untrue. You do the judging. The script is advisory: it never blocks, and a candidate is a lead, not a verdict.

## Steps

1. **Config.** Read `<repo>/.docs-map.yaml`. If it is missing, go to *Setting up a repo* below, then come back.
2. **Run** the `check_docs_map.py` that sits next to this file:
   ```
   python3 <this-skill-dir>/check_docs_map.py --repo <repo> [--base main | --commit SHA] [--json]
   ```
   The default compares the merge-base with `main` to the working tree, including uncommitted and untracked files. Exit 2 means the config is broken or a rule names a target that doesn't exist. Fix the config before going further.
3. **Judge every candidate.** Open the doc at the cited line and check it against the change:
   - `[rule]`: the change touched something this doc describes. Update the doc only if what it says is now untrue. If the rule prints `run:`, execute that command; generated docs are regenerated, never edited by hand.
   - `[stale]` / `[stale-comment]`: the diff removed this value, and a doc (or a code comment or docstring) still names it. Usually stale. A value written as a minimum ("3.11+") or as history is still true.
   - `[code]`, listed under "still used elsewhere": other code may also need the new value. Report it, but leave it alone unless it is inside the change you are making.
4. **Done** when every candidate has exactly one outcome: *updated* (with the file you changed) or *dismissed* (with a one-line reason, e.g. "says 3.11+ as a minimum, still true"). Report them as a table: `Candidate | Outcome | Reason`.

## Setting up a repo

Start from the closest file in `<kit>/templates/` (the kit is the repo this skill's folder is symlinked from), or from `<kit>/examples/`. Every rule is `when` → `update`:

- `paths`: a changed file matches a glob. On its own this is too noisy. Pair it with `diff_regex` whenever the doc depends on *what* changed, not *where*. A paths-only check scored 1 useful flag out of 14 on a real repo.
- `added`: fires only on new files (new stack, script, skill, Lambda).
- `diff_regex`: matched against the added and removed lines of the files matching `paths`.
- `update` lists the docs to check, `run` gives a regen command, and `note` says what to look for.

Put generated docs (portal, Postman, OpenAPI output) in `exclude`. Rerun the script over the repo's last ~25 commits (`--commit` per SHA) and tighten any rule that flags more noise than real misses.
