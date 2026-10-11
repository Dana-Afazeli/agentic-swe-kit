"""`make tree` in a project with names of its own: the two knobs of `scripts/tree.py`, and the file
of the session lock.

The names here are not the kit's. With the base branch and the prefix set to two that no other test
uses, a lookup that still reads the kit's prefix, or a new branch that still starts at the kit's
base, finds nothing or starts in the wrong place.
"""

import json
import subprocess
from pathlib import Path

import pytest
from test_tree import Syncs, git

import session_lock
import tree

BASE = "trunk"
PREFIX = "unit"


@pytest.fixture(autouse=True)
def no_user_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def a_checkout(folder: Path, *branches: str) -> Path:
    """`<folder>/project` on `trunk`, with a bare `origin` that holds `trunk` and each of
    `branches`, made from it."""
    folder.mkdir()
    origin = folder / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", BASE, str(origin)], check=True, timeout=60)
    main = folder / "project"
    main.mkdir()
    git(main, "init", "-q", "-b", BASE)
    (main / "f.txt").write_text("base\n", "utf-8")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "base")
    git(main, "remote", "add", "origin", str(origin))
    git(main, "push", "-q", "-u", "origin", BASE)
    for branch in branches:
        git(main, "push", "-q", "origin", f"{BASE}:refs/heads/{branch}")
    return main


def test_the_prefix_finds_the_brief_and_the_base_starts_a_new_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(tree, "BASE_BRANCH", BASE)
    monkeypatch.setattr(tree, "BRANCH_PREFIX", PREFIX)
    main = a_checkout(tmp_path / "found", f"{PREFIX}-009-x")
    git(main, "commit", "-q", "--allow-empty", "-m", "local only, not on origin")
    syncs = Syncs()

    assert tree.main(["tree", "--brief", "009"], cwd=main, sync=syncs) == 0
    assert tree.main(["tree", "--new", f"{PREFIX}-010-y"], cwd=main, sync=syncs) == 0
    assert tree.main(["untree", "--brief", "009"], cwd=main, sync=syncs) == 0

    found = main.parent / "project-009"
    started = main.parent / f"project-{PREFIX}-010-y"
    assert syncs.folders == [found, started]
    assert not found.exists()  # `untree` found it by the prefix, and kept the branch
    assert f"{PREFIX}-009-x" in git(main, "branch", "--list", f"{PREFIX}-009-x")
    assert git(started, "branch", "--show-current") == f"{PREFIX}-010-y"
    assert git(started, "rev-parse", "HEAD") == git(main, "rev-parse", f"origin/{BASE}")
    assert git(started, "rev-parse", "HEAD") != git(main, "rev-parse", "HEAD")
    capsys.readouterr()

    # the edge: a branch that carries the base's name where the prefix goes is not a brief branch
    other = a_checkout(tmp_path / "edge", f"{BASE}-009-x")

    code = tree.main(["tree", "--brief", "009"], cwd=other, sync=Syncs())

    assert code == 2
    assert f"no branch matches origin/{PREFIX}-009-*" in capsys.readouterr().err
    assert not (other.parent / "project-009").exists()


def test_the_lock_is_a_file_of_the_trees_git_directory_that_leaves_the_tree_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main = a_checkout(tmp_path / "lock")
    made = tmp_path / "lock" / "project-009"
    git(main, "worktree", "add", "-q", "-b", f"{PREFIX}-009-x", str(made))
    edit = {
        "hook_event_name": "PreToolUse",
        "session_id": "session-aaaa",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(made / "f.txt")},
    }
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(made))

    code = session_lock.main(stdin=json.dumps(edit), clock=lambda: 1_000_000.0)

    lock = main / ".git" / "worktrees" / made.name / "kit-session.lock"
    assert code == 0
    assert lock.is_file()
    assert json.loads(lock.read_text("utf-8"))["session_id"] == "session-aaaa"
    assert git(made, "status", "--short") == ""
    assert git(main, "status", "--short") == ""
