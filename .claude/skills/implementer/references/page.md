# The page: one filled example, and three mistakes to avoid

The page is the pull request's description. The maintainer reads the part above the reference
line and nothing else, with no memory of your session; the reviewers check the part below it.
Fill in `assets/pr-page.md`; this file shows what a finished one looks like.

The example is invented: a service that sends reminders, and a brief 042 that exists nowhere.

````markdown
Brief: [`docs/briefs/042-quiet-hours.md`](docs/briefs/042-quiet-hours.md)

## What this is, and where it sits
The service now holds its reminders at night. Between 23:00 and 07:00, in the user's own time
zone, a reminder that comes due is still worked out, but it waits and is sent at 07:00 with a
first line saying when it was due. Outside those hours nothing changes.

Before this unit, every reminder went out the moment it came due. After it comes brief 043,
which lets a user change the hours; here they are two settings read at start.

Not in this unit: a way to mark one reminder as urgent enough to be sent at night, and anything
for reminders that go to a group.

## Next steps for the maintainer
- [ ] **Read "Decisions for the maintainer" below and reply with one word.** The answer decides
      whether one more test is added before the merge.
- [ ] **Add `gates-approved`** after reading the one-line change to `pyproject.toml` (a new
      marker, `clock`, for the two tests that use a fake clock). CI's `gate-guard` job is red
      until then, and the merge waits on it.
- [ ] **Set a reminder for after 23:00 and look at 07:00.** No test runs against the real
      delivery; this is the one check that does.
- [ ] **Merge.** That lets brief 043 start.

## Decisions for the maintainer
**What happens to a reminder that is waiting when the service restarts?**
The situation: a held reminder lives in memory until 07:00. If the service is restarted at
night, the reminder is lost and nothing arrives in the morning. I checked this by stopping the
service at 23:30 with one reminder held (`quiet_restart.txt` in the proofs comment): after the
restart, nothing was sent at 07:00.
- **keep**: leave it as it is. To build: nothing. What a user notices: after a night restart,
  the reminders that were waiting never arrive, and nothing tells them so.
- **file**: write held reminders to a file in the state directory and read it at start. To
  build: about 60 lines and two tests in this pull request. What a user notices: nothing; a
  restart loses no reminder.
- **later**: the same as "file", as a line in `docs/BACKLOG.md` for the unit that makes the
  queue survive a restart. To build: nothing now. What a user notices: the same as with "keep"
  until that unit is merged.

I recommend **later**: that unit has to store the queue anyway, and two formats for one state
directory is a cost of its own. Reply `keep`, `file` or `later`.

## Not proven
- **The real 07:00.** The tests move a fake clock. Whether a reminder leaves at 07:00 on the
  real one is the third step above.
- **A change of the clock's offset during the night** (summer time). Not tested; a test with a
  time zone that changes its offset at 02:00 would show it.

Reference: below this line, checked by the reviewers

## File by file
- `src/pkg/core/quiet.py`: `is_quiet(now, start, end)` and `release_time(now, end)`. Pure.
- `src/pkg/io/queue.py`: holds a reminder that is due while `is_quiet` says so.
- `src/pkg/core/settings.py`: the two settings, `quiet_start` and `quiet_end`.
- `tests/test_quiet.py`, `tests/test_queue.py`: the brief's seven criteria, one test each.
- `pyproject.toml`: the `clock` marker.

## Where this differs from the brief
The brief names the settings `quiet_from` and `quiet_to`. `settings.py` already uses `_start` and
`_end` for the working hours, so these follow it.

## The review record
- code-review · round 1 · asked opus/high · answered claude-opus-5-5 x38 · FINDINGS 2 · $1.61 · 402 s
- plan-reviewer · round 1 · asked sonnet/medium · answered claude-sonnet-5-5 x21 · GREEN · $0.31 · 96 s
- code-review · round 2 · asked opus/high · answered claude-opus-5-5 x19 · GREEN · $0.88 · 240 s

Threads: 2 resolved, 0 open. No reviewer has read the commit made after round 2 (a FRICTION line).

## Out of scope, noticed
- `docs/BACKLOG.md`: the service's log lines give times in UTC and the settings are local times.

## Docs made stale, and fixed
- `README.md`, "Status": said every reminder is sent when due. Fixed.

## Gate files changed
- `pyproject.toml`: one line, the marker `clock`. No threshold and no tool option changes.

## Checks weakened
None. The integrity script, run against the base branch, prints nothing.
````

## Three mistakes, each with what to write in its place

**A decision that does not stand alone.** It leans on the session's own labels, so only the
session can read it.

- Wrong: `- [ ] Decide on finding 4 (the residual window): see the thread.`
- Right: the block under "Decisions for the maintainer" above. It gives the situation, each
  option with what it takes to build and what a user notices of it, a recommendation, the word
  to reply, and the run that checked the fact.

**A page that tells its own history.** The reader never saw the earlier draft or the
conversation, so a sentence that answers them answers nobody.

- Wrong: `Rewritten after your correction: the first draft held every reminder, also by day.`
- Right: `The service now holds its reminders at night.` Say what the pull request is at its
  head. How it came to be so goes in the commit message, a PR comment or `docs/FRICTION.md`.

**A step that does not say what it unblocks.** The maintainer cannot tell whether it can wait.

- Wrong: `- [ ] Add the label.`
- Right: `- [ ] Add gates-approved after reading the one-line change to pyproject.toml. CI's
  gate-guard job is red until then, and the merge waits on it.`

`scripts/pr.py page` catches none of the three: it checks the page's shape (its length, its
parts, a comment left from the template) and not its words. The conformance reviewer reports all
three.
