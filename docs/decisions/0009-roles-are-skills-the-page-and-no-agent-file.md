# ADR-0009 — Roles are skills; the PR description is a page; the conformance reviewer has no agent file

**Status:** accepted 2026-10-10 (adopted from the source project's ADR-0011, decisions 9 to 12, of
2026-10-08, and its pull request #15) · **Deciders:** the maintainer · **Supersedes:** nothing
whole. ADR-0003's allowlist and hooks stand; the agent file it mentions in passing is gone.

## Context
Three roles build a project made from the kit: the planning session that writes a brief, the
session that builds it, and the processes that review it. How each works was spread over
`AGENTS.md` (which every session loads, whatever its role), two templates (the brief, the PR
description), an agent file (`.claude/agents/plan-reviewer.md`), the `review-loop` skill and the
workflow documents. What that cost, in the source project and in the kit's first pull requests:
- A PR description of 579 lines, 413 of them evidence and proofs that no reviewer read; the
  maintainer's part was not findable in it.
- Rules a role needed were in a file every role paid for in context, and rules a session needed
  were in places it never read.
- The agent file let any session spawn the conformance reviewer as an agent — inside its own
  context, past the launcher's cost cap, time limit and advisor switch. A review done inside the
  session that made the change is not a review, whatever it finds.
- A fix in a review loop covered the reported case and not its kind, round after round: eight
  rounds on the Bash guard, five on cancel handling.
- Work the maintainer had said yes to in chat was reported as out of scope by a reviewer that could
  not see the chat.

## Decision
1. **Each role is a skill**, a folder under `.claude/skills/` whose `SKILL.md` is the whole
   procedure of the role's work, started by one line: `/brief-writer`, `/implementer NNN`, and
   `/reviewer conformance` for the process the launcher starts. Its templates are in `assets/`
   (the brief, the page), its examples and its rule table in `references/`, its scripts in
   `scripts/`. An instruction someone could check starts with an id (`B-`, `I-`, `P-`, `C-`), and
   `references/rules.md` has one row per id with where it is checked from; `scripts/roles.py`
   fails when text and table disagree. Checking that a session kept its rules is not built: it is
   measured from records first (the source project's brief 010), a gate only after that.
2. **`AGENTS.md` keeps what every role needs** — it opens with "Roles", which sends a session to
   its skill — and nothing one role alone needs. Budget 85 lines, from 100.
3. **The PR description is a page**: at most 80 lines the maintainer reads (what this is and where
   it sits · next steps, each with what it unblocks · decisions, each standing alone · not proven),
   then a reference line and the parts the reviewers check. `pr.py page` refuses what is not the
   page by shape; whether it reads cold is the conformance reviewer's to judge. Proofs go in one PR
   comment (`pr.py proofs`), verbatim from saved files, never in the description.
4. **The conformance reviewer has no agent file.** The launcher names its tools
   (`--tools Read,Grep,Glob,Bash`: it reads, and reads git and the PR through a shell) and starts
   it on the reviewer skill. It has no `Edit` and no `Write` tool; Bash can still write, so that it
   only reads is asked of it, and its clone is thrown away. With the file gone, no session can
   spawn that reviewer as an agent.
5. **The conformance review checks the proofs and the page too** (P-05 proof missing or
   contradicted, P-06 does not read cold, P-07 not the page) beside the four kinds it had.
6. **Work beyond a brief needs the maintainer's word on the pull request**: the label
   `scope-approved`, asked for by the implementer, who lists the work on the page with the
   maintainer's words quoted. The conformance reviewer counts such work as a finding only without
   the list or the label. The label is read by that reviewer alone; no CI job holds the merge for it.
7. **Fix the kind, not the case** (I-14): at the second finding of one kind the implementer stops
   patching, writes the invariant and a test for each way it can break; a third round on one kind
   goes to the maintainer as a decision.
8. **The skills name no person and no project**, so that they are the same text in every project
   made from the kit and in the source they came from: they say `the maintainer` and `the base
   branch`, and `AGENTS.md`'s Roles section says who and which. `kit.py` renders nothing under
   `.claude/skills/`, and leaves the phrase "the maintainer" alone wherever it stands in backticks.

Considered and set aside: rendering the skills with the project's values — `pr.py` is Python and
is never rendered, so a rendered page template would say a name where the script looks for the
role phrase, and every rendered project's `pr.py page` would refuse its own page; test prompts for
the skills (`evals/`) — the source project's are its own, and running a skill on a prompt is the
rehearsal's work; keeping the agent file with a `skills:` field — it would still let a session spawn
the reviewer.

## Consequences
- A session that is asked to plan runs `/brief-writer`; one asked to build runs
  `/implementer NNN`; a reviewer process reads its reference. A rule that lives in a skill reaches
  only a session that runs it, which is why "Roles" is the first section of `AGENTS.md`.
- The maintainer changes how a role works by editing its skill, in the kit (then every project
  takes it with `kit.py update`, a clean merge, since the text is the same everywhere) or in a
  project (then `update` merges the kit's change into the project's, and a collision is visible).
- `tests/harness/test_role_skills.py` holds the shape of the skills and of `AGENTS.md`;
  `test_roles.py` the rules; `test_pr.py` the page and the proofs comment. The rendered-project
  test runs all three in a project rendered with long names, where `pr.py` and the page template
  have to agree.
- `.claude/skills/implementer/scripts/pr.py` lives in a dot-folder that basedpyright leaves out,
  also when named: a test type-checks a copy of it in strict mode (BACKLOG).
- What would make this wrong: a session that regularly reaches a skill late or not at all (the
  trigger rate is measured once, in the rehearsal, not tuned); a page that the maintainer finds
  too short for a unit; a `scope-approved` used so often that a reviewer's report is not enough and
  CI has to hold the merge for it.
