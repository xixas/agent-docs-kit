from agentdocs import gitdiff


def test_changed_files_commit_mode(repo):
    repo.commit({"a.txt": "1\n", "b.txt": "1\n", "c.txt": "1\n"})
    repo.write("a.txt", "2\n")
    (repo.path / "b.txt").unlink()
    sha = repo.commit({"new.txt": "x\n"})
    assert gitdiff.changed_files(repo.path, commit=sha) == {
        "a.txt": "M", "b.txt": "D", "new.txt": "A"}


def test_changed_files_worktree_mode_with_untracked(repo):
    repo.commit({"a.txt": "1\n", "b.txt": "1\n"})
    repo.git("checkout", "-q", "-b", "feat")
    repo.commit({"c.txt": "1\n"})            # committed on branch
    repo.write("a.txt", "2\n")               # unstaged modification
    repo.write("staged.txt", "s\n")
    repo.git("add", "staged.txt")            # staged add
    repo.write("untracked.txt", "u\n")       # untracked
    got = gitdiff.changed_files(repo.path, base="main")
    assert got == {"c.txt": "A", "a.txt": "M", "staged.txt": "A", "untracked.txt": "A"}


def test_diff_lines_added_removed(repo):
    repo.commit({"a.txt": "one\ntwo\nthree\n", "gone.txt": "bye\n"})
    repo.write("a.txt", "one\nTWO\nthree\nfour\n")
    (repo.path / "gone.txt").unlink()
    repo.write("new.txt", "n1\nn2\n")
    sha = repo.commit()
    d = gitdiff.diff_lines(repo.path, commit=sha)
    assert d["a.txt"].added == [(2, "TWO"), (4, "four")]
    assert d["a.txt"].removed == ["two"]
    assert d["gone.txt"].removed == ["bye"] and d["gone.txt"].added == []
    assert d["new.txt"].added == [(1, "n1"), (2, "n2")]


def test_diff_lines_includes_untracked(repo):
    repo.commit({"a.txt": "x\n"})
    repo.write("u.txt", "hello\n")
    assert gitdiff.diff_lines(repo.path)["u.txt"].added == [(1, "hello")]
