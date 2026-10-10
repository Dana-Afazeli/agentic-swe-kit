# Brief NNN — <slug>

**Run `/implementer NNN` in a fresh Claude Code session started in the development checkout.** You
need no context beyond this file and the repository; do not look for the planning conversation:
there isn't one here, on purpose. This brief lives on branch `<base>-NNN-<slug>` as draft PR #<n>.
Sessions: implementer <model / effort> · review: the `review-loop` skill, `--code <model/effort>`
`--plan <model/effort>` `--rounds <N>` (all named here: the launcher has no default model).
Labels this PR needs from the maintainer: `brief-approved` to start · <`gates-approved` (which
gate files), `checks-weakened-approved` (which test, and why), or "no other">.
Needs merged: <the PRs that have to be on the base branch first, or "nothing">.
Size: about <N> added lines of code and tests. Over about 1,000, this is two briefs.

## Context
<Only what the implementer needs. Two to five lines. Link decision records, research notes, the
roadmap section.>

## Objective
<The diff in ≤ 2 sentences. If it doesn't fit, the brief is two briefs.>

## Out of scope — do not do these
- <explicit non-goals; especially the tempting adjacent work>

## Inputs
- <files to read, each with what it is read for>

## Interface
<module path; public names and signatures the tests will call — precise enough that someone who
never saw the implementation could write the tests>

## Acceptance criteria — concrete cases; write them as failing tests first
1. <given literal input … → expected output …; test name `test_…`>
2. <edge case by name: empty input, limit exactly hit, unicode outside the BMP, …>
3. …
A criterion a trivial test could satisfy is not a criterion. Existing tests may not be removed,
skipped or weakened, and no escape-hatch comment added: CI job `integrity` lists it; if a test is
genuinely wrong, say so in the PR and the maintainer labels it `checks-weakened-approved`.
Gates: `make check` green; `make mutate` shows no surviving mutant in the touched modules that
the mutation gate covers.
Check by hand: <each behaviour that matters and that no test can show, with how the maintainer
can check it (a command, something to look at in the running product); or "nothing">.

## Proofs — in the proofs comment, not in the description
- The failing-test output **before** the implementation (red), and what made it red.
- `make check` output **after** (green), with its exit code.
- A types proof must be one only strict mode rejects (an unannotated parameter), not one every
  mode rejects.
- <any brief-specific proof, e.g. "the hook stays blocked until the fix">

## Cautions — the same in every brief
- **Every wait and every teardown in a test has a bound.** A bound inside a test does not bound
  its teardown: a test whose own wait fails after five seconds can still hang for ever when it
  is torn down.
- **Ask of a red run: "red because of what?"** before you write the fix. The failure message or a
  log line of the unfixed run has to name the cause; a test can be red for a reason that is not
  the missing behaviour.
- **A test of a queue, or of an order, is run once against a deliberately wrong implementation**
  (one that runs a task per message): a test that passes against it tests nothing.
- **Three kinds of mutant no test kills**, so do not write the code that makes them: a flag read
  only for its truth and initialised to a value nothing reads; a bound that a later check
  verifies again; a `join` separator over at most one element. Compute the exact value, and give
  a flag no value to mutate.

## Output contract
The description is the page, set with the implementer skill's `pr.py page`: what this is and
where it sits · **Next steps for the maintainer** (every action only the maintainer can take, in
order, each with what it unblocks) · **Decisions for the maintainer** · **Not proven**; the
reference sections below the line. Proofs go in the proofs comment (`pr.py proofs`).
Out-of-scope things you notice → a line in `docs/BACKLOG.md`; what went wrong, was slow or
confused → a line in `docs/FRICTION.md`. Mark the PR ready (`gh pr ready <n>`) when done. Do not
merge; do not touch labels.

## One caution
<the single most likely way this unit goes wrong>

Brief written in session <id>
