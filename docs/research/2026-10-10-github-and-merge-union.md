# Research notes — does GitHub honour `merge=union`? (run 2026-10-10)

Carried from the source project's `docs/research/` (its pull request #17, merged 2026-10-10): the
runs and versions are the ones named below.
**Status:** snapshot (2026-10-10) — not edited; newer findings go in a new dated file.

Run for brief 009, criterion 7. Question: with `docs/FRICTION.md merge=union` in `.gitattributes`,
does GitHub report two pull requests that each append a row to that file as mergeable?

## Run
Two branches forked from one commit that holds `.gitattributes` (`docs/BACKLOG.md merge=union` and
`docs/FRICTION.md merge=union`). Each appended one different row at the end of
`docs/FRICTION.md`. A draft pull request from the second into the first, read twice:

```
$ git merge-tree --write-tree probe-union-base probe-union-head      # local git
dbdfb8a050a5ff96dfc2e0e42e80225ad2504997                              # a tree, exit 0: no conflict
$ gh pr view 20 --json mergeable,mergeStateStatus
{"mergeStateStatus":"DIRTY","mergeable":"CONFLICTING"}
$ gh pr view 20 --json mergeable,mergeStateStatus                    # one second later
{"mergeStateStatus":"DIRTY","mergeable":"CONFLICTING"}
```

## Result
**GitHub does not honour the attribute: `CONFLICTING`.** The same two branches merge with no
conflict on a machine, because local git applies the union driver. So:

- `merge=union` makes `git merge origin/<base>` resolve by itself where two sides appended rows,
  and keeps both rows.
- It does not make GitHub's own mergeability check, or its merge button, treat two such branches as
  mergeable. A pull request whose base has moved in these files shows conflicts until its branch
  has merged the base locally and been pushed.

A lookup on 2026-10-08 had found one report (a 2016 thread on rubocop's PR 3594) that GitHub does
not honour the attribute; this run agrees with it.
