---
name: review-loop
description: Run the review-and-fix loop on a pull request of this repository. One command starts plan-reviewer and the bundled /code-review as separate processes, each on a named model and effort; then validate every finding by reproducing it, fix with TDD, answer on the PR, and run the command again until both are green or the rounds are used. Use it when a PR is ready for review, when the maintainer asks to run the reviewers, to loop reviews until green, to fix review comments, to re-review after fixes, or asks for a code review on a named model or effort.
argument-hint: "<pr> [--code MODEL/EFFORT] [--plan MODEL/EFFORT] [--rounds N]"
---

# Review loop

A reviewer's finding is a hypothesis: it earns a change only after you have reproduced it. The loop
ends when both reviewers are green, when the rounds are used, or when what is left needs the maintainer.
Follow `AGENTS.md` throughout.

## 1. Run the reviewers: one command

```
uv run python scripts/review.py <pr>
```

Run it with the Bash tool and `run_in_background: true`. It returns within the two reviewers' time
limits, 28 minutes together, plus the seconds it takes to make their clones.

Each reviewer works in a clone of its own, of the PR's branch as GitHub has it, made for the run
and removed after it. So the reviewers see what is pushed and nothing else, and what happens in
this checkout while they run does not reach them: you may go on working.

Before the call: the work is committed and pushed, and `make check` is green. On the PR's branch
the command refuses to start with a head that is not pushed or a tree that is not clean, because
the review would not see that work.

The model and effort of each reviewer come from the brief's "Sessions:" line, or from what the maintainer
said; pass them exactly. There is no default: the command refuses to start a reviewer whose model
and effort were not named. If neither the brief nor the maintainer named them, ask the maintainer; do not pick.

| Option | What it sets |
|---|---|
| `--code MODEL/EFFORT` | the bundled `/code-review`; the effort is also its review level. Needed when it runs |
| `--plan MODEL/EFFORT` | `plan-reviewer`, conformance to the brief. Needed when it runs |
| `--rounds N` | how many rounds each reviewer may use; 3 when not named |
| `--only plan`, `--only code` | one reviewer; a PR that has no brief takes `--only code` |
| `--expire REVIEWER` | that reviewer's green no longer counts, because the commits since changed what it reviewed (your judgment; see `GREEN` below) |

Models: `sonnet`, `opus`, `fable`, or a full model name. Efforts: `low`, `medium`, `high`, `xhigh`,
`max`. Before the first call, tell the maintainer in one line what will run: the reviewers, the model and
effort of each, the number of rounds.

The command works out the rest: which reviewers still have to run (not green, rounds left), the
round number, the brief (`docs/briefs/NNN-*.md`, from the branch name), what each reviewer is told,
its spending cap and time limit, and the record comment posted on the PR for each run. Use the same
command with the same options in every round.

Do not start the reviewers any other way. Through the Skill tool, `/code-review` answers on the
project's pinned subagent model whatever you ask for, and a hand-briefed agent is not the code
review (`docs/kit/research/2026-10-05-review-model-and-effort.md`).

### Reading what it prints

```
code-review · round 1 · FINDINGS 3
  asked opus/xhigh · answered claude-opus-5-5 x41 · $1.84 · 412 s · advisor calls 0 · denied tool calls 0
  inline comments added: 3
  record: <link to the record comment on the PR>
  report: <path>/code-round-1/report.md

next: validate each finding by reproducing it, ...
```

(The figures above only show the layout.)

- `GREEN`: nothing raised. That reviewer is not run again while its green stands. When commits
  land after it, the command says `the head has moved since` and lists the files changed since
  that green. **Whether the green still stands is your decision, each round:** if those commits
  changed what that reviewer reviewed, or anything that affects it (code it reviewed, a test it
  relied on, the skill or the docs it checked, a brief), the green is expired: pass
  `--expire <reviewer>` and it runs again. If the commits touched nothing it reviewed, say so in
  one line and go on. Decide from the list of files and the diff, not from the file names alone.
- `FINDINGS n`: go to step 2. The code review's findings are inline comments on the PR;
  plan-reviewer's are in its record comment. `report.md` holds the same text.
- `NO VERDICT`: the reviewer did not end with a verdict line. Read the report and treat what it
  says as findings.
- `FAILED`: the `problem:` line says why: the time limit, the spending cap, the process died, or
  the reviewer left the PR's head in its clone. A failed run uses a round. Do what the `next:` line
  says.
- `warning:` the reviewer left changes in its clone. Nothing is harmed, the clone is gone; the
  record comment says it too. Mention it in the report to the maintainer.
- `answered` is read from the run's record, not from what was asked. Quote that line when you
  report which model ran; never write the model from memory.
- `denied tool calls` above 0: the reviewer tried something it may not do. The `denied:` lines say
  what; mention it in the report to the maintainer.
- The `next:` line is the instruction for what to do now.

## 2. Validate every finding yourself

Reach your own verdict from evidence before you compare it with the reviewer's, and keep fact apart
from severity: a finding can be true and low-impact. Do not agree to be agreeable and do not reject
by reflex.

1. **Reproduce** with a probe in your scratchpad, bounded by `signal.alarm(60)`, at two or three
   input sizes so that a slow case shows its growth instead of hanging (macOS has no `timeout`).
2. Decide one of:
   - **fix**: true, and inside the brief's scope;
   - **reject with evidence**: say what you ran and what it showed;
   - **park**: true, out of scope: one line in `docs/BACKLOG.md`;
   - **The maintainer's decision**: a rule would have to change: put it under "Next steps for the
     maintainer" with the options and your recommendation.
3. If a finding is partly right, fix that part and say which part you did not take.

## 3. Fix with TDD, and check what the fix costs elsewhere

1. Write the failing test first and save its output: that is the red proof. Prefer a test that
   counts work to one that reads a clock, so the gate answers the same everywhere.
2. Write the smallest fix. `make check`; and `make mutate MUTANTS="<module>.*"` when you touched
   `src/kitpkg/core/`. A surviving mutant means restructure the code, never an escape comment.
3. Measure the neighbours: a fix that removes one cliff can slow the common case. Run the committed
   code and the fixed code on several input shapes and compare their output on random inputs.
4. Never remove, skip or weaken a test, never add an escape-hatch comment. A gate file changes only
   when the finding is about that file, and then it goes under "Gate files changed" in the PR.

## 4. Answer on the PR, then run the command again

1. Read every comment on the PR first, top-level ones too (`references/commands.md`). Do this
   before each push and before `gh pr ready`, not once.
2. Reply in each inline thread with the evidence: what you reproduced, the fix (commit, test), what
   you measured, what you did not take and why. Post from a file (`-F body=@file`).
3. Findings that have no inline thread (plan-reviewer's, and any the summary lists as not posted
   inline): answer them in one top-level comment, by number. The next round reads it.
4. One commit and one push per round. Read `gh pr checks <pr>` once: a red check is yours to fix
   before the next round; do not wait in a loop for pending ones.
5. **Resolve each thread that is genuinely fixed, and only those.** This is your judgment, thread
   by thread; no tool does it for you. A thread is genuinely fixed when you have seen the fix
   work at the pushed head: the test that was red is green, or the probe that showed the defect
   now gives the right answer, and the whole finding is covered, not a part of it. Then resolve
   it (`references/commands.md`).
6. **Every other thread stays open: an open thread is how this loop escalates to the maintainer.** Parked,
   rejected, kept as it is, fixed in part, a decision to take, a fix you could not see working:
   leave it open, and make sure your last answer in it says what is still open and what the maintainer has
   to decide or know. Never resolve a thread to make the PR look finished.
7. Run the same command again. It starts only the reviewers that are not green, and it says so
   when a reviewer has used its rounds. The next reviewer reads resolved threads too and raises
   again what does not hold.

## 5. Close out

Reached when the `next:` line says every reviewer is green, or says to stop.

1. Go through the threads once more (step 4, items 5 and 6): the last round's fixes too are
   resolved where you saw them work, and nothing else is. Say in the report that no reviewer has
   checked the last round's fixes.
2. Rebuild the PR body from saved proof files (verbatim, every cut marked `[…]`). In the
   walkthrough, give one line per reviewer run, copied from its record comment: round, asked,
   answered, verdict, cost, time. Update "Next steps for the maintainer" and "Docs this change made stale".
3. Append `docs/FRICTION.md` lines for what went wrong, was slow or confused. Take figures from
   saved files, not from memory.
4. **Post the closing comment on the PR**, the last thing on it and the one the maintainer reads at the
   end (`gh api repos/<o>/<r>/issues/<n>/comments -F body=@closing.md`). Head it
   `**Review loop closed**` when every reviewer is green, `**Review loop stopped**` when the
   rounds are used. Its body, in this order:
   - **Next steps for the maintainer**, the same checklist as in the PR body: every action only the maintainer can
     take, every thread still open as an item of its own (its link, and what the maintainer has to decide
     or know), and the merge last;
   - one line per reviewer: its last verdict, the rounds it used, the model and effort that ran
     (copied from the record comments);
   - threads: how many resolved, how many open;
   - what no reviewer has checked (the last round's fixes), and what was not run.
   Post it from a file, after the PR body is rebuilt, so the two say the same thing.
5. Report to the maintainer in chat in the same order, shorter, with the link to the closing comment.

## Requests and controls

Say which is which when you report; do not present a request as a control.

- **Controls** (the launcher enforces them): the model and effort of each reviewer; the time
  limit; the spending cap on the reviewer process and its subagents; no advisor and no MCP servers
  in a reviewer process; the number of rounds; a record comment for every run; one call at a time
  per reviewer. And where the reviewer works: a clone that is thrown away, so what it writes,
  commits or switches in its working tree does not reach this checkout.
- **Pushes from the clone: two nets.** Its `origin` has no push address, and a pre-push hook
  refuses every push. A push with the address typed out and `--no-verify` still gets out: the
  reviewer process has your credentials. The Bash guard, which runs in the clone too, refuses a
  push that lands on the base branch, and any change of labels.
- **Nets, not walls**: the edit tools are denied inside the clone, and the plain spelling of a
  command that changes git state, changes the PR (`gh pr merge`, `gh pr edit`), or starts another
  `claude`, is refused. Another spelling gets through. In the clone that harms nothing; `gh` and
  the cost of a `claude` started that way are not held by the clone.
- **Requests** (the reviewer is told, nothing enforces it): stay read-only, do not answer or
  resolve threads, read the earlier comments first, do not repeat settled points, stay inside about
  25 tool calls, bound every probe.
- **Yours, and nobody else's:** which threads are resolved. The launcher never resolves one and
  the reviewers are told not to. A resolved thread says that you saw the fix work.

## Pitfalls

- The Bash guard reads path names in a command's text: a command that writes a file and names a
  gate path is refused. Write files with the editor and keep shell commands plain.
- In zsh, `cmd | tee f; echo $?` reports `tee`. Use `cmd > f 2>&1; echo "exit code: $?" >> f`.
- `grep` here is ugrep and rejects some bounded patterns; use a short Python file for context.
- The project's hooks run in a reviewer process too. The Stop hook stands aside there (the launcher
  marks the process with `KIT_REVIEWER_CLONE=1`): a reviewer changes nothing, and the branch's own
  red — a renamed test awaiting the label — must not keep it from ending. Before that marker
  existed, both reviewers of the kit's PR 1 ran to their time limits with their reports written and
  unposted.
- On a PR that has no brief, plan-reviewer cannot run: use `--only code` in every round. The
  `next:` line then closes the loop on the code review alone and says that plan-reviewer had no
  brief. With a brief, `--only` never closes the loop: the line asks for the reviewer left out.
- A second call for the same PR while one is running is refused. Wait for the first to return.
