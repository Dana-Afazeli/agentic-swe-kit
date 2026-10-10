# Brief 004 — role skills: the brief writer, the implementer and the reviewer are each a skill

**Run `/implementer 004` in a fresh Claude Code session started in the development checkout.** You
need no context beyond this file and the repository; do not look for the planning conversation:
there isn't one here, on purpose. This brief lives on branch `main-004-role-skills` as draft PR #4.
Sessions: implementer — the planning session itself, by the maintainer's standing decision of
2026-10-06 · review: the `review-loop` skill, `--code opus/high` `--plan sonnet/medium`
`--rounds 3` (all named here: the launcher has no default model).
Labels this PR needs from the maintainer: `brief-approved` to start · `gates-approved`
(`.claude/**`, `scripts/**`, `pyproject.toml`, `kit.py`, `AGENTS.md`) · `checks-weakened-approved`
(two test IDs of the review launcher change: the one that asserted the conformance reviewer runs as
an agent, and a parametrised case whose made-up brief file was named after the template that
moves).
Needs merged: PRs #1, #2 and #3 (this branch is stacked on `main-003-stop-hook-make-check-only`).
Size: about 3,500 added lines, 1,700 of them tests. Over the 1,000-line rule by design: a port of
one merged change of the source project, whose pieces do not stand alone (the skills, the scripts
that check them, the launcher that starts one of them, the documents that describe them).

## Context
How each of the three roles works — the planning session that writes a brief, the session that
builds it, the processes that review it — is spread over `AGENTS.md`, two templates
(`docs/briefs/000-TEMPLATE.md`, `.github/pull_request_template.md`), an agent file
(`.claude/agents/plan-reviewer.md`), the `review-loop` skill and the workflow documents. The source
project made each role a **skill** (its PR #15, 2026-10-10; its ADR-0011, decisions 9–12): a
folder under `.claude/skills/` whose `SKILL.md` is the procedure a session runs, with its templates
(`assets/`), examples and rule table (`references/`) and scripts beside it. Its rules are
numbered (`B-`, `I-`, `P-`, `C-`) and a script fails when a skill's text and its table disagree.
The PR description becomes a **page** — at most 80 lines the maintainer reads, a reference line,
then what the reviewers check — set by a script that refuses what is not the page; proofs go in one
comment. The conformance reviewer has no agent file: the launcher names its tools. A fourth label,
`scope-approved`, is how the maintainer's yes to work beyond a brief reaches the pull request. The
skills were written to name no person and no project, for this kit. ADR-0009 (in this PR) records
the decision for the kit; `docs/kit/research/` carries the two dated notes the mechanics rest on.

## Objective
The kit carries the three role skills, `scripts/roles.py`, the page and proofs script, the launcher
change and the four-label workflow, with every document saying what is true; the two templates and
the agent file are gone. `kit.py` renders nothing under `.claude/skills/`: skills name no person
and no project, and `AGENTS.md`'s Roles section says who the maintainer is and which branch is the
base.

## Out of scope — do not do these
- No `evals/` for the skills and no test that requires them (the maintainer's decision of
  2026-10-10); running a skill on a test prompt is the rehearsal brief's work.
- No adherence checker, no state machine, nothing that starts a role by itself.
- No change to what a gate does: hooks, CI jobs, the `Makefile`, thresholds. `scope-approved` is read
  by the conformance reviewer only, as in the source project.
- `kit.py update`/`status` (PR #2) and the Stop hook (PR #3) beyond what this change touches.
- Rewording the skills beyond what a generic template needs: the text is the source project's, so
  that a later update of either side merges cleanly.

## Inputs
- The source project's PR #15 at its merge commit `fa7686d`, read through the GitHub API, for every
  file under "Copied" below, `scripts/review.py`'s four hunks, `AGENTS.md`'s shape, and the tests
  `tests/test_roles.py`, `tests/test_role_skills.py`, `tests/test_pr.py`, `tests/test_review.py`.
- `kit.py` (`render_text`, `CATEGORIES`, `LABELS`, `SHADOWED`, the next-steps text) — what the port
  changes; `tests/harness/test_kit.py`, `test_knobs.py`, `test_no_leftovers.py` — what goes red.
- `scripts/review.py` and `tests/harness/test_review.py` — the launcher and its fake `claude`.
- `AGENTS.md`, `docs/kit/{HARNESS,WORKFLOW,PHILOSOPHY,SETUP}.md`, `README.md`, `docs/ROADMAP.md`,
  `docs/BACKLOG.md` — the sentences this change makes false.

## Interface
- Copied: `.claude/skills/brief-writer/{SKILL.md,assets/brief.md,references/decisions.md,references/rules.md}`,
  `.claude/skills/implementer/{SKILL.md,assets/pr-page.md,references/page.md,references/rules.md,scripts/pr.py}`,
  `.claude/skills/reviewer/{SKILL.md,references/conformance.md,references/correctness.md,references/rules.md}`,
  `scripts/roles.py` (`rules(skill: Path) -> list[Rule]`, `Rule(id, words, checked_from)`, `main(skills) -> int`),
  the `review-loop` skill's `SKILL.md` and `references/commands.md` as reworded upstream, keeping
  the kit's own pitfalls.
- `scripts/review.py`: `PROTOCOL` → `.claude/skills/reviewer/references/correctness.md`;
  `PLAN_TOOLS = "Read,Grep,Glob,Bash"`; the conformance reviewer starts as
  `claude -p --tools Read,Grep,Glob,Bash …` with a prompt whose first line is `/reviewer conformance`.
- `kit.py`: `render_text(path, …)` returns text under `.claude/skills/` unchanged; `KIT_OWNED` loses
  the two template paths; `LABELS` gains `scope-approved`; `SHADOWED` gains `pr` and `roles`.
- `pyproject.toml`: `.claude/skills/implementer/scripts` on ruff's `src`, basedpyright's
  `extraPaths` and pytest's `pythonpath`.
- Removed: `.claude/agents/plan-reviewer.md`, `.github/pull_request_template.md`,
  `docs/briefs/000-TEMPLATE.md`, `.claude/skills/review-loop/references/code-review-protocol.md`.

## Acceptance criteria — concrete cases; write them as failing tests first
1. `uv run python scripts/roles.py` exits 0 and lists exactly B-01…B-12, I-01…I-17, P-01…P-09 and
   C-01…C-06, each in its skill (`test_the_repositorys_rules_are_consistent`,
   `test_each_role_skill_has_exactly_the_ids_the_brief_names`); on temporary skills, an id with no
   row, a row with no id, an id used twice, a bad "checked from" each exit 1 naming file and line
   (`tests/harness/test_roles.py`, ported).
2. `pr.py page` on files: 81 lines above the reference line → exit 1, the message says 81; a part
   missing → exit 1 naming it; a comment of the template left → exit 1; a right page with
   `--dry-run` → exit 0 and `page.md` in the folder. `pr.py proofs --dry-run` on a folder with
   `red.txt` and `green.txt` → one file, the marker with head and session id first, one collapsed
   block per file, text unchanged; a second session id accumulates (`tests/harness/test_pr.py`,
   ported, with the kit's repository root and a neutral `src/pkg/core/…` example).
3. Each `SKILL.md`: frontmatter with `name` and `description`; at most 200 lines; ends with "How
   this role ends"; names every file under its `references/`, `assets/`, `scripts/`; no ALWAYS,
   NEVER, MUST in capitals; no `$` followed by a digit; no pronoun of one person for the
   maintainer; no pointer at a repository's history (`PR #n`, `ADR-dddd`, `FRICTION 20dd`)
   (`tests/harness/test_role_skills.py`, ported without the evals cases).
4. The conformance reviewer: `claude_argv("plan", …)` begins `claude -p --tools Read,Grep,Glob,Bash`
   and holds no `--agent`; `plan_prompt` begins `/reviewer conformance`; the code reviewer's command
   holds no `--tools`; `PROTOCOL` is the reviewer skill's `correctness.md` and every `{{…}}`
   placeholder survives (`test_review.py`, `test_role_skills.py`).
5. `kit.py init --package demo --maintainer "Ada Lovelace" --base release/2026-stable --branch-prefix feature/units`
   in a committed copy leaves every file under `.claude/skills/` byte-identical to the kit's, and
   renders `AGENTS.md`'s Roles line (`test_render_text_leaves_the_skills_alone`; the rendered-project
   test runs the ported tests too, so `pr.py`'s headings and the rendered page template agree).
6. `AGENTS.md`: shorter than 92 lines and no longer than the budget its header names; its first
   section is "Roles" and names `/brief-writer`, `/implementer NNN` and `scripts/review.py`; it has
   no heading containing "TDD" and does not contain "failing test", "walkthrough" or "review-loop";
   it keeps `Never commit or push to \`main\``, the gate files list, the four labels, the Bash
   guard, secrets, one session per checkout, "Project rules".
7. `.claude/agents/plan-reviewer.md`, `.github/pull_request_template.md`,
   `docs/briefs/000-TEMPLATE.md` are gone and no tracked file outside the records (`docs/briefs/`,
   `docs/decisions/`, `docs/kit/research/`, `docs/research/`, `docs/FRICTION.md`, `CHANGELOG.md`)
   names them; `kit.category()` places every skill file under kit-owned; every ownership pattern
   still names a file.
8. `uv run python scripts/integrity.py --base origin/main-003-stop-hook-make-check-only` lists
   exactly the two changed IDs of `test_review.py` and nothing else.
9. A run, not a test: this PR's own round 1 — the conformance reviewer's record exists on the PR,
   begins `**[plan-reviewer · round 1`, and came from a process the launcher started with
   `--tools Read,Grep,Glob,Bash` (the dry-run output in the proofs comment).
A criterion a trivial test could satisfy is not a criterion. Existing tests may not be removed,
skipped or weakened, and no escape-hatch comment added: CI job `integrity` lists it; if a test is
genuinely wrong, say so in the PR and the maintainer labels it `checks-weakened-approved`.
Gates: `make check` green; `make mutate` does not apply (no `core/` module changes).
Check by hand: that the three skills read as the maintainer wants them, since they are what the
maintainer edits to change how a role works (about 400 lines together); that a project rendered
from this head has a `pr.py page --dry-run` that accepts a page built from its own page template.

## Proofs — in the proofs comment, not in the description
- The ported tests red before each change they drive (the launcher, `render_text`, `AGENTS.md`),
  and what made them red; `make check` green after, with its exit code.
- `uv run python scripts/roles.py`, exit 0, 44 lines.
- The integrity listing of criterion 8.
- `kit.py update` once for real: a project rendered from PR 3's head takes this head — the four
  removed files go, the skills arrive, `AGENTS.md` merges with its "Project rules" intact,
  `make check` green in the project.
- The launcher's `--dry-run` for this PR, showing the conformance reviewer's command line.

## Cautions — the same in every brief
- **Every wait and every teardown in a test has a bound.** A bound inside a test does not bound
  its teardown: a test whose own wait fails after five seconds can still hang for ever when it
  is torn down.
- **Ask of a red run: "red because of what?"** before you write the fix. The failure message or a
  log line of the unfixed run has to name the cause; a test can be red for a reason that is not
  the missing behaviour.
- **A test of a queue, or of an order, is run once against a deliberately wrong implementation**
  (one that runs a task per message): a test that passes against it tests nothing.
- **Three kinds of mutant no test kills**, so do not write the code that makes them: a flag read
  only for its truth and initialised to a value nothing reads; a bound that a later check
  verifies again; a `join` separator over at most one element. Compute the exact value, and give
  a flag no value to mutate.

## Output contract
The description is the page, set with the implementer skill's `pr.py page`: what this is and
where it sits · **Next steps for the maintainer** (every action only the maintainer can take, in
order, each with what it unblocks) · **Decisions for the maintainer** · **Not proven**; the
reference sections below the line. Proofs go in the proofs comment (`pr.py proofs`).
Out-of-scope things you notice → a line in `docs/BACKLOG.md`; what went wrong, was slow or
confused → a line in `docs/FRICTION.md`. Mark the PR ready (`gh pr ready <n>`) when done. Do not
merge; do not touch labels.

## One caution
The skills are the source project's text, and the kit's renderer rewrites "the maintainer" in
every file that is not Python. Rendered skills would say "Ada Lovelace" where `pr.py`, which is
Python and never rendered, looks for "Next steps for the maintainer": every rendered project's
`pr.py page` would then refuse its own page. The exemption of `.claude/skills/` from rendering is
the one line this port cannot do without; the rendered-project test is where its absence shows.

Brief written in session fe6d99fa-621b-4dc0-966c-fcb4af39d988
