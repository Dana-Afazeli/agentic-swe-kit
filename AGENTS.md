# AGENTS.md — working in this repository

For Claude Code sessions that develop this repository. Loaded at session start. There is no
`CLAUDE.md` here and there must never be one: it would silence this file. Budget: 100 lines; a line
stays only if removing it would cause a mistake. Everything above "Project rules" is kit-owned and
is merged by a kit update (`docs/kit/HARNESS.md`, "File ownership").

## The gate
- `make check` (lint, strict types, import contracts, tests, coverage) must be green before you
  call anything done. Paste its output, with the exit code.
- The Stop hook runs it whenever code changed and keeps the session from stopping while it is red,
  or while a test that exists on `main` is gone or skipped. Fix the cause; do not look for a way round.
- `make mutate` when you touch `src/kitpkg/core/`: CI runs it on the changed core modules.

## TDD protocol
1. Write the failing test first, from the brief's acceptance criteria. Run it; show it failing.
2. Write the code. Run `make check`; show it green.
3. Refactor with the tests green.
- Never remove, skip, xfail or weaken a test, and never add an escape-hatch comment (`# noqa`,
  `# type: ignore`, `# pyright: ignore`, `# pragma: no cover`, `# pragma: no mutate`) to get to
  green. CI job `integrity` turns red on either until the maintainer labels the PR
  `checks-weakened-approved`.
- If a test is wrong, or an escape hatch is justified, say so in the PR with the reason and list it
  under "Next steps for the maintainer". A renamed test counts as a removed one: same answer. Once
  the maintainer has added the label, the Stop hook lets you stop.

## Architecture — import-linter enforces it (`make arch`)
- `kitpkg.core` holds the decisions and is pure: nothing from `kitpkg.io` or `kitpkg.main`, no I/O
  package, no clock, no `await`. `kitpkg.io` holds the boundaries; `kitpkg.main` wires them.
  The contracts are in `pyproject.toml`; when a new boundary appears, add a contract, not a comment.

## Work protocol
- One brief = one PR. The brief is already a draft PR on branch `main-NNN-slug`:
  `git fetch && git switch main-NNN-slug`, work there, fill in `.github/pull_request_template.md`,
  `gh pr ready <n>` when done. Read the PR's comments, top-level too, before each push.
- Review: once the PR is ready, run the `review-loop` skill (`uv run python scripts/review.py <n>`).
  It starts both reviewers as processes of their own, on the model and effort the brief names.
- Never commit or push to `main`. Never merge, force-push, or `git commit --no-verify`.
- Labels are the maintainer's (`brief-approved`, `gates-approved`, `checks-weakened-approved`):
  never add, remove or create one. Ask in the PR. `gh api` is for reading, for comments and reviews
  on the PR, and for resolving review threads.
- Gate files — `Makefile`, `pyproject.toml`, `uv.lock`, `.pre-commit-config.yaml`, `.python-version`,
  `.gitignore`, `.betterleaks*`, `kit.py`, `.claude/**`, `.github/**`, `scripts/**` — need
  `gates-approved`, and each push that touches one removes the label again. So does any tool's own
  config file (`pytest.ini`, `ruff.toml`, `pyrightconfig.json`, `setup.cfg`, `GNUmakefile`, …): it
  would override `pyproject.toml` or the `Makefile`. Configuration goes in those two. Change them
  with the editor so the maintainer sees every diff; the Bash guard refuses shell writes to them
  (`uv add|remove|lock|sync` are fine).
- The Bash guard (`scripts/guard_bash.py`) also refuses `rm` on tracked files, `rm -r/-f` outside
  the repository and the temp directory, and `rm` on a path it cannot resolve. Name paths
  literally, from the repository root.
- Stay inside the brief. What else you notice is one line in `docs/BACKLOG.md`, not a change.
- Secrets never enter the repo; runtime state lives outside it.

## Where things live
- Reading order: `README.md`. Why we work this way: `docs/kit/PHILOSOPHY.md`. How: `docs/kit/WORKFLOW.md`.
  The harness itself: `docs/kit/HARNESS.md`. This project's deviations from the kit: `docs/DELTAS.md`.
  What we build: `docs/ROADMAP.md`.
- `docs/briefs/` units of work · `docs/decisions/` ADRs (superseded by a new ADR, never edited) ·
  `docs/research/` dated lookups · `docs/FRICTION.md` · `docs/BACKLOG.md`.
- Kit-owned files (`kit.py`, `scripts/`, `.claude/`, `.github/`, `Makefile`, `docs/kit/`,
  `tests/harness/`, the templates) change through a kit update or a PR to the kit. Project additions
  go in `project.mk`, `.github/workflows/project.yml`, `docs/DELTAS.md` and "Project rules" below.
- A `Status: living` document must stay true: if your change makes a sentence in one false, fix it
  in the same PR.

## Facts and state
- Facts about Claude Code and the tools come from `docs/kit/research/` and `docs/research/`, not
  from memory. If a fact is missing, look it up, verify it, and write it down there with the date.
- State lives in files and git, never in a conversation: the next session sees only the repository.
- One session per checkout. Never `git switch` in a folder another session is using; clone a copy.

## Models and cost
- Name `model` and `effort` on every agent you start; nothing inherits. Default Sonnet at medium;
  Opus at high for one hardest-judgment agent, never a fan-out; the largest models only as reviewers
  of hard or high-stakes work, and stingily. Haiku only for mechanical steps. The brief names the
  reviewers' model and effort; `scripts/review.py` refuses to start one without them.

## Habits
- Friction: when something goes wrong, is slow or confuses, append a line to `docs/FRICTION.md`
  (`date | kind | what happened | what would have caught it | → outcome`).
- Proofs in a PR are verbatim: paste from a saved file into a collapsed block and mark every
  trimmed line with `[…]`. Never retype output.
- CI shell: `|| true` only on a filter such as `grep`, never on the command that gathers the input.
  A failed `git diff` must stop the job, not read as "nothing changed".
- `make eval` costs money: run it only when a brief says so.
- No global installs: everything goes through `uv` and the lockfile. basedpyright stays strict;
  thresholds rise from friction and are never lowered in a feature PR.

## Project rules — this project's own; a kit update leaves this section alone
- (none yet)
