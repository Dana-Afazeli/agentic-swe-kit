# Changelog

All notable changes to the kit. The format follows [Keep a Changelog](https://keepachangelog.com/);
versions are git tags (`vX.Y.Z`), and `KIT_VERSION` in `kit.py` names the version a project records
in its `kit.lock`. `kit.py update` prints the sections between a project's version and the one it
moves to.

## Unreleased

### Added
- The harness extracted from the source project (`v2` @ `606515e`, 2026-10-06): `make check`
  (ruff, basedpyright strict, import-linter, pytest with a 90 % branch-coverage floor), `make mutate`
  with its gate script, the Bash guard, the Stop gate, the format hook, `integrity.py`, `review.py`
  and the `review-loop` skill, `plan-reviewer`, the CI workflow (`check`, `mutation`, `secrets`,
  `integrity`, `gate-guard`), the pre-commit configuration, the PR template, `AGENTS.md`.
- A minimal sample package (`core/` pure, `io/`, `main.py`) with one contract, `Core is pure`
  (ADR-0006), and a `prove` marker reserved for the self-proofs.
- `project.mk`, included by the Makefile, for project-owned targets.
- Documents: `README.md`, `docs/kit/PHILOSOPHY.md`, `WORKFLOW.md`, `HARNESS.md`, `SETUP.md`, the
  brief and ADR templates, three research notes carried over, ADR-0001 to ADR-0007.

### Changed from the source project
- The maintainer is a role phrase (`the maintainer`), the base branch is `main`, unit branches are
  `main-NNN-slug`; every knob site carries a `# knob: <name>` comment.
- The deny rules on the base branch are exact spellings: a prefix rule would also refuse pushes to
  `main-*` unit branches.
- `kit.py` is a gate file (guard, CI regex, `ask` rule).
- The marker expression of the gate is `not live and not eval and not prove`, in the Makefile,
  `integrity.py` and mutmut's `pytest_add_cli_args`.
- mutmut's `also_copy` includes `.claude/`: the review launcher reads the code-review protocol
  relative to its own location, and mutmut relocates the scripts.
