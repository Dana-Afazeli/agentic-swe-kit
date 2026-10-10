# Brief NNN — <slug>

**Execute in a fresh Claude Code session started in the development checkout.** You need no context
beyond this file and the repository; do not look for the planning conversation — there is none here,
on purpose. This brief is already a draft PR on branch `main-NNN-<slug>`, approved by the maintainer
(`brief-approved`): `git fetch && git switch main-NNN-<slug>`, work there, and mark the PR ready
when done. Sessions: implementer <model / effort> · reviewers: `plan-reviewer` <model / effort>,
`/code-review` <model / effort>, <N> rounds.

## Context
<Only what the implementer needs. Two to five lines. Link decision records, research notes, the
roadmap section.>

## Objective
<The diff in ≤ 2 sentences. If it does not fit, the brief is two briefs.>

## Out of scope — do not do these
- <explicit non-goals; especially the tempting adjacent work>

## Inputs
- <files to read; references outside the repository, read-only>

## Interface
<module path; public names and signatures the tests will call — precise enough that someone who
never saw the implementation could write the tests>

## Acceptance criteria — concrete cases; write them as failing tests first
1. <given literal input … → expected output …; test name `test_…`>
2. <edge case by name: empty input, limit exactly hit, unicode outside the BMP, …>
3. …
A criterion a trivial test could satisfy is not a criterion. Existing tests may not be removed,
skipped or weakened — the CI job `integrity` catches it (run `scripts/integrity.py` yourself before
`gh pr ready`); if a test is genuinely wrong,
say so in the PR and the maintainer labels it `checks-weakened-approved`.
Gates: `make check` green; `make mutate` shows no surviving mutant in touched `core/` modules (or a
justified `# pragma: no mutate`, which needs the same label).

## Proofs to paste into the PR
- The failing-test output **before** the implementation (red).
- `make check` output **after** (green), with its exit code.
- <any brief-specific proof, e.g. "the hook stays blocked until the fix">
Run each planted proof against the tool once before this brief is approved.

## Output contract
Fill in `.github/pull_request_template.md`: the brief link, **Next steps for the maintainer** (every
action only the maintainer can take, as a checklist, in order), **Walkthrough for the maintainer**
(≤ 15 lines: what changed, why, where it sits, what to read first), the proofs (verbatim, from saved
files, trimmed lines marked `[…]`), out-of-scope things you noticed (→ a line in `docs/BACKLOG.md`; a
line in `docs/FRICTION.md` for anything that went wrong, was slow or confusing), docs this change
made stale and fixed. Read the PR's comments, top-level ones too, before each push and before `gh pr
ready`. Then run the review loop (`uv run python scripts/review.py <n> --plan … --code …`). Do not merge.

## One caution
<the single most likely way this unit goes wrong>
