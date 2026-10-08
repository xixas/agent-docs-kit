"""Git diff parsing: changed files + statuses, added/removed lines."""
import re
import subprocess
from pathlib import Path


_HUNK = re.compile(r"@@ -\S+ \+(\d+)")


def _git(repo, *args, check=True):
    r = subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                       text=True, check=False)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r


def changed_files(repo, commit=None, base="main"):
    """Return {path: status} with status in A/M/D."""
    left, right = _range(repo, commit, base)
    r = _git(repo, "diff", "--name-status", "--no-renames", "-z", *left, *right)
    parts = r.stdout.split("\0")
    out = {}
    for i in range(0, len(parts) - 1, 2):
        out[parts[i + 1]] = parts[i][0]
    if commit is None:
        for path in untracked(repo):
            out.setdefault(path, "A")
    return out


def untracked(repo):
    r = _git(repo, "ls-files", "--others", "--exclude-standard", "-z")
    return [p for p in r.stdout.split("\0") if p]


def _range(repo, commit, base):
    """Return (left_args, right_args) for `git diff`."""
    if commit:
        return [f"{commit}^"], [commit]
    mb = _git(repo, "merge-base", base, "HEAD", check=False)
    rev = mb.stdout.strip() if mb.returncode == 0 and mb.stdout.strip() else "HEAD"
    return [rev], []


class FileDiff:
    def __init__(self):
        self.added = []    # [(lineno_in_new_file, text)]
        self.removed = []  # [text]


def diff_lines(repo, commit=None, base="main"):
    """Return {path: FileDiff} of added/removed lines (binary files skipped)."""
    left, right = _range(repo, commit, base)
    r = _git(repo, "diff", "-U0", "--no-renames", "--no-color", *left, *right)
    out, cur, new_no = {}, None, 0
    for line in r.stdout.split("\n"):
        if line.startswith("diff --git "):
            cur = None
        elif line.startswith("+++ "):
            name = line[4:]
            if name != "/dev/null":
                cur = out.setdefault(name[2:] if name.startswith("b/") else name, FileDiff())
        elif line.startswith("--- "):
            if line[4:] == "/dev/null":
                continue
            name = line[4:]
            path = name[2:] if name.startswith("a/") else name
            out.setdefault(path, FileDiff())
            cur = out[path]  # replaced by +++ line unless file deleted
        elif line.startswith("@@"):
            m = _HUNK.match(line)
            new_no = int(m.group(1)) if m else 0
        elif cur is not None and line.startswith("+"):
            cur.added.append((new_no, line[1:]))
            new_no += 1
        elif cur is not None and line.startswith("-"):
            cur.removed.append(line[1:])
    if commit is None:
        for path in untracked(repo):
            try:
                text = (Path(repo) / path).read_text()
            except (UnicodeDecodeError, OSError):
                continue
            fd = out.setdefault(path, FileDiff())
            fd.added = [(i, t) for i, t in enumerate(text.splitlines(), 1)]
    return out
