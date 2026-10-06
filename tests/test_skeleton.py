"""The skeleton imports cleanly and is fully covered from day one.

The 90 % coverage floor holds on an empty project, so the first real unit starts from green.
"""

import importlib
import importlib.metadata

import pytest

import kitpkg
from kitpkg.main import main

PACKAGES = [
    "kitpkg",
    "kitpkg.core",
    "kitpkg.core.text",
    "kitpkg.io",
    "kitpkg.io.console",
    "kitpkg.main",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports(name: str) -> None:
    assert importlib.import_module(name).__name__ == name


def test_version_matches_installed_metadata() -> None:
    assert kitpkg.__version__ == importlib.metadata.version("kitpkg")


def test_main_says_nothing_to_run_and_returns_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0
    assert capsys.readouterr().out == "kitpkg: nothing to run yet\n"
