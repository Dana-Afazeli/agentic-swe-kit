"""Fixtures for the harness's own tests (kit-owned; a kit update may replace this file)."""

import fnmatch
import os
import re
import subprocess
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

import pytest

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

Leftovers = Callable[[Path, Iterable[str], Iterable[str], Iterable[str]], list[str]]


def _leftovers(
    root: Path, paths: Iterable[str], tokens: Iterable[str], allow: Iterable[str]
) -> list[str]:
    """`path:line: token` for every token that starts a word in a file not covered by `allow`.

    URLs are stripped before the scan: the kit's own address names its owner.
    """
    patterns = [(token, re.compile(r"(?<![\w/])" + re.escape(token))) for token in tokens]
    allowed = tuple(allow)
    found: list[str] = []
    for path in paths:
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in allowed):
            continue
        text = re.sub(r"https?://\S+", "", (root / path).read_text("utf-8", errors="replace"))
        for number, line in enumerate(text.splitlines(), 1):
            found.extend(
                f"{path}:{number}: {token}" for token, pattern in patterns if pattern.search(line)
            )
    return found


@pytest.fixture
def leftovers() -> Leftovers:
    return _leftovers
