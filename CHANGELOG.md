# Changelog

All notable changes to the kit. The format follows [Keep a Changelog](https://keepachangelog.com/);
versions are git tags (`vX.Y.Z`), and `KIT_VERSION` in `kit.py` names the version a project records
in its `kit.lock`. `kit.py update` prints the sections between a project's version and the one it
moves to.

## Unreleased

### Added
- `kit.py` with `init` (render the placeholders in place, seed the project-owned files, remove the
  kit-only ones, write `kit.lock`, re-lock, run the gate; `--labels`, `--hooks`, `--no-sync`),
  `render --into DIR` and `labels`. The ownership manifest (`CATEGORIES`, `SEEDS`, `VERBATIM`)
  and `render_text`/`render_path` are what a later `update` reuses (ADR-0001, ADR-0007).
- Tests: every tracked file has one owner and every pattern names a file; `render_text` rewrites
  each knob site and nothing else, and changes nothing with the kit's own values; `init` in a
  committed copy of the kit; every knob's sites agree (`test_knobs.py`); no token of the source
  project remains (`test_no_leftovers.py`).
- `.github/actions/base`: the ref CI compares against, including the first push of a branch, where
  `github.event.before` is forty zeros and the whole history counts from the root commit. The
  seed's first CI run was red on all three push jobs for that reason.
- `kit.py update [--to REF] [--from REF] [--repo URL] [--no-sync]`: the three-way merge of the
  kit-owned and mixed files between the kit version a project has and a newer one, both rendered
  with the project's answers (ADR-0007); conflicts stay as markers and are listed; the lock records
  version, commit and repository; the changelog between the versions is printed. The command
  takes the newer kit's `kit.py` first and re-runs it, so the newer manifest decides; "behind" is
  the history's order (`git merge-base --is-ancestor`), not the version string's; `--to` takes any
  ref, a branch included. `kit.py status [--from REF]`: the version here, the newest tag, the
  kit-owned files that differ from the kit as rendered.
- The Stop hook stands aside in a reviewer's clone: `scripts/review.py` marks its processes with
  `KIT_REVIEWER_CLONE=1`. Both reviewers of PR 1 had run to their time limits, blocked by the
  branch's own renamed tests, with their reports written and unposted.

### Changed in the review of PR 1
- Branch names are rendered in prose, rules and workflows only; in a `.py` file only the `# knob:`
  lines change (a test asserts it for every kit-owned `.py`). Rendering them into test data had
  left a project with another base red on four tests, and on lint for a long name.
- `tests/harness/test_no_leftovers.py` is kit-only: it scans for the source project's names, and a
  project whose maintainer or package carries one would have failed its own gate.
- `.github/*` narrowed to the kit's three paths; a project's own workflow is not managed. `render`
  refuses inside a project.
- `kit.lock` is written with TOML strings (a name outside the BMP could not be read back);
  `validate()` refuses module-shadowing package names, names that are not project names for uv,
  branch names git refuses or the rendered files cannot hold, a prefix under the base's name, and
  quotes in the maintainer's name; a missing `uv`, `make` or `gh` is a sentence, not a traceback;
  `init` stages again after `uv lock` and `ruff format`; `render` refuses the kit itself.
- The reviewer-clone marker is removed from the environment of the harness's own tests (an autouse
  fixture): in a reviewer's `make check` it had turned fourteen Stop-gate tests red.
- `init` and `render` work in a linked worktree (`.git` is a file there); a package named like a
  standard-library module is refused; the base branch goes into `ci.yml` as a quoted YAML string;
  the next steps say the init commit goes straight to the base branch, and why.
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
