"""Stale-value pass: tokens removed by a diff that docs may still mention."""
import re
import subprocess
from dataclasses import dataclass

from .docsmap import any_glob

VERSION = re.compile(r"(?<![\w.])\d+\.\d+(?:\.\d+)?(?![\w]|\.\d)")
PY_ENUM = re.compile(r"PYTHON_(\d+)_(\d+)")
PY_BARE = re.compile(r"python(\d+)\.(\d+)", re.I)
NODE = re.compile(r"(?:NODEJS_(\d+)_X|nodejs(\d+)\.x)", re.I)
ENVVAR = re.compile(r"(?<![A-Za-z0-9_])[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+(?![A-Za-z0-9_])")
HOST = re.compile(r"(?<![\w.-])[a-z0-9-]+(?:\.[a-z0-9-]+)+\.(?:com|net|io|org|app|dev|cloud)\b")


@dataclass(frozen=True)
class Token:
    label: str    # human-readable, also the key
    regex: str    # pattern used to search docs and code


def _plain(value):
    return Token(value, r"(?<![\w.-])" + re.escape(value) + r"(?![\w-]|\.\d)")


def extract_tokens(text):
    out = set()
    for m in PY_ENUM.finditer(text):
        out.add(_plain(f"{m[1]}.{m[2]}"))
    for m in PY_BARE.finditer(text):
        out.add(_plain(f"{m[1]}.{m[2]}"))
    for m in NODE.finditer(text):
        v = m[1] or m[2]
        out.add(Token(f"nodejs{v}",
                      rf"(?i)node(?:\.?js)?[\s_-]*v?{v}(?:\.x|_x)?(?![\w.])"))
    for m in VERSION.finditer(text):
        out.add(_plain(m[0]))
    for m in ENVVAR.finditer(text):
        v = m[0]
        if len(v) >= 6 and not PY_ENUM.fullmatch(v) and not NODE.fullmatch(v):
            out.add(_plain(v))
    for m in HOST.finditer(text):
        out.add(_plain(m[0]))
    return out


def stale_tokens(lines, ignore=()):
    """Tokens in removed lines and in no added line, across the whole diff."""
    removed, added = set(), set()
    for path, fd in lines.items():
        if ignore and any_glob(path, list(ignore)):
            continue
        for t in fd.removed:
            removed |= extract_tokens(t)
        for _, t in fd.added:
            added |= extract_tokens(t)
    return sorted(removed - added, key=lambda t: t.label)


def _grep(repo, needle, excludes):
    spec = [":(exclude,glob)" + g for g in excludes]
    r = subprocess.run(
        ["git", "grep", "--untracked", "-I", "-i", "-n", "-F", "-e", needle, "--", ".", *spec],
        cwd=str(repo), capture_output=True, text=True)
    return r.stdout.splitlines()  # exit 1 == no matches


def drop_tokens_in_code(repo, tokens, docs, exclude):
    """Drop tokens that a non-doc tracked file still contains."""
    excludes = list(docs) + list(exclude)
    kept = []
    for t in tokens:
        rx = re.compile(t.regex)
        still_used = False
        for line in _grep(repo, t.label, excludes):
            _, _, rest = line.split(":", 2)   # path:lineno:text
            if rx.search(rest):
                still_used = True
                break
        if not still_used:
            kept.append(t)
    return kept


@dataclass
class Hit:
    token: str
    path: str
    line: int
    text: str
    changed: bool


def doc_files(repo, docs, exclude):
    r = subprocess.run(["git", "ls-files", "-co", "--exclude-standard", "-z"],
                       cwd=str(repo), capture_output=True, text=True)
    paths = [p for p in r.stdout.split("\0") if p]
    return sorted(p for p in set(paths)
                  if any_glob(p, docs) and not any_glob(p, exclude))


def find_in_docs(repo, tokens, docs, exclude, changed):
    from pathlib import Path
    compiled = [(t, re.compile(t.regex)) for t in tokens]
    hits = []
    for path in doc_files(repo, docs, exclude):
        try:
            text = (Path(repo) / path).read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for no, line in enumerate(text.splitlines(), 1):
            for t, rx in compiled:
                if rx.search(line):
                    hits.append(Hit(t.label, path, no, line.strip()[:200], path in changed))
    return hits
