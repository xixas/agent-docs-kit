from agentdocs import stale
from agentdocs.gitdiff import FileDiff


def fd(added=(), removed=()):
    d = FileDiff()
    d.added = [(i, t) for i, t in enumerate(added, 1)]
    d.removed = list(removed)
    return d


def labels(tokens):
    return sorted(t.label for t in tokens)


def test_python_runtime_normalised_and_diffed():
    d = {"stacks/x.py": fd(added=["runtime=Runtime.PYTHON_3_14"],
                           removed=["runtime=Runtime.PYTHON_3_13"])}
    assert labels(stale.stale_tokens(d)) == ["3.13"]


def test_other_token_kinds():
    d = {"a": fd(removed=[
        "FROM public.ecr.aws/lambda/python3.12",
        "export OLD_API_KEY=1  # see api.old-host.com and x.cloudfront.net",
        "FOO_BAR=1 A_BCD=2 version 4.5.6",
    ])}
    got = labels(stale.stale_tokens(d))
    assert "3.12" in got and "OLD_API_KEY" in got and "FOO_BAR" in got
    assert "api.old-host.com" in got and "x.cloudfront.net" in got
    assert "4.5.6" in got
    assert "A_BCD" not in got            # shorter than 6 chars


def test_token_still_added_elsewhere_is_not_stale():
    d = {"a": fd(removed=["HOST_NAME=1"]), "b": fd(added=["HOST_NAME=2"])}
    assert stale.stale_tokens(d) == []


def test_node_runtime():
    d = {"a": fd(removed=["runtime: nodejs20.x"], added=["runtime: nodejs22.x"])}
    assert labels(stale.stale_tokens(d)) == ["nodejs20"]


def test_tokens_still_in_code_are_dropped(repo):
    repo.commit({"src/a.py": "PY = '3.13'\n", "docs/x.md": "uses 3.13 and 3.12\n",
                 "README.md": "3.12\n"})
    toks = [stale.Token("3.13", stale._plain("3.13").regex),
            stale.Token("3.12", stale._plain("3.12").regex)]
    kept = stale.drop_tokens_in_code(repo.path, toks, ["README.md", "docs/**/*.md"], [])
    assert [t.label for t in kept] == ["3.12"]   # docs mentions don't count as code


def test_exclude_globs_do_not_count_as_code(repo):
    repo.commit({"docs/portal/index.html": "3.12\n"})
    toks = [stale._plain("3.12")]
    assert stale.drop_tokens_in_code(repo.path, toks, ["docs/**/*.md"], ["docs/portal/**"]) == toks


def test_doc_search_whole_token_and_exclude(repo):
    repo.commit({
        "README.md": "Python 3.13 here\nversion 13.13 and 3.131 and 3.13.1\n",
        "docs/a.md": "nothing\nruntime 3.13\n",
        "docs/portal/p.md": "3.13\n",
        "docs/skip.txt": "3.13\n",
    })
    toks = [stale._plain("3.13")]
    hits = stale.find_in_docs(repo.path, toks, ["README.md", "docs/**/*.md"],
                              ["docs/portal/**"], changed={"docs/a.md": "M"})
    got = [(h.path, h.line, h.changed) for h in hits]
    assert got == [("README.md", 1, False), ("docs/a.md", 2, True)]
    assert hits[0].token == "3.13" and "Python 3.13" in hits[0].text


def test_doc_search_finds_version_glued_to_a_word(repo):
    repo.commit({"docs/a.md": "--runtime python3.13 --x\nimage python:3.13-slim\nx 13.13 y\n"})
    hits = stale.find_in_docs(repo.path, [stale._plain("3.13")], ["docs/**/*.md"], [], {})
    assert [h.line for h in hits] == [1, 2]
