import pytest

from agentdocs import docsmap

GOOD = """
docs: ["README.md"]
rules:
  - id: r1
    when: {paths: ["src/*.py"]}
    update: ["README.md"]
"""


def cfg(repo, text):
    repo.write(".docs-map.yaml", text)
    return docsmap.load_config(repo.path / ".docs-map.yaml", repo.path)


def test_load_valid(repo):
    repo.write("README.md", "hi")
    c = cfg(repo, GOOD)
    assert c.docs == ["README.md"] and c.exclude == []
    assert c.rules[0].id == "r1" and c.rules[0].update == ["README.md"]


def test_bad_key_is_error(repo):
    repo.write("README.md", "hi")
    with pytest.raises(docsmap.ConfigError, match="unknown"):
        cfg(repo, GOOD.replace("update:", "updates:"))
    with pytest.raises(docsmap.ConfigError, match="unknown"):
        cfg(repo, GOOD.replace("paths:", "path:"))
    with pytest.raises(docsmap.ConfigError, match="unknown"):
        cfg(repo, GOOD + "extra: 1\n")


def test_missing_target_is_error(repo):
    with pytest.raises(docsmap.ConfigError, match="README.md"):
        cfg(repo, GOOD)


def test_bad_regex_and_missing_id(repo):
    repo.write("README.md", "hi")
    with pytest.raises(docsmap.ConfigError, match="diff_regex"):
        cfg(repo, GOOD.replace('{paths: ["src/*.py"]}', '{diff_regex: "("}'))
    with pytest.raises(docsmap.ConfigError, match="id"):
        cfg(repo, GOOD.replace("id: r1", "idd: r1").replace("idd", "id2"))


def mk(**kw):
    base = dict(id="r", update=["docs/A.md"])
    base.update(kw)
    return docsmap.Rule(**base)


def run(rule, files, lines=None):
    c = docsmap.Config(docs=[], exclude=[], rules=[rule])
    return docsmap.evaluate_rules(c, files, lines or {})


def test_paths_trigger_and_glob():
    r = mk(paths=["stacks/*.py", "docs/**/*.md"])
    assert run(r, {"stacks/x.py": "M"})[0].targets == ["docs/A.md"]
    assert run(r, {"stacks/sub/x.py": "M"}) == []   # * does not cross dirs
    assert run(mk(paths=["docs/**/*.md"]), {"docs/a/b/c.md": "M"})  # ** does
    assert run(r, {"other.py": "M"}) == []


def test_target_changed_means_no_candidate():
    r = mk(paths=["stacks/*.py"])
    assert run(r, {"stacks/x.py": "M", "docs/A.md": "M"}) == []


def test_added_trigger_only_on_status_A():
    r = mk(added=["stacks/*_stack.py"])
    assert run(r, {"stacks/new_stack.py": "A"})
    assert run(r, {"stacks/new_stack.py": "M"}) == []


def test_diff_regex_trigger():
    from agentdocs.gitdiff import FileDiff
    fd = FileDiff(); fd.added = [(7, "api.root.add_resource('x')")]
    other = FileDiff(); other.added = [(1, "add_resource in lambda")]
    r = mk(paths=["stacks/*.py"], diff_regex="add_resource|add_method")
    files = {"stacks/a.py": "M", "lambda/b.py": "M"}
    c = run(r, files, {"stacks/a.py": fd, "lambda/b.py": other})
    assert len(c) == 1 and c[0].evidence[-1].startswith("stacks/a.py:7")
    # regex only in a non-matching path, or only in unrelated lines: no fire
    fd2 = FileDiff(); fd2.added = [(1, "nothing")]
    assert run(r, files, {"stacks/a.py": fd2, "lambda/b.py": other}) == []
    # no paths -> all files considered; removed lines count
    fd3 = FileDiff(); fd3.removed = ["HttpRoute(x)"]
    assert run(mk(diff_regex="HttpRoute"), {"z.py": "M"}, {"z.py": fd3})


def test_glob_match_semantics_without_full_match():
    g = docsmap.glob_match
    assert g("docs/a/b/c.md", "docs/**/*.md") and g("docs/c.md", "docs/**/*.md")
    assert not g("docs/a/b.md", "docs/*.md")
    assert g("x/a.py", "x/?.py") and not g("x/ab.py", "x/?.py") and not g("x//.py", "x/?.py")
    assert g("a.lock", "*.lock") and not g("d/a.lock", "*.lock") and g("d/a.lock", "**/*.lock")
    assert g("graphify-out/x/y", "graphify-out/**") and g("a+b.md", "a+b.md") and not g("aXb.md", "a.b.md")
    assert g("requirements-dev.txt", "requirements*.txt")


def test_every_template_loads(tmp_path):
    from pathlib import Path
    import yaml
    tdir = Path(__file__).resolve().parent.parent / "templates"
    templates = sorted(tdir.glob("*.docs-map.yaml"))
    assert templates
    for t in templates:
        for rule in yaml.safe_load(t.read_text()).get("rules", []):
            for target in rule.get("update", []):
                f = tmp_path / target
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("x\n")
        cfg = docsmap.load_config(t, tmp_path)
        assert cfg.rules, t.name
