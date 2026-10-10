# The implementer's rules

One row per numbered rule. I-01 to I-12 stand in this skill's `SKILL.md`; I-13 to I-17 are the
rules of the review loop and stand in `.claude/skills/review-loop/SKILL.md`, the implementer's
last step. "Checked from" says where someone looks to see whether a session kept the rule:
`transcript` (the session's record), `PR` (what is on the pull request), `git`, `judgment` (a
person or a model has to read and decide), or `not checkable`. `uv run python scripts/roles.py`
fails when this table and the text disagree.

| Id | Rule | Checked from |
|---|---|---|
| I-01 | this skill runs before anything else | transcript |
| I-02 | the PR carries `brief-approved` before work starts, or the session stops and asks there | transcript |
| I-03 | the failing test comes first: run, saved, with what made it red | transcript |
| I-04 | `make check` is green after the last change, saved with its exit code | transcript |
| I-05 | no test removed, skipped or weakened, and no escape-hatch comment | git |
| I-06 | `make mutate` on the gated modules that were touched | transcript |
| I-07 | stays inside the brief; what else it notices is a BACKLOG line; work beyond it only on the maintainer's word, listed on the page, with `scope-approved` asked for | judgment |
| I-08 | a FRICTION line for what went wrong, was slow or confused | judgment |
| I-09 | proofs word for word from saved files, cuts marked, in one PR comment, none in the description | PR |
| I-10 | the description is the page | PR |
| I-11 | the page is rebuilt at each push that changes the diff | PR |
| I-12 | a decision names the run that checked its facts, and keeps the maintainer's words apart from the session's | judgment |
| I-13 | every comment on the PR is read before each push and before `gh pr ready` | transcript |
| I-14 | fix the kind, not the case; a third round on one kind goes to the maintainer | judgment |
| I-15 | a finding is reproduced before anything changes | transcript |
| I-16 | a thread is resolved only when its fix was seen working at the pushed head | judgment |
| I-17 | the loop ends with the closing comment, which says what the page says | PR |
