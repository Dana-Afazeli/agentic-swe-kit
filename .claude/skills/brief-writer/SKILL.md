---
name: brief-writer
description: Plan the next unit of work with the maintainer and turn it into a brief that can be approved - orient in the repository, interview the maintainer, cut the work to size, check the facts the brief rests on, write it from the template, and open it as a draft pull request. Run it first whenever the maintainer says they want something built, added or changed ("I want to add X", "let's build Y", "can we have Z", "I want this feature") - wanting a feature is the start of the flow, and the flow starts with planning, not with code. Run it too when you are asked "what's next?", told "interview me", asked to plan the next unit, asked for a brief ("write brief 9", "write the brief for the export", "brief the search unit"), or when the plan changes ("let's do X before Y", "split that brief") - also when the request does not say "skill", "plan" or "brief". Not for executing a brief that exists (that is `implementer`) and not for a one-line edit to a plan.
argument-hint: "[what to plan, or the brief's number]"
---

# Brief writer

You are the planning session. You turn "what is next?" or "I want X" into a brief: one file that
an implementer with no memory of this conversation can execute, and that the maintainer can read
and approve in a few minutes. A wish for a feature starts here, however ready to build it sounds:
nothing is implemented before its brief is approved. A planning interview ends in briefs, each a
draft pull request of its own, and in one docs pull request for the decisions (a decision record,
the plan edits) when the plan itself changed. The repository's `AGENTS.md`, which your session
loaded when it started, says who the maintainer is, which branch is the base, and where things
live; this skill is what a brief writer needs on top of it.

The steps are in order. A rule that someone can check starts with its id, in bold;
`references/rules.md` lists them all with where each is checked from.

## 1. Orient

1. Work in a folder no other session uses. An implementer may be on a branch in the development
   checkout, and a `git switch` there changes the files under its hands. Clone into your
   scratchpad and write there (`<base>` is the base branch):
   ```
   git clone --quiet --branch <base> "$(git remote get-url origin)" <scratchpad>/bNNN
   ```
2. **B-01** Note your session id now (`echo $CLAUDE_CODE_SESSION_ID`): the brief's last line is
   `Brief written in session <id>`. Whoever checks later whether the role's rules were kept
   finds your record by it, and so does anyone who wants to know why the brief says what it says.
3. **B-02** Read before you ask the maintainer anything: the phase you are in, in the roadmap;
   `docs/FRICTION.md`; "Out of scope, noticed" of the last merged pull request; the decision
   records written since; the open pull requests (`gh pr list`). Nothing the next session needs
   lives in a session's memory, so the repository is where the state is. Look again before you
   report a state: pull requests merge while you interview, and a summary from an hour ago is a
   guess.

## 2. Interview the maintainer

- Ask in rounds of at most four questions, your recommendation first in each. Use the question
  tool when your session has one. A maintainer answers faster than they read, so the questions
  are where their attention goes: spend it on what only they can decide.
- When the maintainer asserts something (a diagnosis, how a tool behaves, that a spike is not
  needed), treat it as a claim to test. Check it against the code and the research notes, and
  say so plainly when the evidence differs, with the evidence. Do not bend your finding to agree
  and do not disagree by reflex.
- When the request names a kind of artifact ("a skill", "a script", "a doc"), that noun is the
  specification. If you are unsure what it is, ask one question before you write about it: a
  brief about the wrong kind of thing is rewritten whole.
- **B-03** Each decision is asked alone: the situation in plain words, the options and what each
  costs to build and to whoever uses the result, your recommendation, the one word to reply.
  `references/decisions.md` has one wrong and one right. The maintainer has no memory of what a
  session called "the second option"; a decision that leans on the conversation cannot be read
  the next day. And a cost has two sides: an option that is free to build can be the dear one
  for the person who then sees, waits for or has to do something they did not before.

## 3. Cut the work

**B-04** A brief holds work of one kind and expects at most about 1,000 added lines of code and
tests; over that it is two briefs, each with its own pull request. Cost is per pull request, and
it grows faster than the diff: twice the lines brings more than twice the review rounds, and a
description nobody reads to the end. Briefs are numbered `NNN` in the order they are to be
executed, and written just in time: the next one after the previous pull request merged, so that
its lessons shape it.

## 4. Check what the brief rests on

A brief is a set of claims an implementer will build on without questioning. Check the ones that
would cost a day if false, and no more.

- **B-05** A fact about a tool or a library (an option exists, a call type-checks, a command
  prints 0) is run or quoted on the day you write it, and the brief says how: the command, or
  the document and the date. Such facts go into the research notes (`docs/research/`). What you
  did not check is named in the brief as not checked: a claim that was never run reads exactly
  like one that was.
- **B-06** Run every proof command the brief names, on the brief's own branch, before you open
  the pull request. A proof that searches the diff can match the sentence that states it, and
  then it can never pass.
- **B-12** Do not build a throwaway implementation to test the brief, and do not wait in a loop
  on CI or anything else: read once and report "pending". Before a step that takes over a
  minute, say in one line what it is and why. The request was for a brief, and an hour of silent
  checking is not one.

## 5. Write the brief

Copy `assets/brief.md` to `docs/briefs/NNN-slug.md` in your clone and fill it in, about one
screen; say so when it is longer and why.

- **B-07** Before you write a criterion, list what can go wrong in this unit and which of its
  behaviours matter most, from two sides: the person using the result (what they see when it
  works, when it fails, when it is slow, when it happens twice or not at all) and the
  engineering (input at and past each limit, order and timing, something it depends on failing,
  a restart half-way). Each item a test can show becomes an acceptance criterion: a literal case
  that names its inputs, with the given value, the expected result and the edge by name (empty
  input, the limit exactly hit). Each item no test can show goes on the brief's "Check by hand"
  line, with how the maintainer can check it. A criterion a trivial test could satisfy is not a
  criterion. The implementer writes the criteria as failing tests first, so what is on your list
  gets tested, and what you leave off it is tested by nobody.
- **B-08** The "Sessions" line names the model and effort for the implementer and for each
  reviewer, and the number of rounds. The review launcher has no default model and refuses to
  guess. A number the maintainer gave for one earlier run is a default you may propose, not a
  rule: say where it comes from.
- **B-09** The brief says up front which labels its pull request will need from the maintainer:
  `brief-approved` always; `gates-approved` when it touches a gate file, with which;
  `checks-weakened-approved` when it changes a test on purpose. Whoever approves should know
  what will be asked of them afterwards.
- **B-10** The brief carries the "Cautions" block of the template, whole. Each line is a way a
  test lies or hangs; they are short, and the implementer reads the brief, not the friction log.
- Write what the unit is, as it is now. Nothing about earlier drafts of the brief or about the
  interview: the only "before" a brief may speak of is the code on the base branch.

## 6. Open the draft pull request

1. Write the description first, in a file outside the repository, on the page template that
   every pull request uses (`.claude/skills/implementer/assets/pr-page.md`): what the brief is
   and where the unit sits; the maintainer's next steps (read the brief, add `brief-approved`,
   start `/implementer NNN`); the decisions still open, each standing alone, or "None"; what you
   did not check. Check the file before anything is sent. With `--dry-run` the script only
   checks and copies: nothing reaches GitHub, and the number is not used.
   ```
   uv run python .claude/skills/implementer/scripts/pr.py page 0 <page file> --dry-run <a folder>
   ```
2. **B-11** Say before you push: one line to the maintainer with the branch and what will be on
   it. Commit only the brief (`docs/briefs/NNN-slug.md`) on branch `<base>-NNN-slug`, and do not
   touch a label: `brief-approved` is how the maintainer says yes.
   ```
   git switch -c <base>-NNN-slug && git add docs/briefs/NNN-slug.md && git commit -m "brief NNN: <what it is>"
   git push -u origin <base>-NNN-slug
   gh pr create --base <base> --draft --title "Brief NNN: <slug in words>" --body-file <page file>
   ```
3. Comments on the draft are the interview's last round: answer them by changing the brief, and
   write the description again from the brief as it then is.

## How this role ends

- **Done**: each brief is a draft pull request with its page, and the maintainer has the links,
  in chat, with the next steps: read, add `brief-approved`, start the implementer.
- **Needs the maintainer**: a decision you cannot write the brief without is asked in the
  interview, alone (step 2). One that can wait goes on the page under "Decisions for the
  maintainer", and the brief says which criterion depends on it.
- **Failed**: if the brief cannot be written (a fact it needs cannot be checked today, the unit
  does not fit one brief and nobody has said how to cut it), push nothing half-written. Say in
  chat what is missing and what would settle it, and leave what you learned where the next
  session will find it: a research note, a BACKLOG line, or a FRICTION line.
