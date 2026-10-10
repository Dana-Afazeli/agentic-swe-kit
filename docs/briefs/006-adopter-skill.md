# Brief 006 — the adopter: a skill that brings an existing repository under the kit

**Run `/implementer 006` in a fresh Claude Code session started in the development checkout.** You
need no context beyond this file and the repository; do not look for the planning conversation:
there isn't one here, on purpose. This brief lives on branch `main-006-adopter-skill` as draft
PR #6.
Sessions: implementer opus / high · review: the `review-loop` skill, `--code opus/high`
`--plan sonnet/medium` `--rounds 2` (all named here: the launcher has no default model).
Labels this PR needs from the maintainer: `brief-approved` to start · `gates-approved` (`kit.py`:
two manifest lines; `.claude/skills/adopter/**`: new files under a gate folder) ·
`checks-weakened-approved` not expected: no test is removed or changed.
Needs merged: PR 5 (brief 005). The skill copies from a render, and after PR 5 a render holds no
record of the kit; PR 5 also numbers the roadmap's units. Once it is on `main`, bring this branch
up to date (`git merge origin/main`) before the first test: the criteria use brief 005's fixture
and manifest.
Size: about 650 added lines — a skill of at most 200 lines, three reference files, one test
module, a decision record. This brief is longer than one screen: it carries the rules the skill
has to hold.

## Context
The kit starts new projects. `kit.py init` runs only in a copy of the kit, and `kit.py render
--into` writes into a folder without looking at what is there: in a scratch clone of an existing
repository on 2026-10-10 it replaced that repository's `README.md`, `.gitignore` and
`.github/workflows/ci.yml`. The gates are Python's (`make check` runs ruff, basedpyright,
import-linter and pytest), so a repository in another language cannot take the kit. `docs/BACKLOG.md`
holds the row "Non-Python variants … when a non-Python project wants the kit"; one does now.

The maintainer decided on 2026-10-10:
- Adoption is a skill an agent runs in the repository, not a command and not templates for a
  second language: "instead of hardcoding the migration, we can have a brief that an agent can run
  and set up even an existing repo to adhere to the philosophy", so that nothing existing is
  written over and what can be added is added. The skill is built in the kit, and the maintainer
  carries its folder into a repository by hand.
- One adoption first, the general mechanism later: an adopted repository takes no `kit.py update`
  yet.
- Two steps: the process first; then the gates the repository lacks, each as a brief through the
  loop the first step installed.
- The skill is run once before it merges, on a scratch clone of a repository of the maintainer's.

## Objective
A kit-only skill, `adopter`, that a session runs in an existing repository of any language: it
copies the kit's process from a render made with that repository's answers, never over a file that
exists, wires `make check` to the checks the repository already has, shows what it installed going
red, and lists each gate the repository lacks as a unit of its roadmap. A table in the skill gives
every file of a rendered project one of four classes, and a test keeps the table complete.

## Out of scope — do not do these
- No `kit.py adopt`, no change to `init`, `render` or `update`, no contract between the kit and a
  language, no templates for another language.
- The skill names no tool of any language but the kit's own. A tool for the target is chosen in
  the target, from documentation read that day and written into a dated note there.
- The skill builds none of the gates the target lacks, fixes no product code and no red check.
- No line in `AGENTS.md`'s "Roles" and no copy in a project made by `init`: the skill has nothing
  to do there.
- `tests/harness/**` is not carried into a target.
- `make prove` (brief 007) and the rehearsal of the kit itself (brief 008).

## Inputs
- `.claude/skills/brief-writer/` and `.claude/skills/implementer/` — the shape of a role skill:
  frontmatter, numbered rules, `references/rules.md`, "How this role ends"; and
  `brief-writer/references/decisions.md` for how a decision is put to the maintainer.
- `scripts/roles.py` (an id is one capital letter, a dash, two digits) and
  `tests/harness/test_role_skills.py` lines 54–160 (the structural tests of a role skill).
- `kit.py`: `KIT_ONLY_FIRST`, `category()`, `render_tree`, `render_command`;
  `test_every_tracked_file_has_an_owner` in `tests/harness/test_kit.py` as the model for the table
  test; `tests/harness/test_stateless.py` (brief 005) for a fixture that renders a project.
- `docs/kit/HARNESS.md` (the gates table, the hooks) for `references/gates.md`.
- `scripts/stop_gate.py`, `scripts/guard_bash.py`, `scripts/fmt_hook.py`, `scripts/integrity.py`,
  `.claude/settings.json`, `.github/workflows/ci.yml`, `Makefile`, `.pre-commit-config.yaml` — to
  tell, file by file, the kit's process from Python's.
- `claude_argv` in `scripts/review.py` (how the kit starts a headless process) and the research
  notes on hooks (2026-10-03) and on role skills in a headless run (2026-10-08).
- Checked on 2026-10-10 at `9458f4f`, each by the command or the line named:
  - In a folder with no Python project, `uv run python scripts/review.py --help`,
    `uv run python .claude/skills/implementer/scripts/pr.py --help` and
    `uv run --project "$PWD" python -c "print(1)"` (the form of the three hook commands in
    `.claude/settings.json`) exit 0. `review.py`, `roles.py`, `pr.py`, `guard_bash.py`,
    `stop_gate.py` and `fmt_hook.py` import the standard library only.
  - `scripts/integrity.py` imports pytest (line 43) and exits 1 without it, which CI's `integrity`
    job reads as "a check was weakened".
  - `scripts/stop_gate.py:33` gates `src/`, `tests/`, `scripts/`; `scripts/guard_bash.py:66-90`
    lists Python tools' files as gate files; `scripts/fmt_hook.py` formats `.py` files with ruff;
    12 of the 64 permission rules in `.claude/settings.json` name a Python tool.
  - `python3 kit.py render --package myapp --base work --branch-prefix work --maintainer "Ada
    Lovelace" --into <folder>` writes 72 files and a `kit.lock` whose `commit` is empty.
  - A hook edited in a settings file reaches the running session (the note on hooks, "Not
    snapshotted at session start").
  - `scripts/stop_gate.py` (`_gate`, lines 115–123) exits 2, which blocks the stop, when it finds
    neither `origin/<base>` nor `<base>`.
  - `B`, `C`, `I` and `P` are the rule letters in use; `A` is free.
  - Not checked: whether `--permission-mode auto` lets a headless session write files and run a
    repository's own check commands in a scratch clone; what such a run costs.

## Interface
- `.claude/skills/adopter/`: `SKILL.md`, `references/rules.md`, `references/pieces.md`,
  `references/gates.md`. Kit-only: `.claude/skills/adopter/*` and `tests/harness/test_adopter.py`
  stand in `KIT_ONLY_FIRST`. Started in the repository to adopt as `/adopter <path of a clone of
  the kit> [<ref>]`; rule ids `A-01` onwards.
- The skill assumes nothing of the kit in the target: no `AGENTS.md`, no `scripts/`, no `make`
  target, no Python project. It needs `git` and `uv`, and says so first.
- `references/pieces.md`: one table, `| pattern | class | note |`, with patterns read as `kit.py`
  reads its manifest (fnmatch over repository-relative paths). Every file of a rendered project
  matches exactly one row. The classes:
  - `as rendered` — copied from the render unchanged: it runs, or reads true, in a repository
    with no Python project;
  - `adapt` — copied from the render and then changed for the target, each change a line in the
    target's `docs/DELTAS.md`;
  - `per stack` — not copied: the target's own equivalent is written (in this step, `make check`
    and nothing else) or is a gate the target lacks;
  - `leave out` — the kit's own or Python's own, and nothing takes its place.
- `references/gates.md`: one entry per row of `HARNESS.md`'s gates table — what the gate
  guarantees, how it is shown red on a planted defect, how the kit does it for Python. The
  target's roadmap units are written from it.
- The steps of `SKILL.md`, in this order: orient, read-only, and run the target's own checks once
  (the baseline) · ask the maintainer (base branch for units, branch prefix, name; each collision;
  which existing commands make up `make check`) · clone the kit at the ref into a scratch folder,
  render from that clone with those answers, and note that clone's commit (`render` reads the
  tree it runs in and asks for a `--package`: any identifier does, since `src/` is left out) ·
  place the pieces on a branch made for the adoption · wire the gate and the hooks · show it red · record · hand over.
- The rules the skill holds, each numbered in its text and in `references/rules.md`:
  1. A path that exists is never written over. A collision is put to the maintainer (place the
     kit's file beside it under another name · leave it out · the maintainer merges by hand);
     until it is answered, the file is left out and listed.
  2. Files come from the render, never from the kit's tree, and a file is placed only as its
     class in the table says.
  3. `make check` runs the checks the target already has, by the commands its CI or its package
     scripts use, and nothing the adopter made up. What is red in the baseline stays out of
     `make check` as the smallest unit the target's own runner can name (one test file, one
     package of a workspace whose test command runs per package) and everything else stays in;
     it is named first in the report and is the first unit of the roadmap.
  4. The Stop gate fires on the paths where the target's code is, and the guard's gate files are
     the target's own configuration files: both are adaptations, and both are listed.
  5. `.claude/settings.json` is written last, because a hook edited there reaches the session
     that is doing the adoption; and the base branch exists in the clone before it is written,
     because the Stop gate blocks while it finds no base.
  6. A tool is named only after its documentation was read that day and a dated note written in
     the target's `docs/research/`.
  7. What was installed is shown working in the target before the report: the guard refusing a
     push to the base branch; the Stop gate holding on a planted failing check and letting go
     without it; `make check` red on a defect planted for each command it runs. What cannot be
     shown on the machine (the CI jobs) is listed as not proven.
  8. Every command that a copied skill or document names (`uv run python scripts/integrity.py`,
     `make mutate`, …) works in the target, or stands in `docs/DELTAS.md` with what replaces it,
     or that nothing does yet.
  9. Each gate of `references/gates.md` that the target lacks is one unit in `docs/ROADMAP.md`.
  10. `docs/DELTAS.md` holds the kit's commit, the answers, every adaptation, every collision
      with its ruling, and everything left out.
  11. Nothing leaves the machine before the maintainer says so: the push, the labels and the
      pull request come after the report. Answers given when the skill is started are not asked
      again; in a run with nobody to ask, what is still open is left out and listed, and the
      skill ends at the report.
- `docs/decisions/0011-adoption-is-a-skill-an-agent-runs.md`: the maintainer's four decisions as
  under "Context". Recorded as the planning session's choices, not the maintainer's: the skill is
  kit-only; the table is over a rendered project and has these four classes; rules 3 (a red check
  stays out), 5 and 11; `kit.py` and `kit.lock` are left out and the kit's commit stands in
  `docs/DELTAS.md`; the rehearsal's model and cap.

## Acceptance criteria — concrete cases; write them as failing tests first
In `tests/harness/test_adopter.py`, with `piece_class(path: str) -> str` reading the table:
1. With the kit rendered (package `acme`, maintainer `Ada Lovelace`), every file of the rendered
   tree has exactly one row, every row matches at least one file, and every class is one of the
   four. The edges: a table with a second row that also matches `scripts/review.py` fails and
   names both rows; a row `docs/gone/*` fails and is named
   (`test_every_file_of_a_project_has_one_class`).
2. `scripts/review.py`, `scripts/roles.py`, `.claude/skills/implementer/scripts/pr.py` and
   `docs/kit/PHILOSOPHY.md` are `as rendered`; `scripts/stop_gate.py`, `scripts/guard_bash.py`,
   `.claude/settings.json`, `.github/workflows/ci.yml` and `AGENTS.md` are `adapt`;
   `scripts/integrity.py`, `scripts/fmt_hook.py` and `Makefile` are `per stack`; `pyproject.toml`,
   `uv.lock`, `kit.py`, `kit.lock`, `README.md`, `src/acme/core/text.py` and
   `tests/harness/test_review.py` are `leave out` (`test_the_classes_of_the_files_that_were_checked`).
3. `kit.category(".claude/skills/adopter/SKILL.md")` and
   `kit.category("tests/harness/test_adopter.py")` are `kit-only`, and the rendered tree holds no
   path under `.claude/skills/adopter/`. The edge: `.claude/skills/implementer/SKILL.md` is still
   `kit-owned` — the new pattern stands before `.claude/*` and takes one folder only
   (`test_the_adopter_stays_in_the_kit`).
4. The structural tests of a role skill hold for `adopter`: a name and a description of over 100
   characters, at most 200 lines, the last heading "How this role ends" with its three states,
   every bundled file named in backticks, no `ALWAYS`, `NEVER` or `MUST`, nothing of this
   repository's history, no pronoun for the maintainer, no dollar sign followed by a digit
   (`test_the_adopter_is_a_role_skill`, calling the checks of `test_role_skills.py`).
5. `uv run python scripts/roles.py` exits 0 and lists at least eleven `A-` rules, and
   `references/rules.md` has a row for each rule under "Interface"
   (`test_the_adopters_rules_are_numbered`).

The rehearsal: one run, which no test can replace. The target is a scratch clone of a repository
the maintainer names; ask for its path once, before the run. After the run:
- R1. `git diff --name-status "$START"..HEAD` in the target shows `A` lines only, and `git status
  --short` shows nothing but the skill's own folder: no file that existed was changed or deleted.
- R2. `make check` in the target runs the target's own commands and every test that was green
  in the baseline. What was red is left out as one file or one package, never as the whole test
  command, and is the first line of the report.
- R3. The guard in the target refuses a push to the base branch with exit code 2.
- R4. The report lists every collision, and the files placed, adapted and left out add up to the
  files of the render.
- R5. The target has no remote, and the run's record holds no `git push` and no `gh` call that
  writes.

Also: `README.md` "Quick start" gains "An existing repository" (copy `.claude/skills/adopter/`
into it, start a session there, `/adopter <path of a clone of the kit>`); `CHANGELOG.md`
("Unreleased"); `docs/ROADMAP.md` gains this unit as 2d; the "Non-Python variants" row of
`docs/BACKLOG.md` reads `→ roadmap`.

A criterion a trivial test could satisfy is not a criterion. Existing tests may not be removed,
skipped or weakened, and no escape-hatch comment added: CI job `integrity` lists it; if a test is
genuinely wrong, say so in the PR and the maintainer labels it `checks-weakened-approved`.
Gates: `make check` green; `make mutate` not applicable (nothing under `src/kitpkg/core` changes).
Check by hand: the maintainer opens the adopted clone the page names (`git log --stat
"$START"..`, `docs/DELTAS.md`, `docs/ROADMAP.md`, the report); and reads `SKILL.md` once as a
session would that has never seen the kit: does each step say what to do when the repository is
not as the step expects?

## Proofs — in the proofs comment, not in the description
- The failing-test output **before** the implementation (red), and what made it red.
- `make check` output **after** (green), with its exit code.
- A types proof must be one only strict mode rejects (an unannotated parameter), not one every
  mode rejects.
- The rehearsal. `$W` is the work folder outside the repository; `$R` is not under the proofs
  folder, which is posted whole.
  ```
  R="$W/rehearsal"; T="$R/target"; K="$(git rev-parse --show-toplevel)"
  git clone -q <the path the maintainer gave> "$T" && git -C "$T" remote remove origin
  START="$(git -C "$T" rev-parse HEAD)"; git -C "$T" remote -v
  mkdir -p "$T/.claude/skills" && cp -R "$K/.claude/skills/adopter" "$T/.claude/skills/"
  echo ".claude/skills/adopter/" >> "$T/.git/info/exclude"
  cd "$T" && claude -p "/adopter $K (nobody can be asked in this run: package target, base branch work, branch prefix work, the maintainer's name stays the maintainer)" \
    --model sonnet --effort medium --permission-mode auto --permission-prompts none \
    --strict-mcp-config --max-budget-usd 5 --output-format stream-json --verbose > "$R/run.jsonl"
  git -C "$T" diff --name-status "$START"..HEAD | cut -c1 | sort | uniq -c
  printf '%s' '{"tool_name":"Bash","tool_input":{"command":"git push origin work"}}' | uv run python scripts/guard_bash.py; echo "exit code: $?"
  ```
  Run on this branch on 2026-10-10: the clone, the removal of the remote (`git remote -v` prints
  nothing) and the `diff` line, against a scratch clone; and the guard line in the kit's own tree
  with `main` for `work`, which prints "git push refused" and exit code 2. Not run: the `cp` and
  the `claude` line, which need the skill; its flags are in `claude --help` of 2.1.296.
- One run. If it ends without a report (the cap, a refusal, a crash), put the record's last
  result line under "Not proven", fix what the record shows, and ask the maintainer before a
  second run.
- The target is not this repository's: nothing of its content goes on this pull request. `$R`
  stays on the machine and the page names its path for the maintainer. The proofs comment gets one
  file with numbers only: files placed, adapted and left out, collisions, the letters of R1, the
  exit codes of R2 and R3, the run's cost and time.

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
The skill is read by a session that has never seen the kit and stands in a repository that is
nothing like it. A sentence that says "the Makefile", "the tests folder" or "the package" assumes
the kit's layout: say what to look for instead, and what to do when it is not there. And the
rehearsal's target is real and is not ours: its remote is removed before the run, and nothing of
it is posted.

Brief written in session b4ea0b41-c867-4aa6-b5e6-2f20b4ea5742
