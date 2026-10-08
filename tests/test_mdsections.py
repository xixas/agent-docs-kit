from agentdocs import mdsections


def test_split_levels_preamble_and_ranges():
    text = "intro\n\n## A\nx\ny\n### sub\nz\n## B\nq\n"
    s = mdsections.split(text)
    assert [x.heading for x in s] == ["", "A", "B"]
    pre, a, b = s
    assert (pre.start, pre.end, pre.lines) == (1, 2, 2)
    assert (a.start, a.end, a.lines, a.level) == (3, 7, 5, 2)
    assert (b.start, b.end) == (8, 9)
    assert a.bytes == len("## A\nx\ny\n### sub\nz\n".encode())


def test_fenced_headings_ignored():
    text = "## A\n```\n## not\n```\n~~~\n## nor\n~~~\n## B\n"
    assert [x.heading for x in mdsections.split(text)] == ["A", "B"]


def test_no_preamble_when_heading_first():
    assert [x.heading for x in mdsections.split("## A\nx\n")] == ["A"]


def test_other_level():
    s = mdsections.split("# T\n## A\n### x\n", level=3)
    assert [(x.heading, x.level) for x in s] == [("", 0), ("x", 3)]


def test_slug_and_duplicates():
    assert mdsections.slug("Hello, World! v1.2 - ok") == "hello-world-v12---ok"
    seen = {}
    assert [mdsections.slug("Dup", seen) for _ in range(3)] == ["dup", "dup-1", "dup-2"]
    assert mdsections.anchors("## Dup\n## Dup\n```\n## x\n```\n") == {"dup", "dup-1"}
