---
name: implementer
description: Take one brief from its first line to a pull request that is ready for the maintainer - check the approval, build each behaviour test-first, keep inside the brief, show the work as the page the maintainer reads and a proofs comment, and hand over to the review loop. Run it first, before reading or changing anything, whenever you are asked to execute, implement, build or continue a brief or its pull request - "/implementer 008", "execute brief 008", "implement the brief", "implement PR 16", "continue brief 008", "pick up where the last session stopped on 008" - also when the request does not say "skill".
argument-hint: "<brief number NNN>"
---

# Implementer

You take one brief from its first line to a pull request that the maintainer can read in five
minutes and merge. The brief is the whole of your task: the maintainer read it and approved it,
and nothing else was approved. The repository's `AGENTS.md`, which your session loaded when it
started, says who the maintainer is and which branch is the base; this skill is what an
implementer needs on top of it.

The steps are in order. A rule that someone can check starts with its id, in bold;
`references/rules.md` lists them all with where each is checked from.

## 1. Start

1. **I-01** This skill comes first: before the session reads the code, plans or answers. If you
   got here late, having read, planned or changed something for this brief already, say so to
   the maintainer and take the steps from here in order all the same: the approval check (I-02)
   comes before any change. What goes wrong without the skill (work on an unapproved brief,
   proofs retyped, a page nobody can read) is found a day later.
2. Find the brief's branch and pull request. `NNN` is the argument and `<base>` the base branch;
   given a PR number instead, start from the third command.
   ```
   git fetch
   git branch -r --list 'origin/<base>-NNN-*'        # one branch: <base>-NNN-slug
   gh pr list --head <base>-NNN-slug --json number,isDraft,labels
   ```
3. **I-02** The PR carries the label `brief-approved`, or you stop: post one comment on the PR
   saying that an implementer is waiting for the label, tell the maintainer, and change nothing.
   A brief can say it was approved when its PR was not, and labels are the maintainer's.
4. Switch to the brief's branch, in a folder no other session is working in. Read the brief in
   full, then every comment on the PR (`gh api repos/<o>/<r>/issues/<n>/comments`): the planning
   session leaves corrections there. Do what the brief's first lines say; if it names a pull
   request that has to be merged first and it is not, tell the maintainer at once and go on with
   what does not depend on it.
5. Make a folder for your work outside the repository, with a folder for the proofs inside it,
   and save a first `make check`, so that you know the gate was green before you touched
   anything:
   ```
   W="${TMPDIR:-/tmp}/work/pr-<n>"; P="$W/proofs"; mkdir -p "$P"
   make check > "$W/baseline.txt" 2>&1; echo "exit code: $?" >> "$W/baseline.txt"
   ```
   Save every output in that shape: in zsh, `cmd | tee f; echo $?` reports `tee`, not `cmd`.
   `$P` is posted whole in step 4, every file of it, so only proofs go there. What is your own
   (this baseline, your notes) stays in `$W`.

## 2. Build, one behaviour at a time

Before the first test, write down in `$W` what can go wrong in this unit and which of its
behaviours matter most. Start from the brief's criteria and its "Check by hand" line, and
add what the code shows and the brief's writer could not see, from two sides: the person using
the result (what they see when it works, fails, is slow, happens twice or not at all) and the
engineering (input at and past each limit, order and timing, something it depends on failing, a
restart half-way). Each case a test can show gets a test, with the criterion it belongs to. Each
case no test can show goes on the page under "Not proven", with how the maintainer can check it
by hand, and as one of the maintainer's steps when it has to be looked at before the merge. A
case that needs behaviour the brief does not ask for is a BACKLOG line (I-07). The brief writer
made the same list without the code in front of them; yours is the second and last look.

Take the acceptance criteria one by one. For each:

1. **I-03** Write the failing test first, from the criterion's literal case. Run it, save the
   output, and read why it is red: the failure message has to name the missing behaviour. A test
   that is red for another reason (a fake that is too slow, a typo, an import) proves nothing,
   and passes for a red proof all the same.
2. Write the smallest code that makes it pass.
3. Refactor with the tests green.

When the last criterion is in:

4. **I-04** `make check` is green after your last change, saved with its exit code. The Stop hook
   runs it too and keeps you from stopping on a red gate: fix the cause, do not look for a way
   round.
5. **I-05** No test is removed, skipped, marked `xfail` or weakened, and no comment switches a
   check off (`# noqa`, `# type: ignore`, `# pyright: ignore`, `# pragma: no cover`,
   `# pragma: no mutate`), to get to green or for any other reason. A renamed test counts as a
   removed one. If you think a test is wrong, or an escape hatch justified, the decision is the
   maintainer's: leave the test as it is and ask (step 3). On a yes, make the change and list it
   on the page under "Checks weakened" with the reason. CI's job `integrity` stays red until the
   maintainer adds `checks-weakened-approved`; the Stop hook does not look, so run
   `uv run python scripts/integrity.py --base origin/<base>` yourself before `gh pr ready`.
6. **I-06** `make mutate MUTANTS="<package>.<module>.*"` for each module you touched that the
   mutation gate covers (`AGENTS.md` says which), and whenever the brief names it. A surviving
   mutant means a missing case or code to restructure, not a pragma.

Two things from the same family: the type checker stays strict, and no threshold (coverage,
mutation, types) is lowered in a feature PR; in CI shell, `|| true` goes only on a filter such as
`grep`, because on the command that gathers the input a failure would read as "nothing changed".

## 3. Notice

- **I-07** Stay inside the brief. What else you notice (a bug next door, a better design, a doc
  that is wrong) is one line in `docs/BACKLOG.md`, not a change: the maintainer approved this
  brief, and every unasked line is review nobody planned for. The one way past the brief is the
  maintainer's own yes to something it does not ask for, said in chat or in a comment. Then do
  it, list it on the page under "Where this differs from the brief" with the maintainer's words
  quoted and where they were said, and add a step that asks for the label `scope-approved`: the
  label is how that yes gets onto the pull request, where the conformance reviewer looks for
  it. A yes you worked out for yourself is not one. If the brief cannot be met as
  written (a criterion contradicts an existing test or another criterion), stop and ask the
  maintainer on the PR before you change or delete anything. First find how far the
  contradiction reaches: put the change in place, run the whole gate once (`make check`, not the
  one test file), save the output, and take the change out again. Your question names every
  test it breaks. A question built on the first file that fails names half of them, and
  recommends a change that meets the other half next.
- **I-08** When something went wrong, was slow or confused you, append a line to
  `docs/FRICTION.md` then, while you still know the figures:
  `date | kind | what happened | what would have caught it | → outcome`. These lines are what
  the next brief and the next version of this skill are written from.

## 4. Show

What you show is two things, and they are kept apart so that the maintainer's part stays short.

1. **I-09** The proofs go in one PR comment, built from your saved files:
   ```
   uv run python .claude/skills/implementer/scripts/pr.py proofs <n> "$P"
   ```
   `scripts/pr.py` puts each file in a collapsed block, word for word. Never retype output; when
   a file is too long, cut it yourself and mark every cut with `[…]`. Keep in the folder the
   proofs the brief names and nothing else: the red run of each criterion and what made it red,
   the last green `make check` with its exit code, the brief's own proofs. No proof goes in the
   description: evidence there buries the part the maintainer has to read.
2. **I-10** The description is the page. Copy `assets/pr-page.md` to a file outside the
   repository, fill it in, and set it:
   ```
   uv run python .claude/skills/implementer/scripts/pr.py page <n> <file>
   ```
   Above the reference line the page has at most 80 lines and is written for someone who has
   never seen this repository or your session; below it is what the reviewers check. It says
   what the pull request is at its head, and nothing about its earlier versions or the
   conversation that shaped it. `references/page.md` has one filled page and three mistakes to
   avoid. The script refuses a page that is too long, has a part missing or with nothing under
   it, or still holds a comment of the template; fix the page, not the script. It checks the
   page's shape and not its words: whether the page can be read cold is yours to get right, and
   the conformance reviewer's to judge.
3. **I-11** Rebuild the page, and post the proofs again, at each push that changes the diff. The
   conformance reviewer reads both in every round, and a page that describes the last push but
   one is reported as a mismatch.
4. **I-12** A decision you put to the maintainer names the command or the run that checked each
   fact it rests on, and you run the case the decision is about before you describe it. Record
   what the maintainer said and what you added as two things: a field you chose in order to
   answer a question is yours, not "decided by the maintainer". A decision described from a
   reviewer's scenario, and not from a run, gets answered on a false picture.
5. Mark the PR ready when the brief's criteria are met and the gate is green: read every comment
   on the PR once more, run the integrity script, then `gh pr ready <n>`. Add `--dry-run <folder>`
   to either `pr.py` command to write the result into a folder and send nothing.

## 5. Hand over to the review loop

Run the `review-loop` skill on the PR, with the reviewers, models, efforts and rounds the brief's
"Sessions" line names, or the ones the maintainer gave you. It is the last step of this role and
its rules are yours: read every comment before each push (I-13), fix the kind and not the case
(I-14), reproduce a finding before changing anything (I-15), resolve a thread only when you saw
its fix work at the pushed head (I-16), and end with the closing comment, which says what the
page says (I-17). Do not merge, and do not touch a label.

You start the reviewers; you are never one of them. Each review is done by a process of its own,
which the launcher starts in a fresh clone of the pushed branch: it has not seen your session,
and all it knows of your work is what is on the pull request. That is what makes its verdict
worth having. A review done inside your session, by you or by an agent you brief, is not a
review, whatever it finds.

## How this role ends

- **Done**: the PR is ready, the loop is closed or stopped with its closing comment, and the page
  is current. Report to the maintainer in chat in the page's order, shorter: what the unit is,
  the next steps, the decisions, what is not proven, and the link.
- **Needs the maintainer**: say what you need in the place where it will be read. A decision
  goes on the page under "Decisions for the maintainer", standing alone; an action (a label, a
  check by hand, a merge that has to come first) under "Next steps for the maintainer" with what
  it unblocks; something that blocks you now, such as a missing `brief-approved` or a brief that
  contradicts itself, also as a PR comment and in chat. Go on with whatever does not depend on
  the answer.
- **Failed**: when you cannot finish, leave the next session a place to start. Commit and push
  what is green on the brief's branch, never a red gate. Add the FRICTION line. Set the page
  with "Next steps for the maintainer" saying where the work stopped, and post a PR comment that
  names the criteria that are met, the one you were on, and what you would try next.
