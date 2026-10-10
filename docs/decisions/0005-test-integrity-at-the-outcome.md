# ADR-0005 — Test integrity is checked at the outcome, not at the edit

**Status:** accepted 2026-10-06 (adopted from the source project's ADR-0008 of 2026-10-03) ·
decision 3 and the second sentence of decision 4 superseded by ADR-0008 (2026-10-08) ·
**Deciders:** the maintainer

## Context
The first design against an implementer that weakens the tests certifying its own code was a
PreToolUse hook that blocks the *edit*: a removed `def test_` or `assert`, an added skip, a `Write`
that shrinks a test file, a shell command that touches `tests/`. It did not survive a closer look:
- Its patterns fire on every legitimate test rewrite — renaming a test, splitting one into two,
  replacing three asserts with one stronger assert, moving a test to another file. In a TDD loop that
  is the refactor step, several times per unit. A guard that blocks the normal case teaches the
  agent to route around it.
- It judges an edit, and an edit is not an outcome. A test deleted in one edit and re-added, better,
  in the next is fine; a test left in place whose body became `assert True` passes every pattern.
- The outcome is already checkable by a layer that cannot be routed around: whatever tool produced
  the change, the test IDs that are gone are gone.

Separately, inline escape hatches (`# noqa`, `# type: ignore`, `# pyright: ignore`, `# pragma: no
cover`, `# pragma: no mutate`) switch a check off for a line without touching a gate file, so nothing
asked the maintainer.

## Decision
1. **No edit-time guard on `tests/`.**
2. **One script, `scripts/integrity.py`, checks the outcome** against the commit where the branch
   left the base, and lists without judging: *vanished tests* (test IDs the gate ran at the base and
   does not run now — both trees collected with the gate's marker expression, from pytest's
   collection hooks, never from what pytest prints); *new skips* (added lines under `tests/`, or in a
   root `conftest.py`, with a skip or xfail marker or call, pytest's or unittest's); *new escape
   hatches* (added lines under `src/`, `scripts/`, `tests/` or the root `conftest.py` with a comment
   that switches a check off).
3. **It runs in two places.** The Stop hook runs the test half after `make check`: a session cannot
   stop while a test from the base is gone, so the agent hears about it in the same session. The CI
   job `integrity` runs all of it and is red until the PR carries the label. Escape hatches are
   checked in CI only: a justified one is legitimate work in progress locally.
4. **One label, `checks-weakened-approved`,** covers a vanished or skipped test and an added escape
   hatch. The Stop hook reads it too (`gh pr view`), and blocks when it cannot read it.
5. `git commit --no-verify` stays denied (permission rule and Bash guard).

## Consequences
- A legitimate rename or removal costs one label and one sentence in the PR.
- Feedback comes at the next stop rather than at the edit, while the session still has the context.
- The hook never parses what a tool prints for people, and never lets its own failure be an exit
  code that means "pass": both hooks catch everything and exit 2.
- Scanned patterns must not match their own source: the test cases live in a data file
  (`tests/harness/fixtures/integrity_cases.toml`), not in a `.py` under `tests/`.
