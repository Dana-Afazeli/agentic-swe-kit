"""Nothing of the source project remains in the kit: no name, no branch, no library of its domain.

The research notes, the changelog and the decision records cite the source on purpose, and the
lock file and the license are not prose; everything else is scanned.
"""

import kit

from conftest import REPO_ROOT, SOURCE_TOKENS, Leftovers

ROOT = REPO_ROOT
CITES_THE_SOURCE = (
    "docs/kit/research/*",
    "CHANGELOG.md",
    "docs/decisions/*",
    "uv.lock",
    "LICENSE",
    "docs/kit/LICENSE",  # where init puts the kit's license in a project
    "docs/kit/LICENSE",  # where init puts the kit's license in a project
    "tests/harness/conftest.py",  # the token list itself
)


def test_no_source_project_token_remains(leftovers: Leftovers) -> None:
    assert leftovers(ROOT, kit.tracked_files(ROOT), SOURCE_TOKENS, CITES_THE_SOURCE) == []
