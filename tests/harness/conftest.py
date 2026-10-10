"""Fixtures for the harness's own tests (kit-owned; a kit update may replace this file)."""

import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

import pytest

import stop_gate

# git exports these to the hooks it runs. `make check` is a pre-commit hook, so without this the
# tests that build a throwaway repository would read and write the real repository's index.
GIT_LOCATION_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_PREFIX",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


@pytest.fixture(autouse=True)
def no_inherited_git_location(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in GIT_LOCATION_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def not_in_a_reviewers_clone(monkeypatch: pytest.MonkeyPatch) -> None:
    """The review launcher marks its processes, and the Stop gate stands aside for them. These
    tests run inside such a process too (a reviewer's `make check`), and the gate's tests expect
    the gate; the one test about the marker sets it again for itself."""
    monkeypatch.delenv(stop_gate.REVIEWER_CLONE_VARIABLE, raising=False)


def repo_root(environ: Mapping[str, str], here: Path) -> Path:
    """The repository `here` belongs to, asked of git: mutmut runs the tests from a copy under
    mutants/, where `Path(__file__).parents[2]` would point at the copy.

    The location variables are left out of git's environment: under a git hook, `GIT_DIR` would
    make git answer with the directory it was asked in. Without a repository at all (an export of
    the tree), the answer is the tree's root by layout.
    """
    env = {k: v for k, v in environ.items() if k not in GIT_LOCATION_VARIABLES}
    out = subprocess.run(
        ["git", "-C", str(here), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if out.returncode == 0 and out.stdout.strip():
        return Path(out.stdout.strip())
    return here.parents[1]


REPO_ROOT = repo_root(os.environ, Path(__file__).resolve().parent)
