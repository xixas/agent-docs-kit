# agent-docs-kit

Three skills for coding agents (Claude Code, Codex) that keep a repo's agent instructions short
and its docs true to the code.

| Skill | What it does | Reach for it when |
|---|---|---|
| `docs-check` | Turns a git diff into a list of docs that may now be stale, then has the agent judge each one: update it or dismiss it with a reason. | Before every push, in a repo that has a `.docs-map.yaml`. Or to set one up. |
| `agent-docs-slim` | Rewrites a long `CLAUDE.md` / `AGENTS.md` into a short index of rules and pointers. Reference material moves to `docs/`, copies of the code are deleted, and rules a hook already enforces come out. | The instruction file is long, stale, or over budget (Claude: about 200 lines; Codex reads only the first 32 KiB). |
| `agent-ab-eval` | Runs frozen task prompts through headless `claude` against the old and new instruction file, and scores rule by rule whether the agent still applied each one. | Before shipping any change to an instruction file or skill. `agent-docs-slim` uses it as its proof step. |

They work as a chain. `agent-docs-slim` makes the file small, `agent-ab-eval` proves nothing was
lost, and `docs-check` keeps the moved docs from drifting afterwards.

## Requirements

- `git` and `python3` with PyYAML (`python3 -m pip install --user pyyaml`). Tested on Python 3.14.
- `agent-ab-eval` also needs the `claude` CLI, logged in. Each eval run is a real agent session
  and spends your usage, so the skill measures one run and asks before the batch.
- Recommended: Matt Pocock's [`writing-for-agents`](https://github.com/mattpocock/skills/tree/main/skills/productivity/writing-for-agents)
  skill. `agent-docs-slim` reads it, when it is installed, for the wording of rules and pointers.
  It still works without it. `install.sh` fetches it for you.

## Install

```bash
git clone https://github.com/xixas/agent-docs-kit.git ~/work/tools/agent-docs-kit
~/work/tools/agent-docs-kit/install.sh
```

`install.sh` symlinks each skill into `~/.claude/skills/` (Claude Code) and `~/.agents/skills/`
(Codex). It also copies `writing-for-agents` from `mattpocock/skills` into both, unless that skill
is already there.

- **Symlinks, not copies.** The scripts load `lib/` through the link's real path. A copied
  skill folder fails with `ModuleNotFoundError: agentdocs`.
- **Update:** `git -C ~/work/tools/agent-docs-kit pull`. The links pick up the change.
- **Links only, no dependency fetch:** `./install.sh --no-deps`.
- **Uninstall:** `./install.sh --uninstall` removes only the links that point into this kit.
- **Don't also vendor these skills into a repo.** An agent that sees the same skill twice lists
  it twice.

## Use

In an agent session, ask in plain words ("check the docs before I push", "slim our CLAUDE.md")
or call the skill by name: `/docs-check`, `/agent-docs-slim`, `/agent-ab-eval`. The agent runs
the scripts below itself, but each one also works standalone:

```bash
# Docs a diff may have made stale (advisory; exit 2 = broken config or no base branch)
python3 skills/docs-check/check_docs_map.py --repo REPO [--base main | --commit SHA] [--json]

# Section sizes, agent budgets, dead links, broken inbound anchors (exit 1 on any problem)
python3 skills/agent-docs-slim/slim_check.py FILE [--repo REPO] [--level 2] [--json]

# A/B eval of two checkouts (dry-run first, then measure one run's cost)
python3 skills/agent-ab-eval/run_eval.py --prompts prompts.yaml --a DIR_A --b DIR_B --dry-run
```

`docs-check` needs a `.docs-map.yaml` in the target repo. Start from
`templates/python-service.docs-map.yaml`, or see `examples/aws-cdk-service.docs-map.yaml` for a
real one. Each `SKILL.md` documents its full procedure.

## Layout

```
skills/<name>/SKILL.md   what the agent follows
skills/<name>/*.py       the skill's script
lib/agentdocs/           shared code (diff parsing, docs map, stale values, links, budgets)
templates/  examples/    starter and real .docs-map.yaml files
tests/                   python3 -m pytest -q
install.sh               symlink the skills, fetch writing-for-agents
```
