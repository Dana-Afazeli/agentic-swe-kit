"""Shared fixtures and hypothesis profiles for the project's tests."""

import os

from hypothesis import settings

# `gate` is what `make check`, the Stop hook and CI run: the same fixed examples every time, so the
# gate gives the same answer everywhere. `search` is run by hand (HYPOTHESIS_PROFILE=search): it
# looks for the input the fixed examples miss, and what it finds becomes a literal case.
settings.register_profile("gate", derandomize=True, deadline=None, database=None, max_examples=200)
settings.register_profile(
    "search", derandomize=False, deadline=None, database=None, max_examples=20000
)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "gate"))
