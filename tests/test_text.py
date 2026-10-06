"""`truncate`: literal cases first, then the properties that hold for every input."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from kitpkg.core.text import truncate


@pytest.mark.parametrize(
    ("text", "limit", "expected"),
    [
        ("abc", 3, "abc"),  # exactly the limit: untouched
        ("abc", 4, "abc"),  # under the limit: untouched
        ("", 0, ""),  # nothing fits in nothing
        ("abcdef", 4, "abc…"),  # cut, the default marker takes one character
        ("abcdef", 1, "…"),  # room for the marker only
        ("abc", 0, ""),  # no room for anything, not even the marker
    ],
)
def test_default_marker(text: str, limit: int, expected: str) -> None:
    assert truncate(text, limit) == expected


@pytest.mark.parametrize(
    ("text", "limit", "marker", "expected"),
    [
        ("abcdef", 5, "...", "ab..."),  # the marker takes three characters
        ("abcdef", 3, "...", "..."),  # the marker fills the limit exactly
        ("abcdef", 2, "...", ".."),  # a marker longer than the limit is cut too
        ("abcdef", 4, "", "abcd"),  # an empty marker: a plain cut
    ],
)
def test_custom_marker(text: str, limit: int, marker: str, expected: str) -> None:
    assert truncate(text, limit, marker) == expected


def test_negative_limit_is_an_error() -> None:
    with pytest.raises(ValueError, match="limit must be at least 0, got -1"):
        truncate("abc", -1)


@given(text=st.text(max_size=60), limit=st.integers(min_value=0, max_value=40))
def test_never_longer_than_the_limit_and_untouched_when_it_fits(text: str, limit: int) -> None:
    result = truncate(text, limit)
    assert len(result) <= limit
    if len(text) <= limit:
        assert result == text
    else:
        assert result.endswith("…"[:limit])
        assert text.startswith(result[:-1] if limit else "")
