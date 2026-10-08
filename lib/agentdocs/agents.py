"""Instruction-file facts per coding agent, and budget warnings against them."""
import re
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from .mdsections import FENCE

# name glob -> [(limit kind, limit, source)]. Limits are vendor guidance, not enforced here.
CODEX = ("bytes", 32 * 1024, "https://learn.chatgpt.com/docs/agent-configuration/agents-md")
LIMITS = {
    # Claude Code: target under 200 lines per CLAUDE.md.
    # https://code.claude.com/docs/en/memory
    # CLAUDE.md is typically shared with Codex (AGENTS.md symlink/import), so the Codex
    # byte cap applies too.
    "CLAUDE.md": [("lines", 200, "https://code.claude.com/docs/en/memory"), CODEX],
    # Codex: AGENTS.md content beyond project_doc_max_bytes (default 32 KiB) is not loaded.
    # https://learn.chatgpt.com/docs/agent-configuration/agents-md
    "AGENTS.md": [CODEX],
    # Cursor: rules recommended under 500 lines.
    # https://cursor.com/docs/context/rules
    "*.mdc": [("lines", 500, "https://cursor.com/docs/context/rules")],
}
INFO_ONLY = ["GEMINI.md"]  # no documented size limit found: report size, never fail

MAX_HOPS = 4
IMPORT = re.compile(r"(?:(?<=\s)|^)@([\w./~-]+)")


def _strip_inline_code(line):
    return re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line)


def effective_text(path, _stack=None, _hop=0):
    """File text with `@path` imports expanded (relative to the importing file).

    Imports in code fences/spans are ignored; max 4 hops; cycles are left unexpanded."""
    path = Path(path).resolve()
    stack = (_stack or []) + [path]
    out, fence = [], None
    raw = path.read_text(errors="replace")
    for line in raw.splitlines():
        m = FENCE.match(line)
        if m:
            fence = None if fence else m.group(1)[0]
            out.append(line)
            continue
        target = None
        if not fence:
            mm = IMPORT.search(_strip_inline_code(line))
            if mm:
                cand = (path.parent / mm.group(1)).resolve() if not mm.group(1).startswith("~") \
                    else Path(mm.group(1)).expanduser()
                if cand.is_file() and cand not in stack and _hop < MAX_HOPS:
                    target = cand
        if target:
            out.append(effective_text(target, stack, _hop + 1).rstrip("\n"))
        else:
            out.append(line)
    return "\n".join(out) + ("\n" if raw.endswith("\n") else "")


def limits_for(path):
    name = PurePosixPath(str(path)).name
    for pat, spec in LIMITS.items():
        if fnmatch(name, pat):
            return spec
    return []


def budget(path):
    """Warnings for the effective file at `path` (imports expanded); [] = within budget."""
    specs = limits_for(path)
    if not specs:
        return []
    text = effective_text(path)
    size = len(text.encode())
    name = PurePosixPath(str(path)).name
    out = []
    for kind, limit, src in specs:
        n = len(text.splitlines()) if kind == "lines" else size
        if n > limit:
            out.append(f"{name}: {n} {kind} exceeds {limit} ({src})")
    return out


def info(path):
    """Informational size lines for files with no documented limit."""
    name = PurePosixPath(str(path)).name
    if name not in INFO_ONLY:
        return []
    text = effective_text(path)
    return [f"{name}: {len(text.splitlines())} lines, {len(text.encode())} bytes (no documented limit)"]
