"""Dead-link detection: outbound links of a file, inbound anchor references to it."""
import re
import subprocess
from pathlib import Path, PurePosixPath

from . import mdsections

LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.I)


def _outside_fences(text):
    """Yield (lineno, line) for lines not inside a fenced code block."""
    fence = None
    for no, line in enumerate(text.splitlines(), 1):
        m = mdsections.FENCE.match(line)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker[0], len(marker)
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            continue
        if not fence:
            yield no, line


def outbound(repo, file):
    repo = Path(repo)
    src = repo / file
    dead = []
    for no, line in _outside_fences(src.read_text()):
        for m in LINK.finditer(line):
            href = m.group(1)
            if EXTERNAL.match(href):
                continue
            path, _, anchor = href.partition("#")
            target = src if not path else (src.parent / path)
            if not target.exists():
                dead.append({"target": href, "line": no, "reason": "missing target"})
            elif anchor and target.suffix.lower() == ".md" and target.is_file() \
                    and anchor.lower() not in mdsections.anchors(target.read_text()):
                dead.append({"target": href, "line": no, "reason": "anchor not found"})
    return dead


def inbound(repo, file):
    """Anchor references to `file` from other tracked files that no longer resolve."""
    repo = Path(repo).resolve()
    target = (repo / file).resolve()
    anchors = mdsections.anchors(target.read_text())
    name = re.escape(target.name)
    rx = re.compile(rf"([\w./~-]*{name})#([\w-]+)")
    r = subprocess.run(["git", "grep", "-nIE", rf"{name}#", "--", "."], cwd=str(repo),
                       capture_output=True, text=True)
    bad = []
    for row in r.stdout.splitlines():
        path, no, text = row.split(":", 2)
        if (repo / path).resolve() == target:
            continue
        for m in rx.finditer(text):
            ref, anchor = m.groups()
            cands = {(repo / PurePosixPath(path).parent / ref).resolve(), (repo / ref).resolve()}
            if target in cands and anchor.lower() not in anchors:
                bad.append({"path": path, "line": int(no), "anchor": anchor, "text": text.strip()[:200]})
    return bad
