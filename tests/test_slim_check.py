import json
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / "skills/agent-docs-slim/slim_check.py"


def cli(repo, *args):
    return subprocess.run([sys.executable, str(CLI), *args, "--repo", str(repo.path)],
                          capture_output=True, text=True)


def test_clean_file_exit_0_and_table_sorted(repo):
    repo.commit({"CLAUDE.md": "## Small\nx\n## Big\n" + "line\n" * 10})
    r = cli(repo, "CLAUDE.md")
    assert r.returncode == 0, r.stdout
    assert r.stdout.index("Big") < r.stdout.index("Small")


def test_failures_exit_1_json(repo):
    repo.commit({"CLAUDE.md": "## A\n[x](gone.md)\n" + "l\n" * 250,
                 "README.md": "CLAUDE.md#nope\n"})
    r = cli(repo, "CLAUDE.md", "--json")
    assert r.returncode == 1
    d = json.loads(r.stdout)
    assert d["budget"] and d["dead_links"] and d["broken_inbound"]
    assert d["sections"][0]["heading"] == "A"


def test_missing_file_exits_2_cleanly(repo):
    repo.commit({"a": "1"})
    r = cli(repo, "NOPE.md")
    assert r.returncode == 2 and "Traceback" not in r.stderr and "NOPE.md" in r.stderr
