# Friction log — the kit's own

**Status:** living · kit-only (a project gets an empty one from `docs/templates/FRICTION.md`).

One line per event: something an agent (or a human) got wrong, something that was slow or costly,
or something that confused. Reviewed in the outer loop: every line becomes a hook, test, rule,
skill — or an explicit `wontfix`. Build against real friction, not anticipated friction.

Format: `date | kind | what happened | what would have caught it | → outcome`
Kinds: `wrong` (shipped something incorrect) · `slow` (bottleneck) · `cost` (money/tokens) ·
`confusing` (misunderstanding between the maintainer and an agent, or in the docs).

| date | kind | what happened | what would have caught it | → outcome |
|---|---|---|---|---|
| 2026-10-06 | wrong | the extracted deny rule `Bash(git push origin main:*)` is a prefix match: with the base branch named `main` and unit branches `main-NNN-slug`, it would have refused every push of a unit branch, while the allow rule for them lost to it (deny wins) | reading each permission rule as a prefix, not as the command it was written for | → exact spellings for the base-branch denies; the Bash guard holds the other spellings; noted in ADR-0003 and HARNESS.md |
| 2026-10-06 | wrong | `make mutate` on the kit failed in mutmut's stats run: `tests/harness/test_review.py` reads the code-review protocol through `review.py`'s `ROOT`, which mutmut relocates under `mutants/`, where `.claude/` did not exist. The source project has the same latent failure; its mutation job skips when no `core/` module changed, so nobody ran it after the launcher landed | running `make mutate` once on every PR that adds a test which reads a file by the script's location | → `also_copy = ["scripts/", ".claude/"]`; a line for the source project's backlog |
| 2026-10-06 | slow | renaming the maintainer to a role phrase lengthened 33 lines past ruff's 100 characters, and several code attributions (a name and a date) read oddly as "The maintainer, 2026-10-06:" | a dry run of the rename against `make lint` before hand-editing; attributions written as "decided <date>" from the start | → rewrapped by hand; attributions read "Decided <date>"; `kit.py init` will have the same problem in reverse when a long name replaces the phrase — its end-to-end test runs `make check` |
