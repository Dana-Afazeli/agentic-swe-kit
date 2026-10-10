# agentic-swe-kit

A maintained template for building software with coding agents the way we have found it has to be
done to stay in control: **one gate the agent can run, two human decisions per unit of work, and
every rule that matters enforced by a machine rather than asked for in prose.** The kit is the
code form of that philosophy: the gates, the Claude Code hooks, the CI jobs, the role skills, the
review loop, the templates and the documents, proven on a real project and extracted here so that the next project
starts with all of it instead of rebuilding it.

**Status:** living. The kit is itself a working project: its own `make check`, `make prove` and CI
run on every change to it. `CHANGELOG.md` says what changed between versions.

## The philosophy in ten lines

1. **A check the agent can run.** `make check` — lint, strict types, import contracts, tests with a
   branch-coverage floor — is the definition of done. "Looks done" is not a signal.
2. **Two human gates, no more.** The maintainer reads the brief (label `brief-approved`) and reads
   the PR (merge). Everything between is agents and machines.
3. **Enforce, don't advise.** Prose is probabilistic; hooks, permission rules and CI are
   deterministic. The agent never polices its own gates: gate files sit behind `ask` rules and a
   label that expires on every push.
4. **A gate nobody has watched fail is not a gate.** `make prove` plants a defect for each gate and
   shows it go red.
5. **Tests are red first, and they are protected at the outcome.** No test vanishes, no skip or
   escape-hatch comment lands, unless the maintainer labels it. A mutation gate checks that tests bite.
6. **Maker ≠ checker.** Reviews run as separate processes on a named model and effort, in a
   throwaway clone; a finding is a hypothesis the implementer reproduces before changing anything.
7. **Context is a budget.** One fresh session per brief; state lives in files and git; one session
   per checkout; `AGENTS.md` stays under 85 lines: what every role needs, the rest in each role's skill.
8. **Nets, not walls.** Each hook says what it stops and what gets through; CI and the human read
   are the wall.
9. **Compound from real friction.** Every correction becomes a hook, a test, a rule or a skill —
   recorded in `docs/FRICTION.md`, built when it recurs, never from anticipation.
10. **Documents have a status.** Living docs are fixed in the PR that makes them stale; decisions
    are records that are never edited; briefs are pull requests.

The long version, with the reasoning and what the friction taught: **`docs/kit/PHILOSOPHY.md`**.

## Quick start — a new project

1. Click **Use this template** on GitHub (or clone this repo), then clone your new repository.
2. Render the placeholders and seed the project files:
   ```sh
   python3 kit.py init --package myproject --maintainer "Your Name" --labels --hooks
   ```
   `init` renames the sample package, rewrites every knob (base branch, branch prefix, maintainer),
   seeds `README.md`, `project.mk`, `docs/DELTAS.md`, `docs/ROADMAP.md`, the friction log and the
   backlog, writes `kit.lock` (your answers and the kit version), re-locks, and runs `make check`.
   `--labels` creates the four labels with `gh`; `--hooks` installs the git hooks (development
   checkout only).
3. Prove the gates on your machine: `make prove`.
4. Commit, push, and run `/brief-writer` in a fresh Claude Code session: it interviews you and opens
   the first brief as a draft PR. `docs/kit/SETUP.md` has the full checklist, including what to customise and where (never in kit-owned files).

Prerequisites: `git`, [`uv`](https://docs.astral.sh/uv/), `gh`, and the Claude Code CLI. Python is
installed by `uv` from `.python-version`. Nothing is installed globally.

## Taking a kit update

```sh
git switch -c main-kit-update
uv run python kit.py update          # or: --to v0.3.0
```
`update` fetches the kit, renders the old and the new version with your `kit.lock` answers, and
three-way merges every kit-owned file: what the kit said at your version, what it says now, what you
have. Files you never touched update cleanly; your additions survive; a real collision shows as
conflict markers that `update` lists. The result is a PR that touches gate files, so your own
`gate-guard` is red until you read the diff and label it — the kit never bypasses your gates.
`uv run python kit.py status` shows your version, the newest one, and kit-owned files you changed.

## What is in the box

| | |
|---|---|
| `make check` | lint (ruff) · strict types (basedpyright) · import contracts (import-linter) · tests with branch coverage ≥ 90 % |
| `make mutate` | mutation testing on the pure core (mutmut), gated: a surviving mutant fails |
| `make prove` | every gate shown red on a planted defect, then green on the clean tree |
| `.claude/settings.json` | allow/ask/deny rules and three hooks: a Bash guard (PreToolUse), a format hook (PostToolUse), a Stop gate that runs `make check` |
| `scripts/` | the hooks, `integrity.py`, `mutation_gate.py`, and `review.py`, which starts the two PR reviewers as headless processes |
| `.claude/skills/` | the three roles as skills — `brief-writer`, `implementer`, `reviewer` — with numbered rules, their templates (the brief, the page) and `pr.py`; and `review-loop`, which starts the reviewers |
| `.github/workflows/ci.yml` | jobs `check`, `mutation`, `secrets`, `integrity`, `gate-guard`, `prove` |
| `AGENTS.md` | what every session loads here: which skill is its role, the gate, the rules every role shares |
| `docs/kit/` | `PHILOSOPHY.md`, `WORKFLOW.md`, `HARNESS.md`, `SETUP.md` |
| `docs/research/` | the kit's dated, verified research notes; kit-only, a project gets the folder empty |
| templates | the brief and the page (in the skills' `assets/`), the ADR (`docs/decisions/0000-TEMPLATE.md`), and the project files `init` seeds |

## Map of the documents

- `docs/kit/PHILOSOPHY.md` — why each piece exists, and what we learned building it.
- `docs/kit/WORKFLOW.md` — how work flows: actors, the inner loop per unit, briefs as PRs, the
  review loop, the weekly outer loop, the documentation lifecycle, compounding.
- `docs/kit/HARNESS.md` — the specification: toolchain, targets, the gates table, the contract,
  CI, hooks, the file-ownership rule that makes updates painless.
- `docs/kit/SETUP.md` — applying the kit to a project, customising it, taking updates.
- `docs/MAINTAINING.md` — maintaining the kit itself: changes, releases, what a project receives.
- `docs/decisions/` — the kit's own decision records. `docs/FRICTION.md`, `docs/BACKLOG.md` — the
  kit's own friction log and backlog.

## Provenance and license

Extracted on 2026-10-06 from the development branch of a private project (commit `606515e`), where every
gate had been shown to bite and the hooks had been through eight review rounds. The practices
follow *Commons & Diffs* (ed. 2, Sep 2026), a survey of how teams work with coding agents.
MIT license — see `LICENSE`.
