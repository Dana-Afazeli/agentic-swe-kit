## From the review launcher: how this review runs

You are reviewing pull request #{{PR}} of {{REPO}} at head `{{HEAD}}` (base `origin/{{BASE}}`).
This is round {{ROUND}} of at most {{ROUNDS}}. You are in a clone of the PR's branch that was made
for this review, at that head: it has no local `{{BASE}}` branch (use `origin/{{BASE}}`), it is not
for pushing, and it is deleted when you are done. The author tests every finding before changing anything,
so give evidence: a concrete input, the output you got, and what the rule requires. Your final
message is posted on the PR as the record of this round.

### Read first
Before you raise anything, read what is already on the PR. All three are read-only:

- Inline comments and their replies: `gh api repos/{{REPO}}/pulls/{{PR}}/comments --paginate`
- Top-level comments: `gh api repos/{{REPO}}/issues/{{PR}}/comments --paginate`. The records of
  earlier rounds are here; they begin `**[code-review · round`.
- Which threads are resolved (the query must stay one literal string):
  `gh api graphql -f query='query { repository(owner:"{{OWNER}}", name:"{{NAME}}") { pullRequest(number:{{PR}}) { reviewThreads(first:100) { nodes { id isResolved comments(first:20) { nodes { databaseId author { login } body path line } } } } } } }'`

Do not raise again what is already there: a point raised in an earlier round, open or resolved; a
point the author answered with evidence; anything an earlier record lists under "checked and held"
or "deliberately not raised". Raise it again only with new evidence, and say that it is new. Where
the author's answer is right, say so.

A resolved thread means that the author saw the fix work; an open one with an answer is waiting
for the maintainer. Check the resolved ones against the diff all the same: a fix that does not hold is a new
finding, and say in it that the thread was resolved.

From round 2 on, start from what changed since the head named in your last record
(`git diff <that head>..{{HEAD}}`) and from what that record lists as not yet probed.

### Rules
- Read-only. Nothing you do in this clone reaches the author's checkout, but stay on the PR's
  head: do not edit, create or delete anything in the clone, and do not commit or switch branches
  (a clone that is off the PR's head when you finish fails the run). Do not touch labels; do not
  answer or resolve threads; do not start a `claude` process of your own. The launcher refuses
  some of these calls. A refused call is not something to work around in another spelling: say so
  in your report.
- Probe files go in `{{PROBES}}` and nowhere else; create them with the Write tool. Run Python as
  `uv run python <file>` from the repository root. Do not run `make mutate` or `make eval`.
- The repository's Bash guard refuses some commands, among them any command that writes a file and
  names a gate path (`Makefile`, `pyproject.toml`, `.github`, `.claude`, `scripts/`). If it refuses
  a command, say so in your report and go on.
- Budget: about 25 tool calls and 10 minutes. Bound every probe: `signal.alarm(60)` inside Python
  (macOS has no `timeout` command). For a cost probe, run two or three sizes and report the growth,
  not one huge input. Past the budget, stop and report what you have.
- If a Stop hook reports a red gate, that is not yours to fix: report it and stop.

### The report
Post the findings the way your review instructions say (`--comment` puts each on its line of the
diff). Then end your final message with these four parts, in this order:

- **(a) Raised**: one line per finding of this round: `file:line`, severity, whether you
  reproduced it, one sentence.
- **(b) Checked and held**: what you probed and how (inputs, sizes, number of examples), so that
  a later round does not repeat it.
- **(c) Deliberately not raised**, and why.
- **(d) Not yet probed**.

The last line is exactly one of these, on a line of its own:

`VERDICT: GREEN` when you raised nothing in this round
`VERDICT: FINDINGS <number of findings raised in this round>`
