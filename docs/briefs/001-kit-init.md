# Brief 001 — `kit.py init`: one command turns a copy of the kit into a project

**Execute in a fresh Claude Code session started in the development checkout.** You need no context
beyond this file and the repository. This brief is a draft PR on branch `main-001-init`
(`brief-approved`): `git fetch && git switch main-001-init`, work there, and mark the PR ready when
done. Sessions: implementer — the planning session itself, by the maintainer's decision of
2026-10-06 · reviewers: `plan-reviewer` sonnet/medium, `/code-review` opus/xhigh, 3 rounds.

## Context
The seed on `main` is the harness with the kit's placeholder values (`kitpkg`, `main`, `the
maintainer`, `3.13.12`) at sites marked `# knob: <name>`. A project starts by copying the kit
("Use this template") and must get its own names with one command, so that `kit.py update` can
later render the kit the same way and three-way merge (ADR-0001, ADR-0007; HARNESS.md "Knobs",
"File ownership").

## Objective
A stdlib-only `kit.py` with `init` (render in place, seed, remove, lock, re-lock, gate) and
`render --into DIR`, plus the tests that make a missed knob site or an unowned file fail the gate.

## Out of scope — do not do these
- `kit.py update` and `status` (brief 002); `make prove` (brief 003).
- Any change to the gate scripts' behaviour; only their knob constants are read.
- A templating language or a configuration file read at hook time (ADR-0001).

## Inputs
- `docs/kit/HARNESS.md` §9 (ownership) and §10 (knobs); `docs/decisions/0001`, `0007`.
- The knob sites: `grep -rn '# knob:'`; `.claude/settings.json`; `AGENTS.md`; the brief template.

## Interface
`kit.py`: `Answers` (package, base, prefix, maintainer, python; `validate()`), `PLACEHOLDER`,
`category(path) -> str | None`, `is_managed(path)`, `CATEGORIES`, `SEEDS`, `render_text(path, text,
answers)`, `render_path(path, answers)`, `render_tree(src, dst, answers, paths)`, `write_lock`,
`read_lock`, `tracked_files(root)`, `KIT_VERSION`, `LABELS`, `main(argv)`. Command line: `init
--package P [--maintainer M] [--base B] [--branch-prefix X] [--python V] [--labels] [--hooks]
[--no-sync]`, `render … --into DIR`, `labels`.

## Acceptance criteria — concrete cases; write them as failing tests first
1. Every tracked file of the kit falls into one ownership category; every pattern names a file
   (`tests/harness/test_kit.py`).
2. `render_text` rewrites: `.python-version`; `"main"` on `# knob: base` and `# knob: prefix` lines;
   `[main]` on a `# knob: base` line; `3.13`/`3.14` on `# knob: python` lines; the six JSON rule
   shapes; `` `main` ``, `origin/main`, `HEAD:main`, `main-NNN-`, `main-001-`, `main-:*`,
   `main-kit-update` in prose; `the maintainer`/`The maintainer`; `kitpkg`/`KITPKG` as whole
   tokens. It leaves `def main()`, `kitpkgs`, `a maintainer` alone. With the kit's own values it
   changes no tracked file.
3. `init --package demo --maintainer "Ada Lovelace" --no-sync` in a committed copy of the kit:
   `src/demo/` exists and `src/kitpkg/` does not; `CHANGELOG.md`, `LICENSE`, `docs/templates/`,
   the kit's ADRs are gone; `README.md`, `docs/DELTAS.md`, `docs/ROADMAP.md`, `docs/FRICTION.md`,
   `docs/BACKLOG.md`, `docs/kit/LICENSE`, `kit.lock` exist; no `kitpkg`, `KITPKG`, `the
   maintainer` remains outside `uv.lock`; the lock round-trips; `pyproject` names `demo`.
4. `init` refuses (exit 2, a sentence why): an invalid or uppercase or placeholder package name, a
   dirty tree, a project that has a `kit.lock`.
5. `tests/harness/test_knobs.py`: the base-branch, prefix, package and Python sites agree across
   the scripts, `settings.json`, `ci.yml`, `pyproject.toml`, `AGENTS.md`, `project.mk`, the brief
   template — in the kit, and (criterion 3's copy) after `init`.
6. `tests/harness/test_no_leftovers.py`: no token of the source project in the kit's tracked files.
7. `make check` green, with `kit.py` type-checked strictly and the three gate-file lists naming it.

## Proofs to paste into the PR
- `make check` red before `kit.py` exists (the new tests fail), green after, with exit codes.
- `python3 kit.py render --package demo --into /tmp/x` followed by `grep -r kitpkg /tmp/x` empty.

## Output contract
As the template says. Also: `CHANGELOG.md` gets its lines under Unreleased; `docs/ROADMAP.md` ticks
unit 1. Do not merge.

## One caution
The kit's own files must stay valid after rendering with *any* answers: the leftovers test proves
the tokens are gone, not that the rendered project's `make check` is green — that is brief 003's
end-to-end proof. Until then, run `make check` once by hand in a rendered copy.
