# Roadmap — the kit's own

**Status:** living · kit-only (a project gets its own from `docs/templates/ROADMAP.md`). Tick units
as they merge; a change of plan is a new decision record plus an edit here that links it.

## 0. Seed — done 2026-10-06
The harness copied from the source project with the kit's names, the sample package, the documents.
`make check` and `make mutate` green; pushed to `main` directly, the only direct pushes the kit will
ever see.

## 1. `kit.py init` (brief 001)
Render the placeholders, seed the project-owned files, write `kit.lock`, re-lock, `make check`;
optional labels and hooks. Tests: `render()` is idempotent and covers every knob site; the manifest
covers every tracked file; `init` into a copy leaves no placeholder behind (`test_no_leftovers`
reused); `make check` is green in the copy (under the `prove` marker).
Exit: a project can be started from the template with one command.

## 2. `kit.py update` and `status` (brief 002)
Three-way merge of the kit-owned files between two kit versions rendered with the project's answers
(ADR-0007); the changelog between versions printed; `status` shows the version, the newest tag and
locally modified kit-owned files. Tests against a fake kit repository with two tags: clean merge,
preserved local edit, conflict markers, added file, removed file (unchanged → deleted, changed →
kept and listed), lock rewritten.
Exit: a project on an old kit version takes a newer one with one command and a PR.

## 3. `make prove` (brief 003)
`tests/prove/`: a session fixture clones the committed tree, each proof plants one defect and shows
its gate red, then the clean tree is green; CI job `prove`.
Exit: HARNESS.md's gates table has a proof per row, and the proofs run on every PR.

## 4. Rehearsal (brief 004)
"Use this template" into a private throwaway repository; `init`; `make check`; `make prove`; a PR
there shows the CI jobs and `gate-guard`; a fresh session there loads `AGENTS.md` and is held by the
hooks; then an `update` across two kit refs, once clean and once with a collision. What breaks is
fixed here; what was learned goes into `SETUP.md`.
Exit: the kit has been used once end to end by someone who was not building it.

## 5. Release `v0.1.0`
`KIT_VERSION`, the changelog, the tag, the GitHub release.

## Later
See `docs/BACKLOG.md`.
