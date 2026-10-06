# Commands for the review loop

`<o>/<r>` is the repository (`gh repo view --json nameWithOwner --jq .nameWithOwner`), `<n>` the PR.
Write any comment body to a file with the editor and pass it with `-F body=@file`: the Bash guard
refuses `-f body='...'` when the text holds a gate word, and refuses a command that writes a file
and names a gate path.

## The reviewers
```
uv run python scripts/review.py <n> --plan sonnet/medium --code opus/xhigh   # every reviewer that is not green yet
uv run python scripts/review.py <n> --only code --code opus/xhigh            # one reviewer (a PR with no brief)
uv run python scripts/review.py <n> --plan sonnet/medium --code opus/xhigh --expire code   # the code review's green no longer counts
uv run python scripts/review.py <n> --plan sonnet/medium --code opus/xhigh --rounds 5      # five rounds per reviewer, not three
uv run python scripts/review.py <n> --plan sonnet/medium --code opus/xhigh --dry-run       # print the commands, start nothing
```
The model and effort of a reviewer that runs must be named; there is no default (the values in
the examples are the ones PR #11 ran with). Other options: `--brief PATH`, `--budget-usd X`,
`--timeout-min N` (the last two apply to each reviewer the call starts). Caps when not named:
code $10 and 20 minutes; plan $2 and 8 minutes.
The Bash tool stops a background command after 30 minutes unless told otherwise: with a longer
`--timeout-min`, set the tool's `timeout` above the sum of the two limits.

Exit code 0: the reviewers ran, or none was left to run. 1: a run failed, or its record comment
could not be posted. 2: nothing was started (PR not open; on the PR's branch with a head that is
not pushed or a tree that is not clean; no brief; a clone that could not be made); the message says
which.

The command can be run from a checkout on any branch: the reviewers get clones of what GitHub has
for the PR, and the brief is read from the PR's head on GitHub.

Each run leaves a folder (its path is in the `report:` line): `report.md` (the reviewer's final
message), `record-comment.md` (what was posted), `record.jsonl` (the whole run, large: count in it
with `jq`, never read it), `stderr.txt`, `protocol.md` (what the code reviewer was told), `probes/`.
The reviewers' clones are in the same folders while the call runs and are removed when it ends.

## Read the PR before anything else, and again before each push and `gh pr ready`
```
gh pr view <n> --json state,isDraft,headRefOid,labels,mergeable,mergeStateStatus
gh api repos/<o>/<r>/pulls/<n>/comments          # inline comments
gh api repos/<o>/<r>/issues/<n>/comments         # top-level comments (records and planning notes)
gh api repos/<o>/<r>/pulls/<n>/reviews
gh api graphql -f query='query { repository(owner:"<owner>", name:"<repo>") { pullRequest(number:<n>) { reviewThreads(first:100) { nodes { id isResolved comments(first:20) { nodes { databaseId author { login } body path line } } } } } } }'
```
The GraphQL read must be one literal string (no variables).

## Reply in a thread, answer at the top level, resolve
```
gh api repos/<o>/<r>/pulls/<n>/comments/<comment databaseId>/replies -F body=@reply.md
gh api repos/<o>/<r>/issues/<n>/comments -F body=@answers.md
gh api graphql -f query='mutation { resolveReviewThread(input: {threadId: "PRRT_..."}) { thread { isResolved } } }'
```
Only this exact shape of the mutation passes the guard: a literal thread id and nothing else
(several aliased calls in one mutation are fine; variables, `-F`, files and `--input` are refused).
Nothing may follow the query either: with `--jq …` after it the call is refused.

To resolve the threads you found genuinely fixed (SKILL.md, step 4):
1. Find each thread's id with the GraphQL read above. A thread's first comment has the
   `databaseId` of the finding you answered; the thread's `id` starts with `PRRT_`.
2. Resolve them in one call, one alias per thread:
   `gh api graphql -f query='mutation { a1: resolveReviewThread(input: {threadId: "PRRT_..."}) { thread { isResolved } } a2: resolveReviewThread(input: {threadId: "PRRT_..."}) { thread { isResolved } } }'`
3. Run the read again and check: every thread you meant is `isResolved: true`, and no other is.

Write each comment id out in the address, one command per reply (chain them with `&&`): the guard
refuses an address it has to read through a shell variable, as in `for id in …; do gh api
…/comments/$id/replies`. Never touch labels.

## Probes and proofs
- Bound a Python probe with `import signal; signal.alarm(60)` and run two or three sizes.
- Save each proof as `cmd > f 2>&1; echo "exit code: $?" >> f`.
- Compare committed and fixed code: `git show HEAD:<path> > <scratch>/old.py`, load it with
  `importlib.util.spec_from_file_location`, and run both on the same inputs.
- `make check`; then `make mutate MUTANTS="kitpkg.core.<module>.*"` when `src/kitpkg/core/`
  changed; `uv run diff-cover coverage.xml --compare-branch=origin/main --fail-under=95 --branch-coverage`
  after `git add` (diff-cover does not see untracked files).
- CI after a push: `gh pr checks <n>`, read once.

## The PR body
Build it with a script that reads the saved proof files, so that nothing is retyped: a collapsed
`<details>` per proof, a four-backtick fence, `[…]` wherever lines are cut. Keep every heading of
`.github/pull_request_template.md`. `gh pr edit <n> --body-file <file>`.

## The closing comment (SKILL.md, step 5)
The last comment on the PR, the one the maintainer reads at the end. Write it to a file, then:
```
gh api repos/<o>/<r>/issues/<n>/comments -F body=@closing.md
```
Its first line is `**Review loop closed**` or `**Review loop stopped**`; then "Next steps for
the maintainer" as in the PR body, one line per reviewer (last verdict, rounds used, model and
effort that ran), the thread counts, and what no reviewer has checked.
