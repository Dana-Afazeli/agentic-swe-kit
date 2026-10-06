# Why the kit is the way it is

**Status:** living · kit-owned (a kit update merges this file; a project's deviations go in
`docs/DELTAS.md`).

This document is the reasoning behind every file in the kit. `WORKFLOW.md` says how work flows,
`HARNESS.md` what each gate and hook does, `SETUP.md` how to apply the kit. This one says *why*,
and what the friction taught while the harness was built on a real project in September and
October 2026. If a rule here seems arbitrary, the friction log of that project probably holds the
incident that produced it.

## 1. Where this comes from

The practices follow *Commons & Diffs* (ed. 2, Sep 2026), a survey of how teams were actually
working with coding agents after two years of trying. Its finding was convergence: every school
that worked had a check the agent can run, a short instructions file, a human gate at the pull
request, a separation between the model that writes and the one that checks, and a habit of turning
corrections into machine-enforced rules. The kit is that convergence for **one person with
agents**: it deliberately stops short of fleets, spec-first ceremony and risk zoning. A one-person
project earns those later, from friction, or never.

Two things are true of language models that the whole design rests on. An instruction in prose is
**probabilistic**: it is followed most of the time, less often under pressure, and least when
following it means admitting the work is not done. A hook, a permission rule or a CI job is
**deterministic**: it runs every time, and it does not care how the session feels about it. The kit
puts every rule that matters in the second category and keeps the first category short.

## 2. The principles, and how each shows up

| Principle | What it buys | Where it lives in the kit |
|---|---|---|
| A check the agent can run | "Looks done" stops being the only signal | `make check`: lint, strict types, import contracts, tests with a branch-coverage floor; one command, deterministic, proven to fail |
| Short instructions file | Context spent only on what the code cannot say | `AGENTS.md` ≤ 100 lines, pruned weekly; no nested files until friction demands one |
| Maker ≠ checker | The model that wrote the code does not grade it | `scripts/review.py` starts the reviewers as separate processes, in a throwaway clone, on a named model |
| Human gate at the PR | The maintainer reads every diff while no verifier has earned trust | One PR per unit, a walkthrough written for the maintainer, the maintainer merges |
| Context as a budget | No kitchen-sink sessions | A fresh session per brief; state lives in files and git; one session per checkout |
| Someone can explain the code | The maintainer owns the design, not only the output | A walkthrough in every PR; small units; a decision record for every decision |
| Enforce, don't advise | Corrections become machine checks | Hooks, import contracts, the coverage floor, the mutation gate, CI, permission rules |
| Compound | Each unit leaves the repo easier for the next agent | The friction log, the compounding step of the inner loop, the skills folder |

## 3. Two human gates, and only two

The maintainer decides twice per unit of work: **the brief** (is this the right thing to build, and
is it specified as tests?) and **the merge** (does the diff do what the brief said, and can I explain
it?). Everything between — implementation, review, fixing, answering review comments — is agents
and machines. The labels make the two gates visible and machine-checkable: `brief-approved` on the
draft PR releases the implementer; the merge is the maintainer's alone (`gh pr merge` always asks).

Why not more gates? Each one costs the maintainer's attention, which is the scarcest resource in a
one-person project; and every gate the agent can satisfy by itself is not a gate. Why not fewer? Because
no verifier has yet earned the trust to merge unread. The report's rule is to add risk zoning
(green changes merge on green CI) only once the verifiers have a track record — the kit has a
backlog item for it and nothing else.

## 4. Enforce, don't advise — and the agent never polices its own gates

Everything that can be a hook, a permission rule or a CI job is one. Three consequences follow.

**Gate files sit behind an `ask` rule and a label.** The files that define the gate — `Makefile`,
`pyproject.toml`, the hooks, the CI workflow, the settings file, every tool's own config file that
could override them — can only be edited through the editor (so the maintainer sees the diff) and
turn the CI job `gate-guard` red until the maintainer adds `gates-approved`. The approval covers
what was read: a later push that touches a gate file removes the label. Without this, the shortest
path from a red gate to a green one is to edit the gate.

**Nets, not walls.** The Bash guard refuses the habitual spellings of the commands that must not
run: `rm` on a tracked file, a shell write to a gate file, `git commit --no-verify`, a force-push, a
push that lands on the base branch, a change of labels. It is read in one pass the way the shell
reads it, and it is still not a wall: `find -delete`, a script that calls `gh`, a variable that
expands to a command's name all get through. The texts say so, by name. Twice during the build, a
text called a net a wall, and twice the next review round broke it in a sandbox. The rule since:
before writing "cannot", try one spelling that does not go through the mechanism the claim rests
on. **CI and the maintainer's read are the wall**; the guard exists to stop the habit early and to
make the agent say so when it is refused.

**The hook fails closed.** A hook that raises an exception exits with code 1, and Claude Code treats
1 as "not a block". Both hooks catch everything and exit 2. A gate that cannot read the labels it
depends on blocks. A CI step whose `git diff` fails must stop the job, never read as "nothing
changed" (`|| true` only on a filter, never on the command that gathers the input). Two steps of
the first CI workflow failed open exactly this way, and a review caught them by running each step
with a bad base.

## 5. A gate nobody has watched fail is not a gate

Every gate in the kit was first shown red on a planted defect, then green after the revert, with
the output pasted in the PR. The habit found real holes: a secret scanner that ignores a bare AWS
key ID (it needs the secret beside it); a mutation tool whose warm cache reported a stale survivor
after a test-only fix; a strict-types proof that would also pass in non-strict mode; a CI job that
aborted on its first real PR because the changed file had no function to mutate. `make prove` keeps
the habit mechanical: it plants each defect in a throwaway clone and asserts its gate goes red, so
a project can re-prove its gates on a new machine or after a kit update.

## 6. Tests: who writes them, and how they are protected

If the implementer writes the tests that certify its own code, what do the tests prove? The report's
answer, and the kit's, is layered verification rather than a different author: the **brief** carries
the acceptance criteria as concrete test cases (literal inputs, expected outputs, the edge cases by
name) and the public interface, precisely enough that someone who never saw the implementation
could write the tests; the **implementer** writes those tests first and shows them failing, then the
code; the **mutation gate** checks that the tests bite (a surviving mutant fails the PR); the
**fresh-context plan-reviewer** maps each criterion to a test and flags tautologies.

Agents are known to delete a failing test instead of fixing the code. The first design blocked the
*edit* — a removed `def test_`, an added skip, a shrinking test file — and did not survive a closer
look: every legitimate refactor of a test trips such a pattern, and a test left in place with its
body gutted trips none. The kit checks the **outcome** instead: `scripts/integrity.py` compares the
test IDs the gate ran at the base with the ones it runs now, and lists vanished tests, new skips, and
new escape-hatch comments (`# noqa`, `# type: ignore`, `# pragma: no cover`, `# pragma: no mutate`,
…) — whatever tool made the change. The Stop hook runs the test half, so the session hears about it
while it still has the context; the CI job runs all of it and is red until the maintainer labels
`checks-weakened-approved`. A legitimate rename costs one label and one sentence in the PR. The
assertion-level case (a test kept, its assertion gutted) is what the mutation gate is for.

The escalation for high-stakes units — a separate session writes acceptance tests the implementer
cannot edit — is described and not built; it is for a project whose friction log shows tests being
gamed.

## 7. Context is a budget

A session that has been planning for an hour is the wrong session to implement: its context holds
every option that was considered, every half-decision. The kit gives each role a fresh session and
puts everything a session needs in the repository, never in a conversation:

- **A fresh session per brief.** The brief is self-contained: an implementer sees the brief and the
  repo, never the planning conversation. A planning session's memory is not where requirements
  live — a requirement parked in a session's notes was lost once, and the rule "state lives in files
  and git" came from it.
- **One session per checkout.** A working directory belongs to the session that runs in it. A branch
  switch changes what every process in that folder sees: on 2026-10-02 a planning session switched
  branches in a folder where an implementer was working, and the implementer's committed files
  vanished from its working tree mid-run. A second session that needs the repo clones its own copy.
  The reviewers get a throwaway clone of the PR's head for the same reason; a review no longer
  depends on what any session does to any checkout.
- **`AGENTS.md` ≤ 100 lines**, loaded at session start, pruned weekly with one question per line:
  would removing it cause a mistake? There is no `CLAUDE.md` in a kit project: Claude Code reads
  `AGENTS.md` only when no `CLAUDE.md` exists, so the second file would silence the first.
- **Facts come from dated research notes**, not from the model's memory. The tools change monthly;
  what the model remembers is a version behind. When a fact is missing, a session looks it up,
  verifies it and writes it down with the date.

## 8. Maker ≠ checker

Two reviewers read every PR: the bundled `/code-review` for correctness, and `plan-reviewer` for
conformance — does the diff do what the brief said, no less and no more. Both run as **processes of
their own** (`claude -p`), each on a model and effort the brief names, because inside a session a
skill answers on the project's pinned subagent model whatever is asked for; for seven review rounds
nobody noticed that "Opus" had answered on Sonnet. The launcher has no default model: a reviewer
whose model nobody named does not start.

A reviewer's finding is a **hypothesis**. The implementer reproduces it before changing anything,
decides fix / reject with evidence / park / escalate, fixes with a failing test first, and answers
in the thread. A thread is **resolved only when the implementer has seen the fix work** at the pushed
head; every other thread stays open, because an open thread is how the loop escalates to the
maintainer. Nothing resolves threads automatically; the maintainer asked for judgment, not a
mechanism.

Reviews are bounded by things the reviewer cannot ignore — a time limit, a spending cap, a clone
with no push address — and by requests it is told about (stay read-only, bound every probe, about 25
tool calls). The texts say which is which. One review ran 25 minutes and 150,000 tokens on a single
cost probe before the caps existed.

## 9. Compounding, from real friction

Every time something goes wrong, is slow, costs too much or confuses, one line goes into
`docs/FRICTION.md`: date, kind, what happened, what would have caught it, outcome. Weekly, each line
becomes a hook, a test, a rule or a skill — or an explicit `wontfix`. The table:

| If you corrected… | It becomes… |
|---|---|
| a formatting or style thing | a ruff rule or the format hook |
| a boundary violation | an import-linter contract |
| a behaviour the tests missed | a test, and a mutation-gate check that the test bites |
| a repeated instruction to the agent | one line in `AGENTS.md` (then prune something else) |
| a procedure the agent needs sometimes | a skill under `.claude/skills/` |
| a mistake the agent must never make | a permission rule or a hook, not prose |

The report's warning is that most of the tooling built in 2025 was abandoned, because it was built
against anticipated friction. The kit's backlog is long and its rule is strict: nothing moves from
the backlog to the harness until the friction log shows it twice.

## 10. Documents have a status

Every document opens with a status line, and the status is the contract. `living`: kept true, and
whoever makes a statement in it false fixes it in the same PR (the PR template asks; the
plan-reviewer checks). `snapshot (date)`: never edited; corrections go in a new file. `superseded
by …` / `deprecated (date) — see …`: the old file stays one cycle with the pointer at the top, so a
model that reaches it is redirected instead of misled. Decision records are never edited after
acceptance except to add "Superseded by". **Briefs are pull requests**: the planning session opens
a draft PR with only the brief; the maintainer approves with a label; the implementer continues on
the same branch; brief and code merge together, so every unit carries its own record of intent.

## 11. Models and cost

Every spawned agent names its model and effort; nothing inherits, because one forgotten override on
a fan-out once cost an order of magnitude more than intended. The policy the kit ships: Sonnet at
medium effort by default; Opus at high for a single hardest-judgment agent, never a fan-out; the
largest models only as reviewers of hard or high-stakes work, and stingily; Haiku only for
mechanical steps. `.claude/settings.json` pins the built-in subagents to Sonnet; a spawn overrides
that only explicitly. The brief says which model reviews the unit, and the launcher refuses to guess.

## 12. What is deliberately absent

Risk zoning (green changes merging unread) · nested `AGENTS.md` files · the acceptance-test split ·
automatic start of the implementer on `brief-approved` and of the review on "ready" · an escalation
label with a notification · a real parser for the Bash guard · GitHub branch protection (unavailable
on private repositories without a paid plan, so the kit's enforcement is local plus CI plus labels) ·
anything for a language other than Python (the documents are language-agnostic; the gates are not).
Each is on the kit's backlog with the friction that would promote it.

## 13. How the kit itself evolves

A project finds friction → its fix lands in the project first (the friction is there) → when it
recurs or is clearly general, a PR to the kit, reviewed by the kit's own review loop, merged by the
maintainer, released as a tag → every project takes it with `kit.py update`, which three-way merges
the kit-owned files and leaves the project's own alone. The kit is a working project under its own
gates, so a change to the harness is proven on the harness before any project sees it.
