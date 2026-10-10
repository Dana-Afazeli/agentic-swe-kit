# The reviewer's rules

One row per numbered rule of the two reviews. `P` rules stand in `conformance.md`, `C` rules in
`correctness.md`. "Checked from" says where someone looks to see whether a reviewer kept the rule:
`transcript` (the run's record), `PR` (what is on the pull request), `git`, `judgment` (a person
or a model has to read and decide), or `not checkable`. `uv run python scripts/roles.py` fails
when this table and the text disagree.

| Id | Rule | Checked from |
|---|---|---|
| P-01 | reports an acceptance criterion that no test would catch | judgment |
| P-02 | reports a change the brief does not ask for or forbids, unless the page lists it on the maintainer's word and the PR carries `scope-approved` | judgment |
| P-03 | reports a statement on the page that the diff contradicts | judgment |
| P-04 | reports a living document the diff made false | judgment |
| P-05 | reports a proof that is missing, stale or contradicted | judgment |
| P-06 | reports a page that does not read cold | judgment |
| P-07 | reports a description that is not the page | PR |
| P-08 | stays read-only: the listed commands and nothing else | transcript |
| P-09 | the record has a line per finding, a line per criterion, the verdict last | PR |
| C-01 | reads the three listings of the pull request before raising anything | transcript |
| C-02 | does not raise again what is settled, unless with new evidence | judgment |
| C-03 | stays read-only and on the PR's head | transcript |
| C-04 | probe files only in the probes folder, each bounded | transcript |
| C-05 | stays inside about 25 tool calls and 10 minutes | transcript |
| C-06 | the report has its four parts, says what was checked under each of the four questions, and ends with the verdict line | PR |
