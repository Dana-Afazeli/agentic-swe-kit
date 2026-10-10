# Brief 005 — a project holds no record of the kit

**Run `/implementer 005` in a fresh Claude Code session started in the development checkout.** You
need no context beyond this file and the repository; do not look for the planning conversation:
there isn't one here, on purpose. This brief lives on branch `main-005-stateless-projects` as draft
PR #5.
Sessions: implementer sonnet / high · review: the `review-loop` skill, `--code opus/high`
`--plan sonnet/medium` `--rounds 2` (all named here: the launcher has no default model).
Labels this PR needs from the maintainer: `brief-approved` to start · `gates-approved` (`kit.py`:
the manifest and two comments; comments and docstrings only in `scripts/integrity.py`,
`scripts/stop_gate.py`, `scripts/review.py`, `scripts/guard_bash.py`, `scripts/roles.py` and
`.github/workflows/ci.yml`) · `checks-weakened-approved` not expected: no test is removed, and the
tests whose data changes keep their names.
Needs merged: nothing.
Size: about 350 added lines of code and tests; the prose changes replace lines one for one. This
brief is longer than one screen because it lists the known sites.

## Context
`kit.py`'s manifest (`CATEGORIES`) decides what a project made by `init` receives. The kit's
decision records, briefs, changelog, roadmap, friction log and backlog are kit-only. Three things
still carry the kit's history into a project: the five research notes (`docs/kit/research/*`
matches the kit-owned `docs/kit/*`); pointers in shipped files to records a project does not have
(17 `ADR-NNNN` ids in 11 files, and the paths of four notes and one brief in four files); and
sentences that tell what happened to the kit instead of what the thing does. Counted on 2026-10-10
at `9458f4f` with `git grep`; the first command under "Proofs" shows the same in a rendered project.

The rule, decided by the maintainer on 2026-10-10: **a project receives the structure and empty
places for its own records, and nothing about how the kit came to be.** The maintainer's two
answers: the research notes — `move` (to `docs/research/`, kit-only there); a pointer to a record
in a shipped file — "just state the decision without explanation or pointers". This unit runs
before `make prove`, which becomes brief 006.

## Objective
A project rendered by `kit.py` holds none of the kit's records, no pointer to one, no record id and
no date: the research notes move to `docs/research/` and are kit-only, `docs/briefs/` and
`docs/research/` ship empty, and every shipped file says what is decided and nothing more. A
kit-only test that renders a project keeps it so.

## Out of scope — do not do these
- `tests/harness/**` ships as it does now: the harness's tests are structure, not history.
- No render rule: nothing is stripped at `init` or `update` time, and `render_text` does not
  change. The kit's own files lose the pointers, so the kit and a project read the same.
- The decision records and briefs 001–004 are records and are not edited, although three links in
  briefs 002 and 004 to `docs/kit/research/…` stop resolving.
- `PHILOSOPHY.md` keeps its reasoning. Only a sentence that tells an event (a date, an incident, a
  count of review rounds) is restated as the fact it taught; nothing else is shortened or moved.
- The shipped documents name a `make prove` target and a CI job `prove` that do not exist yet
  (brief 006 builds them): one `docs/BACKLOG.md` line, no edit.
- Installing the kit into an existing repository, other language stacks, a release tag.

## Inputs
- `kit.py`: `KIT_OWNED`, `PROJECT_OWNED`, `KIT_ONLY_FIRST`, `KIT_ONLY`, `CATEGORIES`, `category()`
  (the first category that matches wins, in the order of `CATEGORIES`), `tracked_files`,
  `render_tree` — for the manifest change and for rendering a project in a test.
- `docs/kit/HARNESS.md` §9 — the ownership table that
  `test_the_categories_are_what_the_harness_doc_says` compares with the manifest.
- `tests/harness/test_kit.py` — `kit_repo`, `project_from`,
  `test_init_renders_seeds_removes_and_writes_the_lock`; `kit_repo` (line 689) and
  `test_update_merges_adds_removes_and_relocks` / `test_update_keeps_a_removed_file_the_project_changed_and_says_so`
  (lines 831, 884) use `docs/kit/research/2026-09-29-toolchain-and-claude-code.md` as the kit-owned
  file that version 0.2.0 removes: after the move no note is kit-owned.
- `tests/harness/test_no_leftovers.py` (`CITES_THE_SOURCE`), `tests/harness/test_role_skills.py`
  (`RECORDS`, `BRIEF`, `test_agents_md_keeps_what_every_role_needs`),
  `tests/harness/test_roles.py:238,298` and `scripts/roles.py:58` (a near-miss case spelled as a
  record id).
- `AGENTS.md` "Facts and state"; `docs/kit/SETUP.md` §7; `README.md` lines 83 and 93;
  `docs/ROADMAP.md`; `docs/decisions/0007-*.md` (ownership) and `0000-TEMPLATE.md`.
- The known sites, by line at `9458f4f`. The rule decides, not this list:
  - record ids — `.github/workflows/ci.yml:116,117` · `docs/kit/HARNESS.md:64,117,170` ·
    `docs/kit/PHILOSOPHY.md:116` · `docs/kit/SETUP.md:34,56` · `docs/kit/WORKFLOW.md:55` ·
    `kit.py:17` · `scripts/integrity.py:1,20` · `scripts/stop_gate.py:9` · `scripts/roles.py:58` ·
    `tests/harness/test_stop_gate.py:5` · `tests/harness/test_roles.py:238,298`
  - paths of records — `AGENTS.md:70` · `scripts/guard_bash.py:34` · `scripts/review.py:15,65` ·
    `tests/harness/test_role_skills.py:32,148,211,258,283,297`
  - dates — `docs/kit/HARNESS.md:12` · `docs/kit/PHILOSOPHY.md:135` · `scripts/review.py:24,229,310`
  - events told — `docs/kit/PHILOSOPHY.md:8-10,114,156` · `docs/kit/WORKFLOW.md:26,93-94` ·
    `docs/kit/SETUP.md:104,110` · `scripts/integrity.py:20` · `kit.py:230,408`

## Interface
- The manifest in `kit.py`: `docs/research/*` is kit-only; `docs/briefs/.gitkeep` and
  `docs/research/.gitkeep`, both empty, are project-owned, so `init` hands them over and `update`
  never touches them; `docs/MAINTAINING.md` (SETUP §7, moved) and
  `tests/harness/test_stateless.py` are kit-only. No new command, option or function in `kit.py`.
- `tests/harness/test_stateless.py`: three functions over a tree, each returning sorted
  `"<file>:<line>: <what matched>"` strings, empty when the tree is clean.
  - `record_ids(root: Path) -> list[str]` — `ADR-[0-9]{4}` in any file.
  - `record_pointers(root: Path, kit_only: Iterable[str]) -> list[str]` — a file other than
    `kit.py` that contains one of the paths in `kit_only`. `kit.py` is the manifest: it names the
    kit's tree.
  - `dates(root: Path) -> list[str]` — `20[0-9]{2}-[0-9]{2}-[0-9]{2}` in a file outside `tests/`,
    `kit.lock` and `uv.lock`.
  - A module-scoped fixture renders the kit once with `kit.render_tree` over `kit.tracked_files`,
    package `acme`, maintainer `Ada Lovelace`; `KIT_ONLY_DOCS` is every tracked path under `docs/`
    whose category is `kit-only` and which the rendered tree does not hold.
- `docs/decisions/0010-a-project-holds-no-record-of-the-kit.md`: the rule and the maintainer's two
  answers in their words, as above. Recorded as the planning session's choices, not the
  maintainer's: `.gitkeep` as the placeholder and its ownership; the date rule and what it leaves
  out; `docs/MAINTAINING.md`; `kit.py` left out of the pointer check; that `PHILOSOPHY.md` keeps
  its reasons; that a site which tells an event keeps the fact.
- Checked on 2026-10-10 at `9458f4f` by calling it: `review.find_brief("main-001-first",
  [".gitkeep", "001-first.md"])` returns `docs/briefs/001-first.md`, and with `[".gitkeep"]`
  returns `None`. Not checked: whether anything else lists `docs/briefs/`.

## Acceptance criteria — concrete cases; write them as failing tests first
1. In the rendered project, the files under `docs/` are exactly `BACKLOG.md`, `DELTAS.md`,
   `FRICTION.md`, `ROADMAP.md`, `briefs/.gitkeep`, `decisions/0000-TEMPLATE.md`, `kit/HARNESS.md`,
   `kit/LICENSE`, `kit/PHILOSOPHY.md`, `kit/SETUP.md`, `kit/WORKFLOW.md`, `research/.gitkeep`, and
   both `.gitkeep` files hold 0 bytes (`test_a_project_gets_the_places_and_none_of_the_records`).
2. `kit.category("docs/research/2026-10-05-review-model-and-effort.md")` is `kit-only`;
   `docs/research/.gitkeep` and `docs/briefs/.gitkeep` are `project-owned` — the edge: each sits
   under a kit-only `*` pattern, and the first match wins; `docs/MAINTAINING.md` is `kit-only`;
   `kit.is_managed("docs/research/2026-11-01-ours.md")` is false
   (`test_the_places_are_the_projects_and_what_the_kit_keeps_there_is_not`).
3. `record_ids`: a tree whose `scripts/x.py` holds the one line `# see ADR-0008` gives
   `["scripts/x.py:1: ADR-0008"]`; a file holding `ADR-NNNN`, `RFC-2119` and `ADR-008` gives `[]`
   — the edges: the template's placeholder, another three-letter token, three digits. The rendered
   project gives `[]` (`test_no_file_of_a_project_names_a_decision_record`).
4. `record_pointers` with `["docs/decisions/0008-stop-hook-keeps-make-check-only.md"]`: a tree
   whose `AGENTS.md` names that path on line 3 gives
   `["AGENTS.md:3: docs/decisions/0008-stop-hook-keeps-make-check-only.md"]`; the same line in
   `kit.py` gives `[]`; a line that names the folder `docs/decisions/` gives `[]`. The rendered
   project with `KIT_ONLY_DOCS` gives `[]`, and `KIT_ONLY_DOCS` holds at least the five notes
   under `docs/research/`, ten decision records and five briefs — the edge: an empty list would
   pass (`test_no_file_of_a_project_points_at_a_record_of_the_kit`).
5. `dates`: `docs/kit/HARNESS.md` holding `(2026-10-06)` gives one entry; the same text in
   `tests/harness/test_review.py`, in `kit.lock` and in `uv.lock` gives `[]`; `2026-1-6` gives
   `[]`. The rendered project gives `[]` (`test_no_file_of_a_project_carries_a_date`).
6. `AGENTS.md` names `docs/research/` and no longer `docs/kit/research/`, in at most 85 lines:
   `test_agents_md_keeps_what_every_role_needs` asks for `docs/research/`.
7. No file of the rendered project contains `docs/kit/research`. Once the notes have moved, their
   old paths are in no list that `record_pointers` reads, and `dates` leaves `tests/` out, so
   nothing else sees them (`test_no_file_of_a_project_names_where_the_notes_were`). On 2026-10-10
   four files do: `AGENTS.md`, `scripts/guard_bash.py`, `scripts/review.py`,
   `tests/harness/test_role_skills.py`.

Tests whose data changes and whose names stay: `kit_repo` gives version 0.1.0 a kit-owned file
made for the purpose (`docs/kit/OLD.md`) that 0.2.0 removes, and the two update tests named under
"Inputs" use it; `CITES_THE_SOURCE` and `RECORDS` name `docs/research/`; `BRIEF` in
`test_role_skills.py` and the near-miss case in `test_roles.py` and `scripts/roles.py` are spelled
with names that are no record of the kit (`RFC-2119` is three letters, a dash and digits too).

The prose, which no test can show, at the two kinds of site:
- A site that points at a record (an id, a path) keeps the decision — what the thing does, what
  the reader has to do — and nothing else: no pointer and no explanation.
- A site that tells an event (a date, an incident, a count of rounds) loses the event and keeps
  the fact, in the present tense; a condition replaces a story.

`PHILOSOPHY.md` is where the reasons live: it keeps them, and loses its ids, dates and events.

| At `9458f4f` | After |
|---|---|
| `ci.yml:116-117` "…adds the label `checks-weakened-approved` (ADR-0005). Only this job holds the merge for it: the Stop hook no longer runs the script (ADR-0008); the implementer runs it…" | "…adds the label `checks-weakened-approved`. Only this job holds the merge for it; the implementer runs the script…" |
| `HARNESS.md:170` "It does not look at vanished tests or at the label: it did until ADR-0008, and held every session on a branch that removed a test on purpose, the reviewers' too; that check is CI's `integrity` job's alone." | "It does not look at vanished tests or at the label: that check is CI's `integrity` job's alone." |
| `PHILOSOPHY.md:116` "a hold the held party cannot lift is a stall, not a gate (ADR-0008)" | the same sentence without the parenthesis |
| `WORKFLOW.md:26` "…share `.git/hooks` and Claude Code's local settings with the main checkout, and both bit us." | "…share `.git/hooks` and Claude Code's local settings with the main checkout." |
| `SETUP.md:110` "…and the kit has no tag for the lock's version (a project made from the kit before its first release)" | the same sentence without the parenthesis |

Also: `docs/kit/SETUP.md` ends with §6, and §7 is `docs/MAINTAINING.md`, except its last line (a
project's fix to a kit-owned file goes to the kit as a pull request), which is for projects and
stays in SETUP §4; `HARNESS.md` §9, `README.md` lines 83 and 93, and `CHANGELOG.md` ("Unreleased":
the notes moved and left the projects, the two places, what `update` does with the notes in a
project that has them) say what is true; `docs/ROADMAP.md` gains this unit as 2c, ticks units 1 to
2b as merged (pull requests 1 to 4, 2026-10-10), and numbers `make prove` 006 and the rehearsal 007.

A criterion a trivial test could satisfy is not a criterion. Existing tests may not be removed,
skipped or weakened, and no escape-hatch comment added: CI job `integrity` lists it; if a test is
genuinely wrong, say so in the PR and the maintainer labels it `checks-weakened-approved`.
Gates: `make check` green; `make mutate` not applicable (nothing under `src/kitpkg/core` changes).
Check by hand: read `git diff origin/main -- docs/kit AGENTS.md scripts .github kit.py` for
meaning — each rewritten sentence still tells a session what to do, with its commands and its
conditions whole; and open `docs/` in a project rendered with the first command under "Proofs":
two empty folders, the record template, four documents and the license.

## Proofs — in the proofs comment, not in the description
- The failing-test output **before** the implementation (red), and what made it red.
- `make check` output **after** (green), with its exit code.
- A types proof must be one only strict mode rejects (an unannotated parameter), not one every
  mode rejects.
- A rendered project, before the first change and after the last (`$W` is the work folder outside
  the repository; a fresh folder for each run). Run on this branch on 2026-10-10: it lists 11 files
  with an id, 4 files that name `docs/kit/research`, and 15 files under `docs/`, five of them
  notes. After: neither `grep` prints a file, and `find` prints the 12 files of criterion 1.
  ```
  python3 kit.py render --package acme --maintainer "Ada Lovelace" --into "$W/before"
  cd "$W/before" && grep -rIlE 'ADR-[0-9]{4}' . | sort
  grep -rIl 'docs/kit/research' . | sort; find docs -type f | sort
  ```
- The real thing once: a project rendered from `9458f4f` takes this branch's head. Expected:
  "5 removed" (the notes), "0 with conflicts", exit code 0, and `git status --short` shows the
  five deletions. Run on this branch on 2026-10-10, where nothing kit-owned differs yet: it prints
  "0 merged, 0 with conflicts, 0 added, 0 removed" with exit code 0, and only `kit.lock` changes.
  ```
  K="$(git rev-parse --show-toplevel)"; git clone -q "$K" "$W/old" && git -C "$W/old" checkout -q 9458f4f
  (cd "$W/old" && python3 kit.py render --package acme --maintainer "Ada Lovelace" --into "$W/project")
  cd "$W/project" && git init -q -b main && git add -A && git commit -qm "a project at 9458f4f"
  git switch -q -c main-kit-update
  python3 kit.py update --repo "$K" --from 9458f4f --to main-005-stateless-projects --no-sync; echo "exit code: $?"
  git status --short
  ```

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
The scans read a rendered project, never the kit's own tree. In the kit, this brief, the decision
records and the changelog name every id and every path on purpose, so a scan of the repository is
red for ever, or is given so many exceptions that it checks nothing. And removing a pointer is not
removing the rule: a sentence that loses its "(ADR-0008)" still has to say that the Stop hook runs
`make check` and nothing else.

Brief written in session b4ea0b41-c867-4aa6-b5e6-2f20b4ea5742
