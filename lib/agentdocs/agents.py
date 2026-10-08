"""Instruction-file facts per coding agent, and budget warnings against them."""
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

# name glob -> (limit kind, limit, source). Limits are vendor guidance, not enforced here.
LIMITS = {
    # Claude Code: target under 200 lines per CLAUDE.md.
    # https://code.claude.com/docs/en/memory
    "CLAUDE.md": ("lines", 200, "https://code.claude.com/docs/en/memory"),
    # Codex: AGENTS.md content beyond project_doc_max_bytes (default 32 KiB) is not loaded.
    # https://learn.chatgpt.com/docs/agent-configuration/agents-md
    "AGENTS.md": ("bytes", 32 * 1024, "https://learn.chatgpt.com/docs/agent-configuration/agents-md"),
    # Cursor: rules recommended under 500 lines.
    # https://cursor.com/docs/context/rules
    # GEMINI.md: no documented size limit found, so no budget is applied.
    "*.mdc": ("lines", 500, "https://cursor.com/docs/context/rules"),
}


def limit_for(path):
    name = PurePosixPath(str(path)).name
    for pat, spec in LIMITS.items():
        if fnmatch(name, pat):
            return spec
    return None


def budget(path):
    """Warnings for the file at `path` (empty list = within budget or no known limit)."""
    spec = limit_for(path)
    if not spec:
        return []
    data = Path(path).read_bytes()
    text, size_bytes = data.decode("utf-8", "replace"), len(data)
    kind, limit, src = spec
    name = PurePosixPath(str(path)).name
    n = len(text.splitlines()) if kind == "lines" else size_bytes
    if n > limit:
        unit = "lines" if kind == "lines" else "bytes"
        return [f"{name}: {n} {unit} exceeds {limit} ({src})"]
    return []
