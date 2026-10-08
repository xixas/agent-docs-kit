"""Stale-value pass: tokens removed by a diff that docs may still mention."""
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import PurePosixPath

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
    kinds: frozenset = frozenset()  # file extensions it was removed from; empty = any


def kind_of(path):
    ext = PurePosixPath(path).suffix.lower()
    return ".yml" if ext == ".yaml" else ext


def _plain(value):
    if re.fullmatch(r"\d+(\.\d+)+", value):   # versions may be glued to a word: python3.13
        return Token(value, r"(?<![\d.])" + re.escape(value) + r"(?!\w|\.\d)")
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
    """Tokens in removed lines and in no added line, across the whole diff.

    Each token records the file kinds (extensions) it was removed from."""
    removed, added = {}, set()
    for path, fd in lines.items():
        if ignore and any_glob(path, list(ignore)):
            continue
        for t in fd.removed:
            for tok in extract_tokens(t):
                removed.setdefault(tok, set()).add(kind_of(path))
        for _, t in fd.added:
            added |= extract_tokens(t)
    return sorted((replace(t, kinds=frozenset(k)) for t, k in removed.items() if t not in added),
                  key=lambda t: t.label)


def _grep(repo, needle, excludes):
    spec = [":(exclude,glob)" + g for g in excludes]
    r = subprocess.run(
        ["git", "grep", "--untracked", "-I", "-i", "-n", "-F", "-e", needle, "--", ".", *spec],
        cwd=str(repo), capture_output=True, text=True)
    return r.stdout.splitlines()  # exit 1 == no matches


def code_usage(repo, tokens, docs, exclude):
    """Split tokens by whether non-doc code still uses them.

    Returns (kept, elsewhere). A token is dropped only if a file of the same
    kind (extension) it was removed from still contains it. Occurrences in
    other kinds of files are returned in `elsewhere` for kept tokens."""
    excludes = list(docs) + list(exclude)
    kept, elsewhere = [], []
    for t in tokens:
        rx = re.compile(t.regex)
        other, same = [], False
        for line in _grep(repo, t.label, excludes):
            path, no, rest = line.split(":", 2)
            if not rx.search(rest):
                continue
            if not t.kinds or kind_of(path) in t.kinds:
                same = True
                break
            other.append({"token": t.label, "path": path, "line": int(no), "text": rest.strip()[:200]})
        if not same:
            kept.append(t)
            elsewhere += other
    return kept, elsewhere


def drop_tokens_in_code(repo, tokens, docs, exclude):
    return code_usage(repo, tokens, docs, exclude)[0]


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
