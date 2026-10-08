from agentdocs import links


def test_outbound_missing_target(repo):
    repo.commit({"CLAUDE.md": "see [a](docs/a.md) and [b](docs/b.md)\n", "docs/a.md": "# A\n"})
    dead = links.outbound(repo.path, "CLAUDE.md")
    assert [(d["target"], d["line"], d["reason"]) for d in dead] == [("docs/b.md", 1, "missing target")]


def test_outbound_anchor_checks(repo):
    repo.commit({
        "CLAUDE.md": "## Here\n[ok](#here) [bad](#nope) [ok2](docs/a.md#top-part) [bad2](docs/a.md#zzz)\n"
                     "[ext](https://x.io/a.md#q) [mail](mailto:a@b.c) [code](docs/c.py#nope)\n",
        "docs/a.md": "# Top part\n", "docs/c.py": "x=1\n"})
    dead = links.outbound(repo.path, "CLAUDE.md")
    assert [(d["target"], d["reason"]) for d in dead] == [
        ("#nope", "anchor not found"), ("docs/a.md#zzz", "anchor not found")]


def test_outbound_skips_code_fences(repo):
    repo.commit({"CLAUDE.md": "```\n[x](gone.md)\n```\n"})
    assert links.outbound(repo.path, "CLAUDE.md") == []


def test_inbound_broken_anchor(repo):
    repo.commit({
        "CLAUDE.md": "## Kept Section\n",
        "README.md": "see CLAUDE.md#kept-section and CLAUDE.md#gone-section\n",
        "docs/x.md": "[a](../CLAUDE.md#kept-section) [b](../CLAUDE.md#old) [o](../OTHER.md#old)\n",
        "OTHER.md": "# o\n"})
    bad = links.inbound(repo.path, "CLAUDE.md")
    assert [(b["path"], b["line"], b["anchor"]) for b in bad] == [
        ("README.md", 1, "gone-section"), ("docs/x.md", 1, "old")]
