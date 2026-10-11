# Brief 007 — parallel trees: several briefs at once, one tree each

**Run `/implementer 007` in a fresh Claude Code session started in the development checkout.** You
need no context beyond this file and the repository; do not look for the planning conversation:
there isn't one here, on purpose. This brief lives on branch `main-007-parallel-trees` as draft
PR #7.
Sessions: implementer sonnet / high · review: the `review-loop` skill, `--code opus/high`
`--plan sonnet/medium` `--rounds 2` (all named here: the launcher has no default model).
Labels this PR needs from the maintainer: `brief-approved` to start · `gates-approved`
(`.claude/settings.json`, `.claude/skills/**`, `scripts/tree.py`, `scripts/session_lock.py`,
`scripts/guard_bash.py`, `Makefile`, `.github/workflows/ci.yml`, `.gitattributes`, `kit.py`) ·
`checks-weakened-approved` not expected: no test is removed, and the tests whose data changes keep
their names.
Needs merged: PR 5 (brief 005). The maintainer on the order: "i want it after 5, brief 7, but will
be implemented after 5"; that it is built before brief 006 is the planning session's reading. Once
PR 5 is on `main`, bring this branch up to date (`git merge origin/main`) before the first test.
Size: about 2,700 added lines, 1,550 of them tests. Over the 1,000-line rule by design: a port of
one merged change of the source project, whose pieces do not stand alone.

## Context
The kit says "one session per checkout" and keeps git worktrees out (ADR-0002; `WORKFLOW.md` §1;
`AGENTS.md` line 73). Nothing enforces the first, and two briefs can be built at once only in a
second clone made by hand. The source project changed this in its PR #17 (merge commit `f70ffad`,
2026-10-10; its ADR-0012):
- `make tree BRIEF=NNN` makes a git worktree for the brief's branch in a folder beside the
  development checkout and syncs it; `BRANCH=<name>` takes a branch by name, `NEW=<name>` makes a
  new one from the base; `make untree` removes the folder and keeps the branch.
- A lock (`scripts/session_lock.py`, two hooks) refuses the editing tools of a second session in
  a tree that another holds. It does not stop the shell.
- `git switch` and `git checkout` are denied, so a tree keeps its branch.
- `docs/BACKLOG.md` and `docs/FRICTION.md` merge by union, and a test finds what a union merge
  can leave behind. GitHub does not honour the attribute, so a branch merges the base and pushes
  before it is marked ready.
- A decision put to the maintainer is one bullet per option, each with what it is to build and
  what it is to use; four skills say so.

The maintainer asked on 2026-10-11 for the same in the kit ("migrate that as well"), as one port.
The source project is the one this kit was extracted from;
`docs/research/2026-10-08-role-skills-in-a-headless-run.md` names its repository. Its files are
fetched through the GitHub API at `f70ffad` and copied.

## Objective
The kit carries the source's code for `make tree` and `make untree`, the session lock, the two
deny rules, the union merge of the two logs with its table check, and the decision shape in the
skills: copied from the source's merge commit, not written again, and changed only where the kit
differs: two branch knobs, an owner for every new file, nothing of the kit's history in what a
project receives. Every document says that briefs run side by side, each in its own tree.

## Out of scope — do not do these
- No change of behaviour against the source: what `tree.py` refuses, what the lock stops and what
  it lets through, the 30 minutes. Its known gaps come along as rows of `docs/BACKLOG.md`
  (`untree` does not read the lock; the lock follows the folder a session started in, not the
  file it edits; a new session in a held tree waits for the lock to age).
- `scripts/review.py` and the reviewers' throwaway clones.
- The source's `evals/` files, its plan document and its friction rows.
- Rewording a skill beyond the source's change: the text is the source project's, so that a later
  change on either side merges cleanly.
- One file per row for the two logs; the adopter skill (brief 006); `make prove`; the rehearsal.

## Inputs
- The source's PR #17 at `f70ffad`, through the GitHub API: `scripts/tree.py`,
  `scripts/session_lock.py`, `tests/test_tree.py`, `tests/test_session_lock.py`,
  `tests/test_doc_tables.py`, `tests/test_settings_rules.py`, `.gitattributes`; its hunks in
  `.claude/settings.json`, `Makefile`, `scripts/guard_bash.py`, `.github/workflows/ci.yml`,
  `tests/test_gate_lists.py` and `tests/test_role_skills.py`; ten skill files; its ADR-0012; its
  two research notes of 2026-10-10.
- `kit.py` (`KIT_OWNED`: `.gitattributes` has no owner yet); `scripts/review.py:69` and
  `scripts/stop_gate.py:25` (how a script carries a branch knob); `tests/harness/test_knobs.py`
  (every knob site); `tests/harness/test_kit.py` (`test_kit_owned_python_changes_only_on_knob_lines`,
  `test_a_rendered_projects_harness_tests_pass_with_other_names`, and its uses of the two
  `git switch` rules as the example of a rendered rule); `tests/harness/test_gate_lists.py`;
  `tests/harness/test_stateless.py` (brief 005).
- The sentences this change makes false: `AGENTS.md` line 73 and its list of gate files;
  `docs/kit/WORKFLOW.md` lines 25–35 and §3; `docs/kit/PHILOSOPHY.md` lines 36 and 134–139;
  `docs/kit/SETUP.md` §2 ("Checkouts") and §3; `docs/kit/HARNESS.md` (targets, hooks, permission
  rules, gate files); `README.md`; ADR-0002 (its status line only).
- The three places that tell a session to switch branches, which it is refused after this
  change: `README.md` line 61 and `docs/kit/SETUP.md` line 83 (`git switch -c …-kit-update`: the
  update's branch is made with `make tree NEW=<prefix>-kit-update`, and the update runs in that
  tree) and `docs/kit/WORKFLOW.md` line 82 (the implementer "runs `git fetch && git switch`").
- Checked on 2026-10-11, the kit at `9458f4f` against the source at `f70ffad`:
  - Of the skill files both hold, all were the same text before the source's change but three:
    `implementer/references/page.md`, `implementer/scripts/pr.py`, `review-loop/SKILL.md`
    (`cmp`, file by file). The change touches ten of the kit's skill files, two of them among
    the three (`page.md`, `review-loop/SKILL.md`), and not `pr.py`.
  - The source's `table_problems`, run unchanged over the kit's files: no problem in
    `docs/BACKLOG.md`, `docs/FRICTION.md` and `docs/templates/FRICTION.md`; two in
    `docs/templates/BACKLOG.md`, whose three tables each hold one empty row ("the same row").
  - In the source's `tree.py`, `BASE` (line 33) is the base branch and the prefix of a brief's
    branch at once (lines 148, 189, 257). `session_lock.py`'s `LOCK_NAME` carries the source
    project's name. `test_tree.py` writes the source's branch names as literals, 44 times.
  - The kit's `.claude/settings.json` lines 19–20 are the two allow rules for `git switch`;
    `kit.py` has no rule of its own for them.
  - `uv run python scripts/roles.py` prints 44 rules.
  - Not checked: the lock's two hooks in a reviewer's clone; `make mutate` with the new tests;
    a session in a tree of the kit (the source's note is about its own repository, with Claude
    Code 2.1.296).

## Interface
- **Copied, not written again.** `scripts/tree.py`, `scripts/session_lock.py`, the four test
  files, `.gitattributes`, the eight skill files and the two research notes are the source's files
  at `f70ffad`, fetched and put in place. That code was reviewed for five rounds there, and a
  second writing of it would start that over. A line differs from the source only where this
  section says so: the two knobs, the lock's name, branch names in test data, where a test finds
  the repository's root, and the words that brief 005's rule takes out (a decision-record id, a
  date, the path of a research note, "(brief 009)"). Any other difference goes on the page under
  "Where this differs from the brief".
- `scripts/tree.py`: the source's, with `BASE_BRANCH = "main"  # knob: base` and
  `BRANCH_PREFIX = "main"  # knob: prefix` in place of `BASE`. `BRIEF=NNN` looks for
  `origin/<prefix>-NNN-*`; `NEW=<name>` starts at `origin/<base>`. The commands, the exit codes
  (0 done · 2 refused · 1 the tree was made and its sync failed) and the refusals are the source's.
- `scripts/session_lock.py`: the source's, with `LOCK_NAME = "kit-session.lock"`.
- `Makefile`: `tree` and `untree`, with `BRIEF`, `BRANCH`, `NEW`.
- `.gitattributes`: `docs/BACKLOG.md merge=union` and `docs/FRICTION.md merge=union`. Kit-owned in
  `kit.py`, and a gate file in `scripts/guard_bash.py`, in `ci.yml` and in the documents' lists.
- `.claude/settings.json`: `session_lock.py` at `SessionStart` and before every tool; deny rules
  `Bash(git switch:*)` and `Bash(git checkout:*)`; the two allow rules for `git switch` gone; an
  ask rule `Edit(/.gitattributes)`.
- `tests/harness/`: `test_tree.py`, `test_session_lock.py`, `test_doc_tables.py`,
  `test_settings_rules.py`, and the source's additions to `test_gate_lists.py` and
  `test_role_skills.py`. A branch name in test data is built from `tree.BASE_BRANCH` and
  `tree.BRANCH_PREFIX`, never written out.
- Skills: `brief-writer/{SKILL.md,assets/brief.md,references/decisions.md,references/rules.md}`,
  `implementer/{SKILL.md,assets/pr-page.md,references/rules.md}` and
  `reviewer/references/conformance.md` are the source's text at `f70ffad`. `implementer/references/page.md`
  and `review-loop/SKILL.md` take the source's hunks and keep the kit's own lines.
- `docs/research/`: the source's two notes, each opening with the line that says where it was
  carried from, as the note of 2026-10-08 does.
- `docs/templates/BACKLOG.md` and `docs/templates/FRICTION.md`: each table keeps its header and
  its separator and holds no row.
- A decision record under the next free number, "Briefs run side by side in worktrees of the
  development checkout": the source's five decisions; ADR-0002 superseded in part (its status
  line says so). Recorded as the planning session's choices, not the maintainer's: two knobs in
  `tree.py`; the lock's file name; the templates without an empty row.

## Acceptance criteria — concrete cases; write them as failing tests first
1. Every case of the source's four test files is in the kit under `tests/harness/` and passes.
   Counted as test functions (`grep -c '^def test_'`): 38 in `test_tree.py`, 34 in
   `test_session_lock.py`, 13 in `test_doc_tables.py`, 3 in `test_settings_rules.py`; pytest
   collects more, since some are parametrised. The proof lists both counts beside the source's; a
   case that could not be ported is named on the page with the reason. The order of work: the
   source's tests come first and are red because the script is not there; then the script is
   copied.
2. Two knobs. With `tree.BASE_BRANCH = "trunk"` and `tree.BRANCH_PREFIX = "unit"`, on a temporary
   repository whose bare origin holds `unit-009-x`: `tree --brief 009` makes the worktree on
   `unit-009-x` in `<checkout>-009`; `tree --new unit-010-y` makes a branch that starts at
   `origin/trunk`. The edge: with only `trunk-009-x` on origin, `tree --brief 009` exits 2 and
   says that no branch was found (`test_the_prefix_finds_the_brief_and_the_base_starts_a_new_branch`).
3. In a project rendered with `--base trunk --branch-prefix unit`, `scripts/tree.py` differs from
   the kit's on its two knob lines and nowhere else, and the four new test files pass there:
   they are in the list that `test_a_rendered_projects_harness_tests_pass_with_other_names` runs.
4. The lock is the file `kit-session.lock` in the tree's git directory: after a session's first
   edit hook in a tree, `git status --short` there prints nothing.
5. Neither allow rule for `git switch` is in `.claude/settings.json`, nor in the settings of a
   project rendered with `--branch-prefix unit`; both deny rules are; and the other git rules a
   brief needs are still allowed (the source's three cases, and the rendered project as a fourth).
6. `kit.category(".gitattributes")` is `kit-owned`; a rendered project holds the file; it is a gate
   file in the three lists (`test_gitattributes_is_a_gate_file_in_all_three_lists`).
7. `table_problems` finds nothing in the kit's two logs, and nothing in the two logs of a rendered
   project. The edge: the seeded `docs/BACKLOG.md` has three tables and no row
   (`test_the_logs_a_project_starts_with_have_no_problem`).
8. `tests/harness/test_stateless.py` stays green: no decision-record id, no date outside `tests/`
   and no path of a research note in `scripts/tree.py`, `scripts/session_lock.py`, the settings
   or the documents. The source's "(brief 009)" and its review rounds are not carried either.
9. The eight skill files named under "Interface" are the source's at `f70ffad` byte for byte;
   `uv run python scripts/roles.py` exits 0 and prints as many rules as on `main` before this
   change (44 at `9458f4f`);
   `test_a_decision_is_a_list_with_one_bullet_per_option_and_each_has_both_costs` is ported.
10. No document that a project receives says "never git worktrees" or "Separate clones".
    `AGENTS.md` says that a brief runs in its own tree, names `make tree BRIEF=NNN`, lists
    `.gitattributes` among the gate files, and has at most 85 lines. No document and no skill
    tells a session to run `git switch` or `git checkout`: `git grep -n 'git switch\|git checkout'
    -- docs/kit README.md AGENTS.md .claude/skills` shows only sentences that say the two are
    refused (on 2026-10-11 it prints seven lines, four of them instructions to switch).

Also: `docs/ROADMAP.md` gains this unit (brief 007) and numbers `make prove` 008 and the rehearsal
009; `CHANGELOG.md` ("Unreleased") says what a project gets and that its sessions can no longer
switch branches; `docs/BACKLOG.md` gets the three rows named under "Out of scope".

A criterion a trivial test could satisfy is not a criterion. Existing tests may not be removed,
skipped or weakened, and no escape-hatch comment added: CI job `integrity` lists it; if a test is
genuinely wrong, say so in the PR and the maintainer labels it `checks-weakened-approved`.
Gates: `make check` green; `make mutate` run once and green, because the new tests read files by
their own location (nothing under `src/kitpkg/core` changes, so CI does not run it).
Check by hand: start `claude` in a tree while another session works there, and try an edit;
`make tree BRIEF=<a real brief>` in the development checkout after the merge, which no run before
the merge touches; `/clear` in a held tree, which waits for the lock to age.

## Proofs — in the proofs comment, not in the description
- The failing-test output **before** the implementation (red), and what made it red.
- `make check` output **after** (green), with its exit code; `make mutate` once, with its exit code.
- A types proof must be one only strict mode rejects (an unannotated parameter), not one every
  mode rejects.
- The counts of criterion 1, by file, beside the source's.
- For each of the eight skill files, `cmp` against the source's file at `f70ffad`: no output.
- For `scripts/tree.py`, `scripts/session_lock.py` and each of the four test files, `diff`
  against the source's file at `f70ffad`: the lines "Interface" names, and nothing else. (The
  fetch of one file at that commit through the GitHub API was run on 2026-10-11 and gave the
  file.)
- The real thing once, in a fresh clone that stands in for the development checkout (`$W` is the
  work folder outside the repository, `$P` its proofs folder):
  ```
  K="$(git rev-parse --show-toplevel)"; git clone -q --bare "$K" "$W/origin.git"
  git -C "$W/origin.git" branch main-900-probe main-007-parallel-trees
  git clone -q --branch main-007-parallel-trees "$W/origin.git" "$W/standin" && cd "$W/standin"
  uv sync --locked --all-groups -q
  make tree BRANCH=main-900-probe; git worktree list
  (cd "$W/standin-main-900-probe" && make check > "$P/tree-check.txt" 2>&1; echo "exit code: $?" >> "$P/tree-check.txt")
  make untree BRANCH=main-900-probe; git worktree list; git branch --list 'main-900-*'
  ```
  The bare copy is the stand-in's origin, so nothing is pushed to the development checkout, and
  the probe branch holds this unit's code. Run on this branch on 2026-10-11: the first four
  lines, which end with a synced clone. Not run: the three lines that need `make tree`.
- The lock, with two headless sessions in one tree, as the carried note on sessions in a worktree
  records it for the source: the second session's `Write` is refused with the message that names
  the holder and `make tree`.
- `kit.py update` once for real: a project rendered from `main` as it is before this change, with
  one permission rule of its own added to `.claude/settings.json`, takes this head. The update's
  branch is a tree (`git worktree add -b main-kit-update ../project-update`) and the update runs
  in it, which also shows `kit.py update` in a worktree. The two scripts and `.gitattributes`
  arrive, the settings merge with the project's rule intact, and `make check` is green there.
- No proof command is `git switch` or `git checkout`: after this change a session is refused both.

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
The source writes its branch names into its tests, and a port that swaps them for the kit's
passes here and fails in every project with another prefix: kit-owned Python changes on its knob
lines only, so test data built from a literal `main-009-x` is not rendered. Build every name from
the script's two constants, and let the rendered-project test run the new files. And say what a
safeguard stops and what gets past it: the deny rules stop the plain spelling of a command
(`git -C . switch` runs past them), and the lock stops the editing tools, not the shell.

Brief written in session b4ea0b41-c867-4aa6-b5e6-2f20b4ea5742
