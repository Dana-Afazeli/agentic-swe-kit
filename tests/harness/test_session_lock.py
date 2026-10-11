"""The session lock: one session at a time may edit in a tree.

`scripts/session_lock.py` runs as a `SessionStart` hook and as a `PreToolUse` hook on the editing
tools. The lock is a file in the tree's own git directory, holding the session's id and when it was
last seen. It is a net against accidents: a lock that cannot be read counts as free, and a hook
that fails does not stop the work.
"""

import io
import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

import session_lock

# The nearest directory above this file that holds the workflow: the repository root, also when
# mutmut runs the tests from its copy under mutants/ (which has no .github/ or .claude/).
ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / ".github" / "workflows" / "ci.yml").is_file()
)
MINUTE = 60.0
START = 1_000_000.0
FIRST = "session-aaaa"
SECOND = "session-bbbb"


def lock_file(git_dir: Path) -> Path:
    return git_dir / session_lock.LOCK_NAME


def stored(git_dir: Path) -> dict[str, object]:
    return json.loads(lock_file(git_dir).read_text("utf-8"))


def event(name: str, session: str) -> dict[str, object]:
    return {"hook_event_name": name, "session_id": session}


# --- the lock, in a temporary git directory with a clock passed in --------------------------------


def test_the_first_session_takes_the_lock(tmp_path: Path) -> None:
    assert session_lock.take(tmp_path, FIRST, START) is None

    assert stored(tmp_path) == {"session_id": FIRST, "seen": START}


def test_the_same_session_again_moves_the_time(tmp_path: Path) -> None:
    session_lock.take(tmp_path, FIRST, START)

    assert session_lock.take(tmp_path, FIRST, START + 5 * MINUTE) is None

    assert stored(tmp_path) == {"session_id": FIRST, "seen": START + 5 * MINUTE}


def test_another_session_ten_minutes_later_finds_the_lock_held(tmp_path: Path) -> None:
    session_lock.take(tmp_path, FIRST, START)

    holder = session_lock.take(tmp_path, SECOND, START + 10 * MINUTE)

    assert holder == session_lock.Lock(FIRST, START)
    assert stored(tmp_path) == {
        "session_id": FIRST,
        "seen": START,
    }  # the refused one changes nothing


def test_another_session_thirty_one_minutes_later_takes_the_lock(tmp_path: Path) -> None:
    session_lock.take(tmp_path, FIRST, START)

    assert session_lock.take(tmp_path, SECOND, START + 31 * MINUTE) is None

    assert stored(tmp_path)["session_id"] == SECOND


def test_the_stale_limit_is_thirty_minutes_and_is_free_from_the_thirtieth(tmp_path: Path) -> None:
    session_lock.take(tmp_path, FIRST, START)

    assert session_lock.STALE_AFTER_MINUTES == 30
    assert session_lock.take(tmp_path, SECOND, START + 29.9 * MINUTE) is not None
    assert session_lock.take(tmp_path, SECOND, START + 30 * MINUTE) is None


@pytest.mark.parametrize(
    "content",
    [
        "this is not json",
        "",
        "[]",
        '{"session_id": "x"}',
        '{"seen": 5}',
        '{"session_id": 7, "seen": 5}',
        '{"session_id": "", "seen": 5}',
        '{"session_id": "x", "seen": "5"}',
        '{"session_id": "x", "seen": true}',
    ],
)
def test_a_lock_that_cannot_be_read_counts_as_free_and_is_replaced(
    tmp_path: Path, content: str
) -> None:
    lock_file(tmp_path).write_text(content, "utf-8")

    assert session_lock.take(tmp_path, FIRST, START) is None

    assert stored(tmp_path) == {"session_id": FIRST, "seen": START}


def test_a_lock_that_is_not_utf8_counts_as_free(tmp_path: Path) -> None:
    lock_file(tmp_path).write_bytes(b"\xff\xfe\x00")

    assert session_lock.take(tmp_path, FIRST, START) is None


def test_a_lock_last_seen_in_the_future_is_free(tmp_path: Path) -> None:
    """The clock was set back: a holder that is 'seen tomorrow' must not hold the tree for a day."""
    session_lock.take(tmp_path, FIRST, START + 24 * 60 * MINUTE)

    assert session_lock.take(tmp_path, SECOND, START) is None


# --- the two hooks --------------------------------------------------------------------------------


def test_session_start_says_nothing_when_the_session_takes_the_lock(tmp_path: Path) -> None:
    code, out, err = session_lock.decide(event("SessionStart", FIRST), tmp_path, START)

    assert (code, out, err) == (0, "", "")


def test_session_start_in_a_held_tree_adds_context_and_does_not_refuse(tmp_path: Path) -> None:
    session_lock.take(tmp_path, FIRST, START)

    code, out, err = session_lock.decide(
        event("SessionStart", SECOND), tmp_path, START + 10 * MINUTE
    )

    assert code == 0
    assert err == ""
    output = json.loads(out)["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart"
    assert FIRST in output["additionalContext"]
    assert "make tree" in output["additionalContext"]
    assert "10 minutes" in output["additionalContext"]


def test_an_edit_in_a_held_tree_exits_2_naming_the_holder_and_make_tree(tmp_path: Path) -> None:
    session_lock.take(tmp_path, FIRST, START)

    code, out, err = session_lock.decide(event("PreToolUse", SECOND), tmp_path, START + 10 * MINUTE)

    assert code == 2
    assert out == ""
    assert FIRST in err
    assert "make tree" in err


def test_an_edit_by_the_holder_passes_and_refreshes_the_lock(tmp_path: Path) -> None:
    session_lock.decide(event("SessionStart", FIRST), tmp_path, START)

    code, _, _ = session_lock.decide(event("PreToolUse", FIRST), tmp_path, START + 20 * MINUTE)

    assert code == 0
    assert stored(tmp_path)["seen"] == START + 20 * MINUTE
    # twenty minutes after that edit the session is still the holder: the edit refreshed it
    assert session_lock.take(tmp_path, SECOND, START + 40 * MINUTE) is not None


def test_an_edit_in_a_tree_nobody_holds_takes_it(tmp_path: Path) -> None:
    """A session that started before the hook was installed has no SessionStart on record."""
    code, _, _ = session_lock.decide(event("PreToolUse", FIRST), tmp_path, START)

    assert code == 0
    assert stored(tmp_path)["session_id"] == FIRST


def test_another_event_and_an_input_without_a_session_id_are_left_alone(tmp_path: Path) -> None:
    session_lock.take(tmp_path, FIRST, START)

    assert session_lock.decide(event("PostToolUse", SECOND), tmp_path, START) == (0, "", "")
    assert session_lock.decide({"hook_event_name": "PreToolUse"}, tmp_path, START) == (0, "", "")
    assert session_lock.decide(event("PreToolUse", ""), tmp_path, START) == (0, "", "")
    assert stored(tmp_path)["session_id"] == FIRST


# --- the settings that run it ---------------------------------------------------------------------


def commands(entries: object, matcher: str | None) -> list[str]:
    """The commands of the entries of one event that have this matcher (None: no matcher)."""
    found: list[str] = []
    for entry in cast(list[dict[str, object]], entries):
        if entry.get("matcher") != matcher:
            continue
        found += [str(hook["command"]) for hook in cast(list[dict[str, object]], entry["hooks"])]
    return found


def test_the_settings_run_the_lock_at_session_start_and_before_every_tool() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text("utf-8"))
    hooks = settings["hooks"]
    script = '"$CLAUDE_PROJECT_DIR/scripts/session_lock.py"'

    at_start = commands(hooks["SessionStart"], None)
    before_tools = commands(hooks["PreToolUse"], None)  # no matcher: every tool
    before_edits_only = commands(hooks["PreToolUse"], "Edit|Write|NotebookEdit")

    assert len(at_start) == 1
    assert len(before_tools) == 1
    assert before_edits_only == []  # one call per tool, not two for an edit
    assert at_start == before_tools
    assert at_start[0].startswith('uv run --project "$CLAUDE_PROJECT_DIR" python ')
    assert at_start[0].endswith(script)
    assert (ROOT / "scripts" / "session_lock.py").is_file()


# --- in a real repository -------------------------------------------------------------------------


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        [
            *("git", "-C", str(repo)),
            *("-c", "user.name=t", "-c", "user.email=t@example.invalid"),
            *("-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"),
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return done.stdout


def a_repo(path: Path) -> Path:
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    (path / "f.txt").write_text("x\n", "utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-qm", "base")
    return path


def run_hook(
    payload: dict[str, object], project: Path, now: float, monkeypatch: pytest.MonkeyPatch
) -> tuple[int, str]:
    """`main` as Claude Code runs it: JSON on stdin, the project folder in the environment."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    stderr = io.StringIO()
    monkeypatch.setattr("sys.stderr", stderr)
    code = session_lock.main(stdin=json.dumps(payload), clock=lambda: now)
    return code, stderr.getvalue()


def test_the_lock_is_in_the_git_directory_and_not_in_the_working_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = a_repo(tmp_path / "repo")

    code, _ = run_hook(event("SessionStart", FIRST), repo, START, monkeypatch)

    assert code == 0
    assert lock_file(repo / ".git").is_file()
    assert git(repo, "status", "--porcelain", "--untracked-files=all") == ""


def test_a_worktree_has_a_lock_of_its_own(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = a_repo(tmp_path / "repo")
    tree = tmp_path / "repo-009"
    git(repo, "worktree", "add", "-q", "-b", "second-tree", str(tree))

    assert run_hook(event("SessionStart", FIRST), repo, START, monkeypatch)[0] == 0
    assert run_hook(event("SessionStart", SECOND), tree, START, monkeypatch)[0] == 0
    # each tree answers to its own holder: the same two sessions, swapped, are refused
    assert run_hook(event("PreToolUse", SECOND), repo, START + MINUTE, monkeypatch)[0] == 2
    assert run_hook(event("PreToolUse", FIRST), tree, START + MINUTE, monkeypatch)[0] == 2
    assert run_hook(event("PreToolUse", FIRST), repo, START + MINUTE, monkeypatch)[0] == 0
    assert run_hook(event("PreToolUse", SECOND), tree, START + MINUTE, monkeypatch)[0] == 0
    assert lock_file(repo / ".git").is_file()
    assert any(lock_file(path).is_file() for path in (repo / ".git" / "worktrees").iterdir())


def test_the_project_folder_is_the_one_in_the_hook_input_when_the_environment_has_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = a_repo(tmp_path / "repo")
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    code = session_lock.main(
        stdin=json.dumps({**event("SessionStart", FIRST), "cwd": str(repo)}), clock=lambda: START
    )

    assert code == 0
    assert lock_file(repo / ".git").is_file()


def test_outside_a_repository_the_work_is_not_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "plain"
    folder.mkdir()

    code, _ = run_hook(event("PreToolUse", FIRST), folder, START, monkeypatch)

    assert code == 0
    assert list(folder.iterdir()) == []


def test_a_hook_that_fails_does_not_block_and_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exit 1 is not blocking for Claude Code; a lock that cannot be written must not stop the
    editing tools of the one session that works here."""
    repo = a_repo(tmp_path / "repo")
    lock_file(
        repo / ".git"
    ).mkdir()  # a directory where the file goes: it can be neither read nor replaced

    code, err = run_hook(event("PreToolUse", FIRST), repo, START, monkeypatch)

    assert code == 1
    assert "session lock" in err
    assert "not blocking" in err


def test_input_that_is_not_json_does_not_block(monkeypatch: pytest.MonkeyPatch) -> None:
    stderr = io.StringIO()
    monkeypatch.setattr("sys.stderr", stderr)

    code = session_lock.main(stdin="not json at all", clock=lambda: START)

    assert code == 1
    assert "not blocking" in stderr.getvalue()


def test_a_lock_whose_time_is_too_large_for_a_float_counts_as_free(tmp_path: Path) -> None:
    lock_file(tmp_path).write_text('{"session_id": "x", "seen": 1' + "0" * 400 + "}", "utf-8")

    assert session_lock.take(tmp_path, FIRST, START) is None

    assert stored(tmp_path) == {"session_id": FIRST, "seen": START}


# --- a tool that is not an editing tool keeps the holder's lock fresh -----------------------------


def tool_call(session: str, tool: str) -> dict[str, object]:
    return {"hook_event_name": "PreToolUse", "session_id": session, "tool_name": tool}


@pytest.mark.parametrize("tool", ["Bash", "Read", "Grep", "Agent"])
def test_a_tool_that_does_not_edit_moves_the_holders_time_and_is_never_refused(
    tmp_path: Path, tool: str
) -> None:
    session_lock.take(tmp_path, FIRST, START)

    result = session_lock.decide(tool_call(FIRST, tool), tmp_path, START + 25 * MINUTE)

    assert result == (0, "", "")
    assert stored(tmp_path) == {"session_id": FIRST, "seen": START + 25 * MINUTE}


def test_a_holder_that_works_without_editing_keeps_the_tree(tmp_path: Path) -> None:
    """The reviewer's case: A edits at 0 and then works in its shell. B starts at 31 minutes."""
    session_lock.decide(tool_call(FIRST, "Edit"), tmp_path, START)
    for minutes in (10, 20, 30):
        session_lock.decide(tool_call(FIRST, "Bash"), tmp_path, START + minutes * MINUTE)

    start = session_lock.decide(event("SessionStart", SECOND), tmp_path, START + 31 * MINUTE)
    edit = session_lock.decide(tool_call(FIRST, "Edit"), tmp_path, START + 32 * MINUTE)

    assert start[0] == 0
    assert FIRST in json.loads(start[1])["hookSpecificOutput"]["additionalContext"]
    assert edit == (0, "", "")
    assert stored(tmp_path)["session_id"] == FIRST


def test_a_tool_that_does_not_edit_changes_nothing_for_another_session(tmp_path: Path) -> None:
    session_lock.take(tmp_path, FIRST, START)

    result = session_lock.decide(tool_call(SECOND, "Read"), tmp_path, START + 5 * MINUTE)

    assert result == (0, "", "")
    assert stored(tmp_path) == {"session_id": FIRST, "seen": START}


def test_a_tool_that_does_not_edit_does_not_take_a_tree_nobody_holds(tmp_path: Path) -> None:
    result = session_lock.decide(tool_call(FIRST, "Read"), tmp_path, START)

    assert result == (0, "", "")
    assert not lock_file(tmp_path).exists()


@pytest.mark.parametrize("tool", ["Edit", "Write", "NotebookEdit"])
def test_an_editing_tool_is_still_refused_for_another_session(tmp_path: Path, tool: str) -> None:
    session_lock.take(tmp_path, FIRST, START)

    code, _, err = session_lock.decide(tool_call(SECOND, tool), tmp_path, START + 5 * MINUTE)

    assert code == 2
    assert FIRST in err


# --- an edit of a file that is not in the tree is not an edit in the tree -------------------------


def edit_of(session: str, path: Path, tool: str = "Write") -> dict[str, object]:
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return {**tool_call(session, tool), "tool_input": {key: str(path)}}


@pytest.mark.parametrize("tool", ["Write", "Edit", "NotebookEdit"])
def test_a_second_sessions_edit_of_a_file_outside_the_tree_is_not_refused_and_takes_nothing(
    tmp_path: Path, tool: str
) -> None:
    tree, git_dir = tmp_path / "tree", tmp_path / "gitdir"
    tree.mkdir()
    git_dir.mkdir()
    session_lock.take(git_dir, FIRST, START)
    outside = tmp_path / "elsewhere" / "notes.txt"

    result = session_lock.decide(
        edit_of(SECOND, outside, tool), git_dir, START + MINUTE, tree_root=tree
    )

    assert result == (0, "", "")
    assert stored(git_dir) == {"session_id": FIRST, "seen": START}


def test_an_edit_outside_the_tree_does_not_take_a_tree_nobody_holds(tmp_path: Path) -> None:
    tree, git_dir = tmp_path / "tree", tmp_path / "gitdir"
    tree.mkdir()
    git_dir.mkdir()

    result = session_lock.decide(
        edit_of(FIRST, tmp_path / "elsewhere" / "n.txt"), git_dir, START, tree_root=tree
    )

    assert result == (0, "", "")
    assert not lock_file(git_dir).exists()


def test_an_edit_of_a_file_in_the_tree_is_refused_for_a_second_session(tmp_path: Path) -> None:
    tree, git_dir = tmp_path / "tree", tmp_path / "gitdir"
    tree.mkdir()
    git_dir.mkdir()
    session_lock.take(git_dir, FIRST, START)

    code, _, err = session_lock.decide(
        edit_of(SECOND, tree / "src" / "new_file.py"), git_dir, START + MINUTE, tree_root=tree
    )

    assert code == 2
    assert FIRST in err


def test_a_path_that_is_not_absolute_counts_as_in_the_tree(tmp_path: Path) -> None:
    tree, git_dir = tmp_path / "tree", tmp_path / "gitdir"
    tree.mkdir()
    git_dir.mkdir()
    session_lock.take(git_dir, FIRST, START)
    event = {**tool_call(SECOND, "Edit"), "tool_input": {"file_path": "src/a.py"}}

    code, _, _ = session_lock.decide(event, git_dir, START + MINUTE, tree_root=tree)

    assert code == 2


def test_through_main_a_file_outside_the_repository_is_not_refused_and_one_inside_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = a_repo(tmp_path / "repo")
    assert run_hook(event("SessionStart", FIRST), repo, START, monkeypatch)[0] == 0
    outside = {**tool_call(SECOND, "Write"), "tool_input": {"file_path": str(tmp_path / "n.txt")}}
    inside = {**tool_call(SECOND, "Write"), "tool_input": {"file_path": str(repo / "f.txt")}}

    assert run_hook(outside, repo, START + MINUTE, monkeypatch)[0] == 0
    assert run_hook(inside, repo, START + MINUTE, monkeypatch)[0] == 2


# --- what the fifth review round found ------------------------------------------------------------


def test_a_holders_edit_of_a_file_outside_the_tree_keeps_its_time_fresh(tmp_path: Path) -> None:
    """Outside the tree an edit is no edit in it, but it is the holder at work: the time moves."""
    tree, git_dir = tmp_path / "tree", tmp_path / "gitdir"
    tree.mkdir()
    git_dir.mkdir()
    outside = tmp_path / "elsewhere" / "notes.txt"
    session_lock.decide(edit_of(FIRST, tree / "a.py"), git_dir, START, tree_root=tree)
    for minutes in (10, 20, 30):
        session_lock.decide(
            edit_of(FIRST, outside), git_dir, START + minutes * MINUTE, tree_root=tree
        )

    start = session_lock.decide(event("SessionStart", SECOND), git_dir, START + 31 * MINUTE)
    edit = session_lock.decide(
        edit_of(FIRST, tree / "a.py"), git_dir, START + 32 * MINUTE, tree_root=tree
    )

    assert FIRST in json.loads(start[1])["hookSpecificOutput"]["additionalContext"]
    assert edit == (0, "", "")


def test_the_hook_asks_git_once_for_both_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = a_repo(tmp_path / "repo")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(repo))
    real_run = subprocess.run
    calls: list[list[str]] = []

    def counting_run(
        command: list[str], *, capture_output: bool, text: bool, check: bool, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return real_run(
            command, capture_output=capture_output, text=text, check=check, timeout=timeout
        )

    monkeypatch.setattr(subprocess, "run", counting_run)
    payload = {**tool_call(FIRST, "Write"), "tool_input": {"file_path": str(repo / "f.txt")}}

    code = session_lock.main(stdin=json.dumps(payload), clock=lambda: START)

    assert code == 0
    assert len([call for call in calls if call[0] == "git"]) == 1
