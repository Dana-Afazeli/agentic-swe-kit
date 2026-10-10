# Brief 003 — the Stop hook keeps `make check`; the vanished-test check is CI's alone

**Execute in a fresh Claude Code session started in the development checkout.** You need no context
beyond this file and the repository. This brief is a draft PR on branch
`main-003-stop-hook-make-check-only` (`brief-approved`): `git fetch && git switch
main-003-stop-hook-make-check-only`, work there, and mark the PR ready when done. Sessions:
implementer — the planning session itself, by the maintainer's standing decision of 2026-10-06 ·
reviewers: `plan-reviewer` sonnet/medium, `/code-review` sonnet/high, 1 round — a port of a change
the source project decided and merged (its ADR-0010, PR #13, 2026-10-07), mostly a removal.

## Context
The Stop hook runs `make check` and then the test half of `scripts/integrity.py`, and blocks the
stop while a test that exists on the base is gone or skipped — until the branch's PR carries
`checks-weakened-approved`, which only the maintainer adds (ADR-0005, decision 3). A hold the held
party cannot lift is a stall, not a gate. The kit paid for it twice before it was a day old: both
reviewers of PR 1 ran to their time limits on a branch with renamed tests (`FRICTION.md`,
2026-10-06 — the launcher's `KIT_REVIEWER_CLONE` marker was the patch), and the init commit of a new
project reads as seventy vanished tests, so a session in a fresh project cannot stop until the
commit is pushed (SETUP.md §2, the open thread on PR 1). The source project met the same wall on its
PR #10 (an implementer sent back about twenty times for a removal its brief asked for; the reviewers
too) and decided ADR-0010: the hook keeps `make check` and nothing else; CI's `integrity` job, which
holds the *merge* for the label, is unchanged.

## Objective
`scripts/stop_gate.py` runs `make check` and nothing else; the vanished-test check, the label and
the `gh` call leave the hook, and every document that said otherwise says what is true now
(ADR-0008 of the kit records the decision and supersedes ADR-0005 decision 3 and the second
sentence of decision 4).

## Out of scope — do not do these
- Any change to `scripts/integrity.py`'s behaviour, to CI's `integrity` job, or to the label: the
  check moves nowhere; it stops being run twice.
- Removing the reviewer-clone exemption (`KIT_REVIEWER_CLONE`): a reviewer still changes nothing,
  and a red `make check` on the PR under review is still the author's, not the reviewer's.
- `make prove` (brief 004), `kit.py` (PRs 1 and 2), the source project.

## Inputs
- `scripts/stop_gate.py`, `tests/harness/test_stop_gate.py`, `scripts/integrity.py` (docstring and
  `--tests-only` help), `.github/workflows/ci.yml` (the `integrity` job's comment), `AGENTS.md`,
  `docs/kit/{SETUP,PHILOSOPHY,HARNESS,WORKFLOW}.md`, `.claude/skills/review-loop/SKILL.md`,
  `docs/briefs/000-TEMPLATE.md`, ADR-0005; the source project's ADR-0010 (read-only).

## Interface
`scripts/stop_gate.py`: `main(run) -> int` and `_gate(run) -> int` as today, minus the integrity
and label steps; `LABEL` removed; `REVIEWER_CLONE_VARIABLE`, `GATED_DIRS`, `GATED_FILES`,
`TAIL_LINES`, `needs_gate`, `find_base`, `changed_paths`, `run_in_root` unchanged.

## Acceptance criteria — concrete cases; write them as failing tests first
1. Code changed, `make check` green → exit 0, nothing on stderr, and the hook ran `make check` and
   **nothing else** — the test's runner raises on any other command
   (`test_a_green_gate_lets_the_session_stop_and_nothing_else_is_run`).
2. Code changed, `make check` red → exit 2 with the last 40 lines, as today
   (`test_red_make_check_blocks_with_the_last_40_lines`, kept).
3. `ci.yml`'s `integrity` job still runs `scripts/integrity.py --base "$BASE"` without
   `--tests-only`, only on `pull_request`, and exits 1 when `checks-weakened-approved` is absent —
   the check the hook gave up cannot leave CI without a test going red
   (`test_ci_still_holds_the_merge_for_a_weakened_test`).
4. The reviewer-clone exemption holds as before (`test_a_reviewers_clone_is_not_gated`, kept).
5. No file in the kit says the Stop hook checks vanished tests or reads the label
   (`grep -rn "tests-only" scripts/stop_gate.py` empty; the prose sites listed under Inputs
   rewritten; `test_gate_lists.py`/`test_knobs.py` unaffected).
The six tests of the label and the integrity step are removed with the behaviour they tested:
**this PR vanishes tests on purpose** and needs `checks-weakened-approved` — CI's job shows the
list, which is the whole point of the change.
Gates: `make check` green; `make mutate` not applicable (no `core/` change).

## Proofs to paste into the PR
- The two new tests red before the change, green after.
- `make check` output after, with its exit code.
- `uv run python scripts/integrity.py --base origin/main-002-update` listing exactly the removed
  stop-gate tests and nothing else.

## Output contract
As `docs/briefs/000-TEMPLATE.md`: the PR template filled in; **Next steps for the maintainer**
include `brief-approved`, `gates-approved` (`scripts/**`, `.github/**` and `AGENTS.md`'s gate
section change), `checks-weakened-approved` (the six removed tests), merge after PRs 1 and 2; the
docs made stale and fixed, listed. Then the review loop, one round. Do not merge.

## One caution
Removing the step is ten lines; the work is the prose. Every sentence that says "the Stop hook and
CI" or "until the label, the hook lets you stop" is now false, and a living doc that stays false
teaches the next session the wrong mechanism. Grep for `Stop hook`, `tests-only`, `lets you stop`
and `checks-weakened` before calling it done.
