# ADR-0007 — Every file has one owner, and a kit update is a three-way merge of the kit-owned ones

**Status:** accepted 2026-10-06 · **Deciders:** the maintainer (requirement), the planning session (design)

## Context
The maintainer's requirement: "if I use this in my repo and an update comes out, it should be
updatable easily." An update that has to be applied by hand is not taken; an update that overwrites
a project's additions is not trusted. Both failure modes come from the same cause: a file that both
the kit and the project edit.

## Decision
1. **Four categories, listed in `kit.py` (`MANAGED`) and tested to cover every tracked file:**
   - *kit-owned*: hooks, scripts, CI, settings, Makefile, the harness tests, `AGENTS.md`, `docs/kit/`,
     the templates — copied at `init`, three-way merged at `update`;
   - *mixed*: `pyproject.toml` alone, because the project's dependencies and the kit's tool
     configuration have to share it — merged, with the kit's edits in `[tool.*]` tables;
   - *project-owned*: seeded once at `init` from `docs/templates/` or by renaming the sample, never
     touched again (`README.md`, `project.mk`, `src/`, the project's tests, `docs/DELTAS.md`,
     `docs/ROADMAP.md`, the friction log, the backlog, the project's decisions and research);
   - *kit-only*: the kit's own README, changelog, decisions, friction log, backlog and templates —
     removed by `init`, never present in a project.
2. **A project extends by adding, never by editing a kit-owned file**: `project.mk` (included by
   the Makefile), `.github/workflows/project.yml`, `docs/DELTAS.md`, a marked "Project rules" section
   at the end of `AGENTS.md`, additions to the permission lists in `settings.json`.
3. **`update` is a three-way merge per kit-owned file** with `git merge-file`: base = the kit at the
   project's recorded version rendered with the project's answers, ours = the project's file, theirs
   = the new kit rendered the same way. Clean merges are written; conflicts stay as markers and are
   listed; a file the kit removed is deleted only if the project left it unchanged; a kit-owned file
   the project deleted is listed and not recreated. `kit.lock` records the version and the answers,
   so the base can always be reconstructed.
4. The update runs on a branch and lands as a PR. It touches gate files, so the project's own
   `gate-guard` holds it until the maintainer reads it.

## Consequences
- Updates are mechanical when the rule is kept, and the conflicts show exactly where it was not.
- The kit must keep its own prose out of project-owned files and its own behaviour out of files the
  project is expected to edit; a kit change that moves a file must say so in the changelog.
- `tests/harness/test_manifest.py` fails the kit's gate when a new file has no owner, so the
  categories cannot drift silently.
- The source project predates this rule; homogenizing it onto the kit is on its backlog.
