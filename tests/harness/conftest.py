"""Fixtures for the harness's own tests (kit-owned; a kit update may replace this file)."""

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
