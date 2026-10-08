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
