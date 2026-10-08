"""Split markdown into heading-delimited sections and compute GitHub anchor slugs."""
import re
from dataclasses import dataclass

HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


@dataclass
class Section:
    heading: str
    level: int
    start: int  # 1-based, inclusive
    end: int    # 1-based, inclusive
    lines: int
    bytes: int


def iter_headings(text):
    """Yield (lineno, level, heading) for headings outside fenced code blocks."""
    fence = None
    for no, line in enumerate(text.splitlines(), 1):
        m = FENCE.match(line)
        if m:
            marker = m.group(1)
            if fence is None:
                fence = marker[0], len(marker)
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            continue
        if fence:
            continue
        h = HEADING.match(line)
        if h:
            yield no, len(h.group(1)), h.group(2)


def split(text, level=2):
    lines = text.splitlines(keepends=True)
    marks = [(no, h) for no, lv, h in iter_headings(text) if lv == level]
    bounds = [(1, "")] + marks if not marks or marks[0][0] > 1 else marks
    out = []
    for i, (start, heading) in enumerate(bounds):
        end = bounds[i + 1][0] - 1 if i + 1 < len(bounds) else len(lines)
        if end < start:
            continue
        chunk = "".join(lines[start - 1:end])
        out.append(Section(heading, level if heading else 0,
                           start, end, end - start + 1, len(chunk.encode())))
    return out


def slug(heading, seen=None):
    """GitHub anchor slug. Pass a dict as `seen` to number duplicates (-1, -2)."""
    s = re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
    if seen is None:
        return s
    n = seen.get(s, -1) + 1
    seen[s] = n
    return s if n == 0 else f"{s}-{n}"


def anchors(text):
    """All anchor slugs of every heading in a markdown text (duplicates numbered)."""
    seen = {}
    return {slug(h, seen) for _, _, h in iter_headings(text)}
