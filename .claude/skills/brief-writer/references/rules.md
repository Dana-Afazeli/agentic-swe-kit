# The brief writer's rules

One row per numbered rule; each stands in this skill's `SKILL.md`. "Checked from" says where
someone looks to see whether a session kept the rule: `transcript` (the session's record), `PR`
(what is on the pull request), `git`, `judgment` (a person or a model has to read and decide), or
`not checkable`. `uv run python scripts/roles.py` fails when this table and the text disagree.

| Id | Rule | Checked from |
|---|---|---|
| B-01 | the brief's last line is `Brief written in session <id>` | git |
| B-02 | reads the plan, the friction log, the last PR, the ADRs and the open PRs first, and again before reporting a state | transcript |
| B-03 | each decision is asked alone: situation, options with their cost to build and to whoever uses the result, a recommendation | transcript |
| B-04 | a brief holds work of one kind, at most about 1,000 added lines of code and tests | PR |
| B-05 | a fact about a tool is run or quoted that day, and the brief says how; what was not checked is named | judgment |
| B-06 | every proof command the brief names was run on the brief's own branch | transcript |
| B-07 | criteria are literal cases that name their inputs, from a list of what can go wrong; what no test can show is named for a check by hand | judgment |
| B-08 | the brief names model, effort and rounds for the implementer and each reviewer | git |
| B-09 | the brief says up front which labels its PR will need | git |
| B-10 | the brief carries the cautions | git |
| B-11 | says before pushing; commits only the brief; touches no label | transcript |
| B-12 | no throwaway implementation, no wait loop; a step over a minute is announced | transcript |
