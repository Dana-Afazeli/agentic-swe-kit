# AGENTS.md — working in this repository

For Claude Code sessions that develop this repository. Loaded at session start. There is no
`CLAUDE.md` here and there must never be one: it would silence this file. Budget: 85 lines. A line
stays only if every role needs it and removing it would cause a mistake; what one role needs lives
in that role's skill. Everything above "Project rules" is kit-owned and is merged by a kit update.

## Roles
A role is a skill: the whole procedure of its work, in `.claude/skills/<role>/`. Run yours before
anything else. A rule that lives in a skill is invisible to a session that has not run it.
- Told that a feature or a change is wanted, asked what is next, to plan, or for a brief → run
  `/brief-writer`: wanting something is the start of the flow, and the flow starts with planning.
- Asked to execute, implement or continue a brief or its pull request → run `/implementer NNN`.
- A reviewer is a process the launcher starts (`scripts/review.py`); it runs the `reviewer` skill.
- The skills name no person and no project, so that they are the same text in every repository.
  Here `the maintainer` is the maintainer, and `the base branch` is `main`: a brief's branch is
  `main-NNN-slug`.

## The gate
- `make check` (lint, strict types, import contracts, tests, coverage) must be green before you
  call anything done. The Stop hook runs it whenever code changed and keeps the session from
  stopping while it is red. Fix the cause; do not look for a way round.
- The mutation gate (`make mutate`) covers `src/kitpkg/core/`; CI runs it on the changed modules.

## Architecture — import-linter enforces it (`make arch`)
- `kitpkg.core` holds the decisions and is pure: nothing from `kitpkg.io` or `kitpkg.main`, no I/O
  package, no clock, no `await`. `kitpkg.io` holds the boundaries; `kitpkg.main` wires them.
  The contracts are in `pyproject.toml`; when a new boundary appears, add a contract, not a comment.

## Git, labels and gate files
- Never commit or push to `main`. Never merge a pull request, force-push, or
  `git commit --no-verify`. A branch is brought up to date with `git merge origin/main`.
- Labels are the maintainer's (`brief-approved`, `gates-approved`, `checks-weakened-approved`,
  `scope-approved`): never add, remove or create one. Ask in the PR. `gh api` is for reading, for
  comments and reviews on the PR, and for resolving review threads.
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
- Secrets never enter the repo; runtime state lives outside it.

## Writing for the maintainer
- The maintainer carries no context from your session and decides too many things to remember any
  of them. Write every text they read as if they had never seen this repository: define each term
  at first use, and never point at "finding 3", "round 2" or "the thread" without saying what it is.
- Each decision stands alone: the situation in plain words, the options and what each costs to
  build and to whoever uses the result, your recommendation, the one word to reply.
- A text says what the thing is. How it came to be so belongs in a commit message, a PR comment or
  `docs/FRICTION.md`, never in a brief, a description, a doc or a code comment.

## Where things live
- Reading order: `README.md`. Why we work this way: `docs/kit/PHILOSOPHY.md`. How: `docs/kit/WORKFLOW.md`.
  The harness itself: `docs/kit/HARNESS.md`. This project's deviations from the kit: `docs/DELTAS.md`.
  What we build: `docs/ROADMAP.md`.
- `docs/briefs/` units of work · `docs/decisions/` ADRs (superseded by a new ADR, never edited) ·
  `docs/research/` dated lookups · `docs/FRICTION.md` · `docs/BACKLOG.md`.
- Kit-owned files (`kit.py`, `scripts/`, `.claude/`, `.github/`, `Makefile`, `docs/kit/`,
  `tests/harness/`) change through a kit update or a PR to the kit. Project additions go in
  `project.mk`, `.github/workflows/project.yml`, `docs/DELTAS.md` and "Project rules" below.
- A `Status: living` document must stay true: if your change makes a sentence in one false, fix it
  in the same PR.

## Facts and state
- Facts about Claude Code and the tools come from `docs/kit/research/` and `docs/research/`, not
  from memory. If a fact is missing, look it up, verify it, and write it down there with the date.
- State lives in files and git, never in a conversation: the next session sees only the repository.
- One session per checkout. Never `git switch` in a folder another session is using; clone a copy.
- `make eval` costs money: run it only when a brief says so. No global installs: everything goes
  through `uv` and the lockfile.

## Models and cost
- Name `model` and `effort` on every agent you start; nothing inherits. Default Sonnet at medium;
  Opus at high for one hardest-judgment agent, never a fan-out; the largest models only as reviewers
  of hard or high-stakes work, and stingily. The brief names the reviewers' model and effort.

## Project rules — this project's own; a kit update leaves this section alone
- (none yet)
