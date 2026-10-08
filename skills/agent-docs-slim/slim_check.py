#!/usr/bin/env python3
"""slim_check: verification gate for slimming an agent instruction file.

Prints a section size table, budget warnings, dead outbound links and broken
inbound anchors. Exit 1 if there is any budget warning, dead link or broken
inbound anchor, else 0."""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "lib"))

from agentdocs import agents, links, mdsections  # noqa: E402


def run(file, repo, level):
    path = Path(repo) / file
    secs = sorted(mdsections.split(path.read_text(), level), key=lambda s: s.bytes, reverse=True)
    return {
        "sections": [asdict(s) for s in secs],
        "budget": agents.budget(path),
        "dead_links": links.outbound(repo, file),
        "broken_inbound": links.inbound(repo, file),
    }


def format_text(r):
    out = [f"{'lines':>6} {'bytes':>7}  section"]
    for s in r["sections"]:
        out.append(f"{s['lines']:>6} {s['bytes']:>7}  {s['heading'] or '(preamble)'}")
    out.append("")
    out += [f"[budget] {w}" for w in r["budget"]]
    out += [f"[dead-link] line {d['line']}: {d['target']} ({d['reason']})" for d in r["dead_links"]]
    out += [f"[broken-inbound] {b['path']}:{b['line']}: #{b['anchor']}" for b in r["broken_inbound"]]
    if not (r["budget"] or r["dead_links"] or r["broken_inbound"]):
        out.append("slim-check: OK")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--level", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = run(a.file, a.repo, a.level)
    print(json.dumps(r, indent=2) if a.json else format_text(r))
    return 1 if (r["budget"] or r["dead_links"] or r["broken_inbound"]) else 0


if __name__ == "__main__":
    sys.exit(main())
