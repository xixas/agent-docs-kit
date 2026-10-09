#!/usr/bin/env bash
# Install the agent-docs-kit skills by symlinking them into each agent's skills dir.
# Symlinks, not copies: the scripts find ../../lib through the link's real path.
#
#   ./install.sh               link the skills, fetch writing-for-agents if missing
#   ./install.sh --no-deps     link the skills only
#   ./install.sh --uninstall   remove the links this script made
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGETS=("$HOME/.claude/skills" "$HOME/.agents/skills")   # Claude Code, Codex
DEP_REPO="https://github.com/mattpocock/skills.git"
DEP_PATH="skills/productivity/writing-for-agents"

mode="install"; deps=1
for arg in "$@"; do
  case "$arg" in
    --uninstall) mode="uninstall" ;;
    --no-deps) deps=0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ $mode == uninstall ]]; then
  for t in "${TARGETS[@]}"; do
    for s in "$KIT"/skills/*/; do
      link="$t/$(basename "$s")"
      if [[ -L $link && $(readlink -f "$link") == "$KIT"/skills/* ]]; then
        rm "$link" && echo "removed $link"
      fi
    done
  done
  exit 0
fi

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
python3 -c 'import yaml' 2>/dev/null || { echo "PyYAML is required: python3 -m pip install --user pyyaml" >&2; exit 1; }

for t in "${TARGETS[@]}"; do
  mkdir -p "$t"
  for s in "$KIT"/skills/*/; do
    name="$(basename "$s")"; link="$t/$name"
    if [[ -e $link && ! -L $link ]]; then
      echo "skip $link: a real directory is there, remove it first" >&2; continue
    fi
    ln -sfn "${s%/}" "$link" && echo "linked $link"
  done
done

if [[ $deps == 1 ]]; then
  for t in "${TARGETS[@]}"; do
    [[ -e $t/writing-for-agents ]] && continue
    tmp="$(mktemp -d)"
    git clone -q --depth 1 --filter=blob:none --sparse "$DEP_REPO" "$tmp"
    git -C "$tmp" sparse-checkout set "$DEP_PATH"
    cp -r "$tmp/$DEP_PATH" "$t/writing-for-agents"
    echo "$(git -C "$tmp" rev-parse HEAD) $DEP_PATH" > "$t/writing-for-agents/.upstream"
    rm -rf "$tmp"
    echo "installed $t/writing-for-agents (from mattpocock/skills)"
  done
fi
