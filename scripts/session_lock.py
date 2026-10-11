"""One session per tree: the lock that keeps a second session from editing in a tree.

Claude Code runs this as a `SessionStart` hook and as a `PreToolUse` hook before every tool, with
the hook's JSON on stdin. The lock is a file in the tree's own git directory
(`git rev-parse --git-dir`: each worktree has one, outside its working tree), holding the id of the
session and when it was last seen.

  SessionStart  takes the lock; in a tree another session holds, adds a note to the session's
                context. A SessionStart hook cannot refuse a session.
  PreToolUse    before an editing tool (`Edit`, `Write`, `NotebookEdit`): refreshes the holder's
                lock, and refuses another session's call with exit 2 and a message that names the
                holder and `make tree`. A tree nobody holds is taken by the first such call, so a
                session that started before the hook was installed holds it from its first edit.
                An editing tool that names a file outside the tree (by an absolute path) is not
                an edit in it: no refusal, no taking.
                Before any other tool: refreshes the lock if this session holds it, and does
                nothing otherwise (no refusal, no taking), so a session that works in its shell
                for half an hour keeps its tree.

The lock belongs to the tree the session was started in. A session started elsewhere that edits a
file in a held tree is not stopped by it: the lock does not follow the file to its tree.

A lock not seen for STALE_AFTER_MINUTES is free. A lock that cannot be read (not JSON, not the
right shape, not text) is free and is replaced. This is a net against accidents, not a wall: it
stops the editing tools of a second session, not its shell, and a failure of the hook itself
exits 1, which Claude Code does not treat as a block — a broken lock must not stop all work.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

LOCK_NAME = "kit-session.lock"
STALE_AFTER_MINUTES = 30
HOOK_EVENTS = ("SessionStart", "PreToolUse")
EDIT_TOOLS = frozenset({"Edit", "Write", "NotebookEdit"})


@dataclass(frozen=True)
class Lock:
    session_id: str
    seen: float


def read_lock(git_dir: Path) -> Lock | None:
    """The lock on file, or None when there is none or it cannot be read."""
    try:
        raw = json.loads((git_dir / LOCK_NAME).read_text("utf-8"))
    except (OSError, ValueError):  # no file, a directory, not text, not JSON
        return None
    if not isinstance(raw, dict):
        return None
    fields = cast(dict[str, object], raw)
    session_id, seen = fields.get("session_id"), fields.get("seen")
    if not isinstance(session_id, str) or not session_id:
        return None
    if isinstance(seen, bool) or not isinstance(seen, (int, float)):
        return None
    try:
        return Lock(session_id, float(seen))
    except OverflowError:  # an integer too large for a float: not a time
        return None


def is_held(lock: Lock, now: float) -> bool:
    """Seen less than the limit ago. A lock seen in the future (the clock was set back) is free."""
    return 0 <= now - lock.seen < STALE_AFTER_MINUTES * 60


def write_lock(git_dir: Path, lock: Lock) -> None:
    """Replace the file in one step, so that a second session never reads half of one."""
    descriptor, temporary = tempfile.mkstemp(dir=git_dir, prefix=f"{LOCK_NAME}.")
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"session_id": lock.session_id, "seen": lock.seen}, handle)
    os.replace(temporary, git_dir / LOCK_NAME)


def take(git_dir: Path, session_id: str, now: float) -> Lock | None:
    """Take the lock for `session_id`, or move its time on if it holds it already.

    Returns None when the session holds the lock afterwards, and the other session's lock when
    that session holds it: nothing is written then."""
    current = read_lock(git_dir)
    if current is not None and current.session_id != session_id and is_held(current, now):
        return current
    write_lock(git_dir, Lock(session_id, now))
    return None


def refresh(git_dir: Path, session_id: str, now: float) -> None:
    """Move the time of the lock on if this session holds it. Never takes it, never refuses."""
    current = read_lock(git_dir)
    if current is not None and current.session_id == session_id:
        write_lock(git_dir, Lock(session_id, now))


def edited_path(event: Mapping[str, object]) -> Path | None:
    """The file an editing tool is about to write, when the hook input names it by an absolute
    path (`file_path`, or `notebook_path` for NotebookEdit)."""
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    fields = cast(dict[str, object], tool_input)
    named = fields.get("file_path") or fields.get("notebook_path")
    if isinstance(named, str) and Path(named).is_absolute():
        return Path(named)
    return None


def is_inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def decide(
    event: Mapping[str, object], git_dir: Path, now: float, tree_root: Path | None = None
) -> tuple[int, str, str]:
    """What the hook answers: (exit code, stdout, stderr). `tree_root` is the top of the tree the
    lock belongs to: a file that an editing tool names outside it is not an edit in the tree."""
    session_id, name = event.get("session_id"), event.get("hook_event_name")
    if not isinstance(session_id, str) or not session_id or name not in HOOK_EVENTS:
        return 0, "", ""
    tool = event.get("tool_name")
    if name == "PreToolUse" and isinstance(tool, str) and tool not in EDIT_TOOLS:
        refresh(git_dir, session_id, now)  # not an edit: keep the holder's time fresh, nothing else
        return 0, "", ""
    target = edited_path(event) if name == "PreToolUse" else None
    if target is not None and tree_root is not None and not is_inside(target, tree_root):
        # a file of no tree, or of another one: this lock does not speak for it, but the holder
        # that writes it is at work
        refresh(git_dir, session_id, now)
        return 0, "", ""
    holder = take(git_dir, session_id, now)
    if holder is None:
        return 0, "", ""

    minutes = int((now - holder.seen) // 60)
    held = f"held by session {holder.session_id}, last seen {minutes} minutes ago"
    start = "to work in a tree of your own, run `make tree BRIEF=NNN` in the main checkout"
    if name == "SessionStart":
        context = (
            f"This tree is {held}. Edits made here are refused while it holds the lock; {start} "
            f"and start a session there, or wait until it has been quiet for "
            f"{STALE_AFTER_MINUTES} minutes."
        )
        output = {
            "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}
        }
        return 0, json.dumps(output), ""
    message = (
        f"session lock: this tree is {held}. One session works in a tree; {start} "
        f"(or `make tree NEW=<name>`), or wait until that session has been quiet for "
        f"{STALE_AFTER_MINUTES} minutes."
    )
    return 2, "", message


def git_paths_of(project: str) -> tuple[Path, Path] | None:
    """The tree's own git directory and the top of its working tree, from one git call; None
    when `project` is not in a working tree."""
    done = subprocess.run(
        ["git", "-C", project, "rev-parse", "--absolute-git-dir", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    if done.returncode != 0 or len(lines) != 2:
        return None
    return Path(lines[0]), Path(lines[1])


def main(stdin: str | None = None, clock: Callable[[], float] = time.time) -> int:
    try:
        event = json.loads(sys.stdin.read() if stdin is None else stdin)
        if not isinstance(event, dict):
            raise ValueError("the hook input is not a JSON object")
        fields = cast(dict[str, object], event)
        project = os.environ.get("CLAUDE_PROJECT_DIR") or fields.get("cwd")
        paths = git_paths_of(project) if isinstance(project, str) and project else None
        if paths is None:  # not a repository: there is nothing to hold
            return 0
        git_dir, tree_root = paths
        code, out, err = decide(fields, git_dir, clock(), tree_root)
    except Exception as error:  # anything at all: a hook that cannot start does not block either
        print(f"session lock: failed ({error!r}) — not blocking", file=sys.stderr)
        return 1
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
