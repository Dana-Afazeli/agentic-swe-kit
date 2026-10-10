# Roadmap — the kit's own

**Status:** living · kit-only (a project gets its own from `docs/templates/ROADMAP.md`). Tick units
as they merge; a change of plan is a new decision record plus an edit here that links it.

## 0. Seed — done 2026-10-06
The harness copied from the source project with the kit's names, the sample package, the documents.
`make check` and `make mutate` green; pushed to `main` directly, the only direct pushes the kit will
ever see.

## 1. `kit.py init` (brief 001) — merged 2026-10-10 (PR 1)
Render the placeholders, seed the project-owned files, write `kit.lock`, re-lock, `make check`;
optional labels and hooks. Tests: `render()` is idempotent and covers every knob site; the manifest
covers every tracked file; `init` into a copy leaves no placeholder behind (`test_no_leftovers`
reused); `make check` is green in the copy (by hand until brief 004 puts it under `prove`).
Exit: a project can be started from the template with one command.

## 2. `kit.py update` and `status` (brief 002) — merged 2026-10-10 (PR 2)
Three-way merge of the kit-owned files between two kit versions rendered with the project's answers
(ADR-0007); the changelog between versions printed; `status` shows the version, the newest tag and
locally modified kit-owned files. Tests against a fake kit repository with two tags: clean merge,
preserved local edit, conflict markers, added file, removed file (unchanged → deleted, changed →
kept and listed), lock rewritten.
Exit: a project on an old kit version takes a newer one with one command and a PR.

## 2a. The Stop hook keeps `make check` only (brief 003) — from friction, merged 2026-10-10 (PR 3)
The vanished-test check leaves the Stop hook (ADR-0008, after the source project's ADR-0010): a hold
the session cannot lift held both reviewers of PR 1 and every fresh project's first session. CI's
`integrity` job holds the merge as before. Exit: a session that removes a test on purpose can stop.

## 2b. Role skills (brief 004) — merged 2026-10-10 (PR 4)
The brief writer, the implementer and the reviewer are each a skill under `.claude/skills/`, with
numbered rules and a script that keeps text and table in step; the PR description is a page the
maintainer can read in five minutes, with the proofs in one comment; the conformance reviewer has no
agent file; `scope-approved` carries the maintainer's yes to work beyond a brief. Adopted from the
source project (its ADR-0011, decisions 9–12); ADR-0009. Exit: a session asked to plan runs
`/brief-writer`, one asked to build runs `/implementer NNN`, and the reviewers read their skill.

## 2c. A project holds no record of the kit (brief 005) — PR open 2026-10-11
The research notes move to `docs/research/` and are kit-only; `docs/briefs/` and `docs/research/`
ship empty; no shipped file names a record id or the path of a record of the kit, and none outside
`tests/` and the lock files carries a date (ADR-0010).
Exit: a rendered project holds none of the kit's records, and a kit-only test keeps it so.

## 3. `make prove` (brief 007)
`tests/prove/`: a session fixture clones the committed tree, each proof plants one defect and shows
its gate red, then the clean tree is green; CI job `prove`.
Exit: HARNESS.md's gates table has a proof per row, and the proofs run on every PR.

## 4. Rehearsal (brief 008)
"Use this template" into a private throwaway repository; `init`; `make check`; `make prove`; a PR
there shows the CI jobs and `gate-guard`; a fresh session there loads `AGENTS.md` and is held by the
hooks; then an `update` across two kit refs, once clean and once with a collision. What breaks is
fixed here; what was learned goes into `SETUP.md`.
Exit: the kit has been used once end to end by someone who was not building it.

## 5. Release `v0.1.0`
`KIT_VERSION`, the changelog, the tag, the GitHub release.

## Later
See `docs/BACKLOG.md`.
