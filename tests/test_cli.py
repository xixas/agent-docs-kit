import json
import subprocess
import sys
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / "skills/docs-check/check_docs_map.py"

MAP = """
docs: ["README.md", "docs/**/*.md"]
rules:
  - id: runtime
    when: {paths: ["infra/*.py"], diff_regex: "PYTHON_"}
    update: ["README.md", "docs/DEPLOY.md"]
    run: "echo regen"
    note: "runtime bump"
"""


def setup(repo):
    repo.commit({"infra/l.py": "r=PYTHON_3_13\n", "README.md": "Python 3.13\n",
                 "docs/DEPLOY.md": "uses python 3.13\n", ".docs-map.yaml": MAP})
    repo.write("infra/l.py", "r=PYTHON_3_14\n")
    repo.write("README.md", "Python 3.14\n")
    return repo.commit()


def cli(repo, *args):
    return subprocess.run([sys.executable, str(CLI), "--repo", str(repo.path), *args],
                          capture_output=True, text=True)


def test_json_output_commit_mode(repo):
    sha = setup(repo)
    p = cli(repo, "--commit", sha, "--json")
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert [r["id"] for r in out["rules"]] == ["runtime"]
    assert out["rules"][0]["targets"] == ["docs/DEPLOY.md"]   # README changed
    assert out["rules"][0]["run"] == "echo regen"
    assert [(h["path"], h["line"], h["token"]) for h in out["stale"]] == [("docs/DEPLOY.md", 1, "3.13")]


def test_text_output_and_worktree_mode(repo):
    setup(repo)
    repo.write("infra/l.py", "r=PYTHON_3_15\n")      # uncommitted
    p = cli(repo, "--base", "main")
    assert p.returncode == 0
    assert "runtime" in p.stdout and "docs/DEPLOY.md" in p.stdout


def test_exit_2_on_bad_config(repo):
    setup(repo)
    repo.write(".docs-map.yaml", MAP.replace("docs/DEPLOY.md", "docs/NOPE.md"))
    p = cli(repo)
    assert p.returncode == 2 and "NOPE.md" in p.stderr


def test_exit_2_on_missing_config(repo):
    repo.commit({"a": "1"})
    assert cli(repo).returncode == 2


def test_exit_0_when_nothing_to_report(repo):
    repo.commit({"a.txt": "1\n", ".docs-map.yaml": "docs: []\n"})
    p = cli(repo, "--json")
    assert p.returncode == 0 and json.loads(p.stdout) == {"rules": [], "stale": []}
