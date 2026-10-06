# How work flows

**Status:** living · kit-owned (a kit update merges this file; a project's deviations go in
`docs/DELTAS.md`).

The two-layer loop: an **inner loop** per unit of work and an **outer loop** once a week. Why it is
shaped this way is in `PHILOSOPHY.md`; what each gate does is in `HARNESS.md`.

## 1. Actors and environments

| Actor | Who | Does |
|---|---|---|
| **The maintainer** | the human | Frames units, reads briefs and PRs, adds labels, merges, keeps the friction log honest |
| **Planning session** | a Claude Code session in the development checkout (any model) | Explores read-only, interviews the maintainer, writes the next brief and the decision records |
| **Implementer** | a *fresh* Claude Code session, started with "Execute `docs/briefs/NNN-slug.md`" | Red → green → refactor; opens the PR; runs the review loop; answers the reviews |
| **Reviewers** | two headless Claude Code processes the implementer starts with `scripts/review.py`: `plan-reviewer` and `/code-review`, each on a named model and effort, each in a throwaway clone of the PR's head | Report gaps between brief and diff, and correctness bugs; findings and a record of each run land on the PR |
| **CI** | GitHub Actions on PRs to the base branch | The same `make check`, plus diff coverage, mutation on changed core modules, secret scan, gate-guard, integrity, prove |

**Checkouts.** Separate clones, never git worktrees: worktrees share `.git/hooks` and Claude Code's
local settings with the main checkout, and both bit us. A *development checkout* is where briefs are
executed and where the git hooks are installed; a *deployment checkout* (if the project runs
something) is pinned to the base branch and pulled after merges, never the development checkout, so a
branch switch cannot change what is running. Paths in documents are examples; the repository assumes
no host.

**One session per checkout.** A Claude Code session owns the working tree it was started in. A
second session that needs the repository at the same time — a planning session writing the next
brief while an implementer runs, a documentation fix — clones its own copy (anywhere; deleted
afterwards). Never run `git switch` or `git checkout` in a folder another session is using.

**Models.** Sonnet at medium by default; Opus at high for a single hardest-judgment agent; the
largest models only as reviewers of hard or high-stakes work, stingily; Haiku only for mechanical
steps. Every spawn names `model` and `effort`. `.claude/settings.json` pins built-in subagents to
Sonnet; `.claude/agents/*.md` files set their own. The brief names the implementer's and the
reviewers' model and effort.

## 2. Inner loop — per unit of work

1. **Frame** (maintainer + planning session): pick the next slice from `docs/ROADMAP.md`. If the diff
   cannot be described in two sentences, split it. Skip the rest for typo-class changes.
2. **Explore** read-only (plan mode, or an Explore subagent on Sonnet). Scope it, or it eats the budget.
3. **Brief** (the planning session interviews the maintainer → `docs/briefs/NNN-slug.md`, one screen,
   from the template, pushed as a **draft PR** on branch `<prefix>-NNN-slug`) — **human gate 1: the
   maintainer reads the brief in the PR and adds `brief-approved`.** Comments on the draft are the
   interview's last round.
4. **Implement** (fresh session on the same branch): for each behaviour, failing test first → run it
   and show the failure → code → green → refactor. The Stop hook enforces `make check` and the
   test-integrity check. Mark the PR ready for review when done. Read the PR's comments — top-level
   ones too — before each push and before marking it ready.
5. **Review** (fresh context): the implementer runs the `review-loop` skill. One command,
   `uv run python scripts/review.py <pr> --plan MODEL/EFFORT --code MODEL/EFFORT`, starts
   `plan-reviewer` (conformance) and `/code-review <effort> --comment` (correctness) as processes of
   their own, in clones of the PR's head. Findings and a record of each run land as PR comments. The
   implementer reproduces each finding before changing anything, fixes with a failing test first,
   answers on the PR, resolves only the threads whose fix it saw work, decides whether a reviewer's
   green still stands after the commits since (`--expire`), and runs the command again — for as many
   rounds as the brief or the maintainer says (default 3). It ends with a closing comment: the
   maintainer's next steps, one line per reviewer, thread counts, what nobody checked.
6. **PR** → CI → **human gate 2: the maintainer reads the diff and the walkthrough, merges (squash).**
   Every PR that touches a gate file needs `gates-approved` first; one that weakened a check needs
   `checks-weakened-approved`.
7. **Compound**: anything corrected twice becomes a hook, test, rule or skill *now*; append the
   friction line; tick the unit in the roadmap.

## 3. Briefs

- Numbered `NNN` in execution order; `docs/briefs/000-TEMPLATE.md` is the format. One screen.
  Self-contained: the implementer sees the brief and the repository, never the planning conversation.
- **The brief is a PR.** The planning session creates the unit's branch `<prefix>-NNN-slug`, commits
  only `docs/briefs/NNN-slug.md`, pushes, and opens a draft PR titled after the brief. The maintainer
  approves with `brief-approved`. The implementer session then runs `git fetch && git switch
  <prefix>-NNN-slug` and executes the brief on the same branch; when done it marks the PR ready.
  Brief and implementation land together, so every merged unit carries its own record of intent.
  Nobody writes to the base branch except through this PR.
- **Before writing brief N+1**, the planning session reads: the phase section in `docs/ROADMAP.md`,
  `docs/FRICTION.md`, the previous PR's "out of scope noticed", and the decision records touched
  since. Nothing lives in a session's memory that the next session needs.
- **Acceptance criteria are concrete test cases** — literal inputs, expected outputs, the edge cases
  by name — plus the unit's public interface (module, names, signatures). A criterion a trivial test
  could satisfy is not a criterion. The implementer writes these as failing tests first.
- Proofs are named explicitly (what must be shown failing, what must be shown passing). Run each
  planted proof against the tool once before the brief names it: two proofs in the first project
  were wrong about the tool.
- The brief names model and effort for the implementer and for each reviewer, and a budget for the
  review (rounds; tool calls and minutes as a request).

## 4. Outer loop — weekly, 30 minutes

- Read `docs/FRICTION.md`. Each line becomes a hook, test, rule, skill — or `wontfix`. Build against
  real friction only.
- Prune `AGENTS.md`: for every line, "would removing it cause a mistake?" Move sometimes-relevant
  knowledge into skills.
- Watch review load: PR size and time-to-merge. If PRs pass ~300 lines or merges drag, shrink briefs.
- Update `docs/ROADMAP.md`; write a decision record for any decision made during the week.
- Check whether a kit update is available (`uv run python kit.py status`) and whether any fix made
  here belongs in the kit.

## 5. Documentation lifecycle

Every file under `docs/` opens with a status line, and the status is the contract:
- `Status: living` — kept true; whoever makes a statement in it false fixes it **in the same PR**
  (the PR template asks "which docs did this change make stale?"; `plan-reviewer` checks).
- `Status: snapshot (date)` — never edited; a record. Corrections go in a new file.
- `Status: superseded by <file>` or `Status: deprecated (date) — see <file>` — the old file stays
  one cycle with the pointer at the top, so a model that reaches it is redirected, not misled; the
  outer loop deletes it once nothing links to it.
- Decision records (`docs/decisions/NNNN-slug.md`: Status / Deciders / Context / Decision /
  Consequences) are never edited after acceptance except to add `Superseded by ADR-NNNN`; the new
  record says what changed and why.
- Kit-owned documents (`docs/kit/**`) are updated by `kit.py update`; a project's deviations from
  them go in `docs/DELTAS.md`, never as edits to the kit's text.
- Reading order is pinned in `README.md` and `AGENTS.md`; a moved file leaves a one-line stub for a
  cycle.

## 6. Compounding rules

| If you corrected… | It becomes… |
|---|---|
| a formatting or style thing | a ruff rule or the format hook |
| a boundary violation | an import-linter contract |
| a behaviour the tests missed | a test, and a mutation-gate check that the test bites |
| a repeated instruction to the agent | one line in `AGENTS.md` (then prune something else) |
| a procedure the agent needs sometimes | a skill under `.claude/skills/` |
| a mistake the agent must never make | a permission rule or a hook, not prose |
| a fix that every project would want | a PR to the kit, then `kit.py update` everywhere |
