#!/usr/bin/env python3
"""docs-check CLI: print docs that may be stale because of a git diff (advisory)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "lib"))

from agentdocs.check import format_text, run_check  # noqa: E402
from agentdocs.docsmap import ConfigError  # noqa: E402
from agentdocs.gitdiff import GitError  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo", default=".")
    ap.add_argument("--config")
    ap.add_argument("--base", help="default: origin/HEAD target, else main, else master")
    ap.add_argument("--commit", help="diff SHA^..SHA instead of merge-base..worktree")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        result = run_check(a.repo, a.config, a.base, a.commit)
    except ConfigError as e:
        print(f"docs-check: config error: {e}", file=sys.stderr)
        return 2
    except GitError as e:
        print(f"docs-check: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2) if a.json else format_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
