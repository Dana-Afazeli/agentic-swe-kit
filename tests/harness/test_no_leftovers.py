"""Nothing of the source project remains in the kit: no name, no branch, no library of its domain.

Kit-only: it scans the kit's tree for the tokens of the project the kit was extracted from, and a
project named after any of them would fail its own gate. The research notes, the changelog and
the decision records cite the source on purpose, and the lock file and the license are not prose.
"""

import kit

from conftest import REPO_ROOT, Leftovers

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
CITES_THE_SOURCE = (
    "docs/kit/research/*",
    "CHANGELOG.md",
    "docs/decisions/*",
    "uv.lock",
    "LICENSE",
    "tests/harness/test_no_leftovers.py",  # the token list itself
)


def test_no_source_project_token_remains(leftovers: Leftovers) -> None:
    tracked = kit.tracked_files(REPO_ROOT)
    assert leftovers(REPO_ROOT, tracked, SOURCE_TOKENS, CITES_THE_SOURCE) == []
