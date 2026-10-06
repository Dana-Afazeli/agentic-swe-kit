# ADR-0001 — A template repository with its own updater, not a library and not copier

**Status:** accepted 2026-10-06 · **Deciders:** the maintainer (interview), the planning session (evidence)

## Context
The harness — about 2,700 lines of hook and gate scripts with 3,300 lines of tests, a CI workflow,
a settings file, a Makefile, templates and documents — was built and hardened on one project. The
maintainer wants every new project to start with all of it, and to keep maintaining it, so a project
that used the kit must be able to take later kit changes without re-doing the setup by hand.

Three shapes were considered:
- **A library**: the Python scripts as an installable package, projects call it from their hooks,
  fixes arrive by bumping a version. It needs a configuration layer now (base branch, gate-file
  lists, maintainer name, mutation scope), a loader import in every hook (a hook that raises exits 1,
  which does not block), and it still leaves `settings.json`, `ci.yml`, the Makefile and the
  documents to be copied and updated some other way.
- **copier**: a generator with an answers file and `copier update` (three-way merge against the
  template's previous version). It puts templating syntax inside every knob-bearing file, so the
  kit stops being a runnable project: no `make check` on itself, no hooks in its own checkout, a
  `{{ }}` clash with the review protocol's placeholders, and one more tool to install.
- **A template repository with a stdlib tool**: the kit is a working project with real default
  values; `kit.py init` renders the placeholders and records the answers; `kit.py update` does what
  copier does — render old and new with the same answers, three-way merge each kit-owned file with
  `git merge-file` — in a few hundred lines we own.

## Decision
1. The kit is a GitHub template repository that is itself a working project under its own gates.
2. `kit.py` (root, stdlib only, a gate file) has `init`, `update` and `status`; `kit.lock` holds the
   answers and the kit version; `KIT_VERSION` and `CHANGELOG.md` version the kit; releases are tags.
3. Knob values are real defaults (`kitpkg`, `main`, `the maintainer`) at sites marked `# knob: <name>`,
   rewritten by one `render()` shared by `init` and `update`; the kit never contains templating syntax.
4. A library extraction stays on the backlog, for the day a second project needs a fix to travel
   faster than an update, or the configuration surface is known from more than one project.

## Consequences
- The kit can be dogfooded: its own `make check`, `make prove` and CI run on every change.
- Updates are a three-way merge, so the file-ownership rule (ADR-0007) has to be strict, or every
  update conflicts.
- The updater is ours to maintain and test; its tests build fake kit versions in a temp repository.
- If projects start editing kit-owned files routinely, or the knob set grows past a handful, revisit:
  that is the signal for the library.
