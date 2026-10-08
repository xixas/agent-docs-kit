from agentdocs import agents


def test_claude_md_line_budget(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("x\n" * 200)
    assert agents.budget(p) == []
    p.write_text("x\n" * 201)
    w = agents.budget(p)
    assert len(w) == 1 and "201 lines" in w[0] and "200" in w[0]


def test_agents_md_byte_budget(tmp_path):
    p = tmp_path / "AGENTS.md"
    p.write_text("a" * 32768)
    assert agents.budget(p) == []
    p.write_text("a" * 32769)
    assert "32769 bytes" in agents.budget(p)[0]


def test_mdc_and_unknown(tmp_path):
    r = tmp_path / "x.mdc"
    r.write_text("l\n" * 501)
    assert "501 lines" in agents.budget(r)[0]
    g = tmp_path / "GEMINI.md"
    g.write_text("l\n" * 9999)
    assert agents.budget(g) == []


def test_imports_expanded_relative_to_file(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/rules.md").write_text("r\n" * 150)
    p = tmp_path / "CLAUDE.md"
    p.write_text("intro\n@docs/rules.md\n" + "x\n" * 60)
    w = agents.budget(p)
    assert len(w) == 1 and "211 lines" in w[0]  # 1 intro + 150 + 60, import line replaced
    assert agents.effective_text(p).count("\n") == 211


def test_import_hops_cycles_and_code_ignored(tmp_path):
    (tmp_path / "a.md").write_text("A\n@b.md\n")
    (tmp_path / "b.md").write_text("B\n@a.md\n")  # cycle
    assert agents.effective_text(tmp_path / "a.md").splitlines() == ["A", "B", "@a.md"]
    for i in range(7):
        (tmp_path / f"h{i}.md").write_text(f"h{i}\n@h{i + 1}.md\n")
    out = agents.effective_text(tmp_path / "h0.md").splitlines()
    assert out[:5] == ["h0", "h1", "h2", "h3", "h4"] and out[5] == "@h5.md"  # 4 hops max
    c = tmp_path / "c.md"
    c.write_text("`@a.md` and\n```\n@a.md\n```\n")
    assert "A" not in agents.effective_text(c).splitlines()


def test_claude_md_also_gets_32k_bytes_check(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text(("a" * 99 + "\n") * 200 + "\n" * 0)
    p.write_text("a" * 40000 + "\n")
    w = agents.budget(p)
    assert len(w) == 1 and "bytes" in w[0]


def test_gemini_info_not_failure(tmp_path):
    g = tmp_path / "GEMINI.md"
    g.write_text("l\n" * 5)
    assert agents.budget(g) == []
    assert "no documented limit" in agents.info(g)[0] and "5 lines" in agents.info(g)[0]
