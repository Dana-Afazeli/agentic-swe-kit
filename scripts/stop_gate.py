"""Stop hook: a session may not stop on a red gate.

Claude Code runs this when a turn is about to end. If code changed — on this branch since it left
the base, or in the working tree — the hook runs `make check`. Exit 2 with the reason on stderr
sends the session back to work; exit 0 lets it stop.

A test that vanished or was skipped does not block the stop: that would hold every session on a
branch that removed a test on purpose, the reviewers' sessions too, until the label
`checks-weakened-approved` is on the PR. That check is the CI job `integrity`'s alone
(`scripts/integrity.py`), which keeps the merge, and not the session, waiting for the maintainer.

There is deliberately no `stop_hook_active` bypass: the hook never reads its input. A bypass
would turn the gate into a one-time nudge. Claude Code itself ends the turn after eight
consecutive blocks, and that is the only way out (docs/kit/HARNESS.md, "Claude Code harness").
"""

import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from subprocess import CompletedProcess

ROOT = Path(__file__).resolve().parents[1]
BASE_BRANCH = "main"  # knob: base
# The branch every PR targets, as (name, the ref that must exist); the remote one is fresher.
BASES = (
    (f"origin/{BASE_BRANCH}", f"refs/remotes/origin/{BASE_BRANCH}"),
    (BASE_BRANCH, f"refs/heads/{BASE_BRANCH}"),
)
# A change to one of these can turn `make check` red: the code, the files that configure the
# gate, and any tool's own config file that would be read instead of them.
GATED_DIRS = ("src/", "tests/", "scripts/")
GATED_FILES = frozenset(
    {
        *("pyproject.toml", "Makefile", "uv.lock", ".python-version"),
        "conftest.py",  # at the root: pytest loads it like the ones under tests/
        # CONFIG_OVERRIDES of guard_bash.py, copied and kept in step by tests/test_gate_lists.py:
        # importing the guard here would let a broken guard_bash.py end this hook with exit 1,
        # which does not block.
        *("GNUmakefile", "makefile", "pytest.toml", ".pytest.toml", "pytest.ini", ".pytest.ini"),
        *("ruff.toml", ".ruff.toml", "pyrightconfig.json", ".coveragerc", ".coveragerc.toml"),
        *(".importlinter", "setup.cfg", "tox.ini", "uv.toml"),
    }
)
TAIL_LINES = 40
# Set by scripts/review.py in the environment of a reviewer process. A reviewer works in a
# throwaway clone of the PR's head and changes nothing; a red gate on the PR under review is the
# author's to pass. Without this marker, the branch's own red would keep both reviewers from ever
# stopping, until the launcher's time limit ended them.
REVIEWER_CLONE_VARIABLE = "KIT_REVIEWER_CLONE"

Runner = Callable[[list[str]], CompletedProcess[str]]


class GitError(RuntimeError):
    """git could not answer, so what changed is unknown."""


def needs_gate(changed: Iterable[str]) -> bool:
    return any(path.startswith(GATED_DIRS) or path in GATED_FILES for path in changed)


def _git(root: Path, *args: str) -> CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )


def find_base(root: Path = ROOT) -> str | None:
    for name, ref in BASES:
        if _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0:
            return name
    return None


def changed_paths(base: str, root: Path = ROOT) -> list[str]:
    """Paths that differ from the base: committed on this branch, staged, modified or untracked."""
    status = _git(root, "status", "--porcelain", "--no-renames", "--untracked-files=all", "-z")
    branch = _git(root, "diff", "--name-only", "--no-renames", "-z", f"{base}...HEAD")
    for result in (status, branch):
        if result.returncode != 0:
            raise GitError(result.stderr.strip())
    working_tree = [entry[3:] for entry in status.stdout.split("\0") if entry]  # "XY path"
    committed = [path for path in branch.stdout.split("\0") if path]
    return sorted({*working_tree, *committed})


def run_in_root(args: list[str]) -> CompletedProcess[str]:
    """Run a command in the repository root, stderr folded into stdout in the order it came."""
    return subprocess.run(
        args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False
    )


def _output(result: CompletedProcess[str]) -> str:
    return (result.stdout or "") + (result.stderr or "")


def main(run: Runner = run_in_root) -> int:
    if os.environ.get(REVIEWER_CLONE_VARIABLE) == "1":
        print("stop gate: a reviewer's clone; the gate is the author's to pass", file=sys.stderr)
        return 0
    try:
        return _gate(run)
    except Exception as error:  # anything at all: a traceback exits 1, and exit 1 does not block
        print(
            f"stop gate: the gate itself failed ({error!r}) — blocking; "
            "repair the hook or the environment (is `make` on the PATH?)",
            file=sys.stderr,
        )
        return 2


def _gate(run: Runner) -> int:
    base = find_base()
    if base is None:
        print(
            f"stop gate: neither origin/{BASE_BRANCH} nor {BASE_BRANCH} exists here, so what "
            f"changed is unknown — fetch the base branch (git fetch origin {BASE_BRANCH})",
            file=sys.stderr,
        )
        return 2
    try:
        changed = changed_paths(base)
    except GitError as error:
        print(f"stop gate: git cannot say what changed against {base}: {error}", file=sys.stderr)
        return 2
    if not needs_gate(changed):
        return 0

    check = run(["make", "check"])
    if check.returncode != 0:
        tail = _output(check).splitlines()[-TAIL_LINES:]
        print(
            f"stop gate: `make check` is red (exit {check.returncode}) — fix it before stopping. "
            f"Its last {len(tail)} lines:",
            *tail,
            sep="\n",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
