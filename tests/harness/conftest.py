"""Fixtures for the harness's own tests (kit-owned; a kit update may replace this file)."""

import fnmatch
import re
import subprocess
from collections.abc import Callable, Iterable
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


# Tokens of the project the kit was extracted from. None may remain in the kit's files, and after
# `kit.py init` none of the kit's own placeholders may remain in a project's (test_no_leftovers.py,
# test_kit.py). URLs are stripped before the scan: the kit's own address names its owner.
SOURCE_TOKENS = (
    "centcom",
    "CENTCOM",
    "Dana",
    "TahamTan",
    "Telegram",
    "aiogram",
    "claude_agent_sdk",
    "v2-",
    "origin/v2",
)

Leftovers = Callable[[Path, Iterable[str], Iterable[str], Iterable[str]], list[str]]


def _leftovers(
    root: Path, paths: Iterable[str], tokens: Iterable[str], allow: Iterable[str]
) -> list[str]:
    """`path:line: token` for every token that starts a word in a file not covered by `allow`."""
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


def _repo_root() -> Path:
    """The repository this test tree belongs to, asked of git: mutmut runs the tests from a copy
    under mutants/, where `Path(__file__).parents[2]` would point at the copy."""
    here = Path(__file__).resolve().parent
    out = subprocess.run(
        ["git", "-C", str(here), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(out.stdout.strip())


REPO_ROOT = _repo_root()
