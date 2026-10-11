"""`make tree` and `make untree`: one git worktree per brief, in a sibling folder.

    make tree BRIEF=009            the one branch origin/<prefix>-009-*, in `<checkout>-009`
    make tree BRANCH=<name>        a branch by name (on origin or local), in `<checkout>-<name>`
    make tree NEW=<name>           a new branch from origin/<base> (for a brief writer), same folder
    make untree BRIEF=009|BRANCH=  remove the tree and keep the branch

`<checkout>` is the folder name of the main checkout, the one that holds `.git`. Each `tree` ends
with `uv sync --locked --all-groups` in the new folder and prints where the tree is and the line
that starts a session in it.

Exit 0 done · 2 refused, with a message that says what to do · 1 the tree was made and its sync
failed (the message names the tree and the command to run there).

Refused: not run from the main checkout; a git call that does not answer in 5 minutes; no branch,
or more than one, for the number; the folder exists; a tree that git lists and whose folder is gone
(`git worktree prune`); the branch is held by another tree (git's own refusal); and, for
`untree`, no tree for the number or branch (a tree is found by its branch or by its folder name, so
a detached HEAD is found too), a tree with an uncommitted or untracked file, an ignored file that no
tool makes again (`.env`, a local settings file), or commits that are on no branch of origin.
"""

import argparse
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from subprocess import CompletedProcess

BASE_BRANCH = "main"  # knob: base
BRANCH_PREFIX = "main"  # knob: prefix — a brief's branch is `<prefix>-NNN-slug`
REMOTE = "origin"
SYNC = ("uv", "sync", "--locked", "--all-groups")
# A plain branch name, one path segment: no slash, no space, nothing git or the shell reads as an
# option.
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
NUMBER = re.compile(r"^[0-9]+$")
LISTED_FILES = 10
GIT_TIMEOUT_S = 300  # for one git command; a fetch or a worktree takes seconds
# What `untree` deletes without a word, because a tool makes it again; any other ignored file
# (.env, a local settings file, a log) is somebody's, and is named in a refusal.
REBUILDABLE = frozenset(
    {".venv", ".pytest_cache", ".ruff_cache", ".hypothesis", ".coverage", "coverage.xml"}
    | {"mutants", "dist", ".DS_Store", ".import_linter_cache"}
)

Syncer = Callable[[Path], int]


class Refused(Exception):
    """The command stops with this message; `code` is its exit code."""

    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


def sync_environment(environ: Mapping[str, str]) -> dict[str, str]:
    """The environment of the sync: `make tree` runs under `uv run`, which sets VIRTUAL_ENV to the
    main checkout's `.venv`, and the new folder has an environment of its own."""
    return {name: value for name, value in environ.items() if name != "VIRTUAL_ENV"}


def uv_sync(folder: Path) -> int:
    done = subprocess.run(SYNC, cwd=folder, env=sync_environment(os.environ), check=False)
    return done.returncode


def _git(cwd: Path, *args: str) -> CompletedProcess[str]:
    command = ["git", "-C", str(cwd), *args]
    try:
        return subprocess.run(
            command, capture_output=True, text=True, check=False, timeout=GIT_TIMEOUT_S
        )
    except subprocess.TimeoutExpired:  # a hung fetch is a refusal, not a traceback
        reason = f"fatal: no answer after {GIT_TIMEOUT_S} s from `git {' '.join(args[:2])}`"
        return CompletedProcess(command, 124, stdout="", stderr=reason)


def _reason(done: CompletedProcess[str]) -> str:
    lines = [line for line in (done.stderr or done.stdout).splitlines() if line.strip()]
    for line in lines:  # git's reason, after any progress lines
        if line.startswith(("fatal:", "error:")):
            return line.split(":", 1)[1].strip()
    return lines[-1] if lines else f"exit {done.returncode}"


def _git_ok(cwd: Path, *args: str) -> str:
    done = _git(cwd, *args)
    if done.returncode != 0:
        raise Refused(f"`git {' '.join(args)}` failed: {_reason(done)}")
    return done.stdout.strip()


def _has_ref(cwd: Path, ref: str) -> bool:
    return _git(cwd, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0


# ------------------------------------------------------------------------------ the main checkout


def main_checkout_of(cwd: Path) -> Path:
    """The top of the main checkout, or a refusal: a worktree has a git directory of its own, and
    the common one is the main checkout's."""
    top = _git(cwd, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise Refused(f"{cwd} is not in a git repository: run this from the main checkout")
    git_dir = _git_ok(cwd, "rev-parse", "--absolute-git-dir")
    common = _git_ok(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if Path(git_dir).resolve() != Path(common).resolve():
        raise Refused(
            f"this is a worktree ({cwd}); run it from the main checkout, {Path(common).parent}"
        )
    return Path(top.stdout.strip())


def _fetch(main: Path) -> None:
    # --prune: a branch deleted on origin must not count as a match for a brief number, nor make
    # a commit look pushed.
    done = _git(main, "fetch", "--quiet", "--prune", REMOTE)
    if done.returncode != 0:
        raise Refused(f"could not fetch {REMOTE}: {_reason(done)}")


def _worktrees(main: Path) -> list[tuple[Path, str | None]]:
    """Every worktree of the repository as (folder, branch name or None), the main one first."""
    listed = _git_ok(main, "worktree", "list", "--porcelain")
    found: list[tuple[Path, str | None]] = []
    for block in listed.split("\n\n"):
        folder: Path | None = None
        branch: str | None = None
        for line in block.splitlines():
            if line.startswith("worktree "):
                folder = Path(line.removeprefix("worktree "))
            elif line.startswith("branch refs/heads/"):
                branch = line.removeprefix("branch refs/heads/")
        if folder is not None:
            found.append((folder, branch))
    return found


# ------------------------------------------------------------------------------------ make tree


def _brief_branch(main: Path, number: str) -> str:
    pattern = f"{REMOTE}/{BRANCH_PREFIX}-{number}-*"
    listed = _git_ok(main, "branch", "-r", "--list", pattern)
    found = [
        line.strip().removeprefix(f"{REMOTE}/") for line in listed.splitlines() if line.strip()
    ]
    if not found:
        raise Refused(
            f"no branch matches {pattern}: write the brief first, or name the branch with BRANCH="
        )
    if len(found) > 1:
        raise Refused(f"more than one branch matches {pattern}: {', '.join(found)}; use BRANCH=")
    return found[0]


def make_tree(main: Path, args: argparse.Namespace, sync: Syncer) -> str:
    _fetch(main)
    suffix = args.brief or args.branch or args.new
    branch = _brief_branch(main, args.brief) if args.brief else args.branch or args.new
    local = _has_ref(main, f"refs/heads/{branch}")
    exists = local or _has_ref(main, f"refs/remotes/{REMOTE}/{branch}")
    if args.branch and not exists:
        raise Refused(f"no branch {branch}, locally or on {REMOTE}; NEW={branch} makes one")
    if args.new and exists:
        raise Refused(f"the branch {branch} exists already; BRANCH={branch} makes a tree for it")

    folder = main.parent / f"{main.name}-{suffix}"
    if folder.exists():
        raise Refused(
            f"{folder} exists: take another name, or `make untree` the tree that is there"
        )

    # A tree that git lists and whose folder is gone holds the branch: found here, whatever folder
    # name it had, and not by reading git's refusal.
    for listed, held in _worktrees(main)[1:]:
        if held == branch and not listed.exists():
            raise Refused(
                f"git lists a tree for {branch} at {listed}, but the folder is gone (deleted by "
                "hand): run `git worktree prune`, then try again"
            )

    if args.new:
        add = [
            "worktree",
            "add",
            "--no-track",
            "-b",
            branch,
            str(folder),
            f"{REMOTE}/{BASE_BRANCH}",
        ]
    elif local:
        add = ["worktree", "add", str(folder), branch]
    else:
        add = ["worktree", "add", "--track", "-b", branch, str(folder), f"{REMOTE}/{branch}"]
    done = _git(main, *add)
    if done.returncode != 0:
        raise Refused(f"git could not make the tree: {_reason(done)}")

    notes = _catch_up_with_origin(main, folder, branch) if local else []

    code = sync(folder)
    if code != 0:
        raise Refused(
            f"the tree is at {folder}, but `{' '.join(SYNC)}` failed there (exit {code}): "
            "run it in that folder",
            code=1,
        )
    start = f"start: cd {shlex.quote(str(folder))} && claude"
    return "\n".join([f"tree: {folder}", *notes, start])


def _catch_up_with_origin(main: Path, folder: Path, branch: str) -> list[str]:
    """A branch that `untree` kept can be behind its origin. Behind: fast-forward the tree.
    Ahead or diverged: change nothing, and say so."""
    remote = f"{REMOTE}/{branch}"
    if not _has_ref(main, f"refs/remotes/{remote}"):
        return []
    local = _git_ok(main, "rev-parse", f"refs/heads/{branch}")
    if local == _git_ok(main, "rev-parse", f"refs/remotes/{remote}"):
        return []
    if _git(main, "merge-base", "--is-ancestor", local, f"refs/remotes/{remote}").returncode == 0:
        merged = _git(folder, "merge", "--quiet", "--ff-only", f"refs/remotes/{remote}")
        if merged.returncode != 0:
            return [
                f"note: {branch} is behind {remote} and could not be brought up to it "
                f"({_reason(merged)}); merge it there"
            ]
        return [f"note: {branch} was behind {remote}; the tree is brought up to it"]
    if _git(main, "merge-base", "--is-ancestor", f"refs/remotes/{remote}", local).returncode == 0:
        ahead = _git_ok(main, "rev-list", "--count", f"refs/remotes/{remote}..{local}")
        return [f"note: {branch} is ahead of {remote} by {ahead} commit(s) that are not pushed"]
    return [f"note: {branch} has diverged from {remote}: nothing was changed; merge it there"]


# ---------------------------------------------------------------------------------- make untree


def _rebuildable(path: str) -> bool:
    """An ignored path that a tool makes again: caches, the virtual environment, coverage output."""
    # `.gitignore` names these without a slash, so git ignores them at any depth
    parts = Path(path.rstrip("/")).parts
    return bool(
        parts
        and (
            any(part in REBUILDABLE for part in parts)
            or "__pycache__" in parts
            or parts[-1].endswith(".pyc")
        )
    )


def remove_tree(main: Path, args: argparse.Namespace) -> str:
    _fetch(main)
    # A tree is found by its branch, or by the folder `tree` made for it: a tree whose HEAD was
    # detached has no branch, and `tree` refuses because that folder is there.
    trees = _worktrees(main)[1:]
    if args.brief:
        wanted, what = f"{BRANCH_PREFIX}-{args.brief}-", f"brief {args.brief}"
        by_branch = [(f, b) for f, b in trees if b is not None and b.startswith(wanted)]
        expected = main.parent / f"{main.name}-{args.brief}"
    else:
        what = f"branch {args.branch}"
        by_branch = [(f, b) for f, b in trees if b == args.branch]
        expected = main.parent / f"{main.name}-{args.branch}"
    by_folder = [(f, b) for f, b in trees if f.resolve() == expected.resolve()]
    found = list(dict(by_branch + by_folder).items())
    if not found:
        raise Refused(f"no tree for {what}: `git worktree list` shows the ones there are")
    if len(found) > 1:
        names = ", ".join(str(folder) for folder, _ in found)
        raise Refused(f"more than one tree for {what}: {names}; use BRANCH=")
    folder, branch = found[0]

    if not folder.exists():
        raise Refused(
            f"git lists a tree at {folder}, but the folder is gone (deleted by hand): run "
            "`git worktree prune`, then try again"
        )
    status = _git(folder, "status", "--porcelain", "--untracked-files=all", "--ignored=traditional")
    if status.returncode != 0:
        raise Refused(f"git cannot read the state of {folder}: {_reason(status)}")
    entries = [(line[:2], line[3:]) for line in status.stdout.splitlines()]  # "XY path"
    changes = [path for code, path in entries if code != "!!"]
    if changes:
        shown = ", ".join(changes[:LISTED_FILES]) + (" …" if len(changes) > LISTED_FILES else "")
        raise Refused(
            f"{folder} has changes that are not committed: {shown}; commit and push them, or "
            "take them out, then run it again"
        )
    kept = [path for code, path in entries if code == "!!" and not _rebuildable(path)]
    if kept:
        shown = ", ".join(kept[:LISTED_FILES]) + (" …" if len(kept) > LISTED_FILES else "")
        raise Refused(
            f"{folder} holds files that git ignores and `untree` would delete: {shown}; move "
            "or delete them, then run it again"
        )
    pushed_nowhere = int(
        _git_ok(folder, "rev-list", "--count", "HEAD", "--not", f"--remotes={REMOTE}")
    )
    if pushed_nowhere:
        plural = "" if pushed_nowhere == 1 else "s"
        where = f"of {branch}" if branch else "of a detached HEAD"
        raise Refused(
            f"{pushed_nowhere} commit{plural} {where} are not on {REMOTE}: push them first "
            f"(`git push` from the tree, or put them on a branch)"
        )

    done = _git(main, "worktree", "remove", str(folder))
    if done.returncode != 0:
        raise Refused(f"git could not remove the tree: {_reason(done)}")
    kept_branch = f"the branch {branch} is kept" if branch else "it had no branch checked out"
    return f"untree: removed {folder}; {kept_branch}"


# --------------------------------------------------------------------------------------- the CLI


def _name(kind: str, pattern: re.Pattern[str]) -> Callable[[str], str]:
    def check(value: str) -> str:
        if not pattern.match(value):
            raise argparse.ArgumentTypeError(f"{value!r} is not {kind}")
        return value

    return check


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tree.py", description=(__doc__ or "").split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    number = _name("a brief number (digits)", NUMBER)
    plain = _name("a plain branch name (letters, digits, `.`, `_`, `-`; no `/`)", NAME)
    for command in ("tree", "untree"):
        sub = commands.add_parser(command)
        choice = sub.add_mutually_exclusive_group(required=True)
        choice.add_argument("--brief", type=number, metavar="NNN")
        choice.add_argument("--branch", type=plain, metavar="NAME")
        if command == "tree":
            choice.add_argument("--new", type=plain, metavar="NAME")
    return parser


def main(argv: Sequence[str] | None = None, cwd: Path | None = None, sync: Syncer = uv_sync) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:  # argparse has printed its usage and the reason
        return stop.code if isinstance(stop.code, int) else 2
    try:
        main_checkout = main_checkout_of(cwd or Path.cwd())
        if args.command == "tree":
            message = make_tree(main_checkout, args, sync)
        else:
            message = remove_tree(main_checkout, args)
    except Refused as refusal:
        print(f"tree: {refusal}", file=sys.stderr)
        return refusal.code
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
