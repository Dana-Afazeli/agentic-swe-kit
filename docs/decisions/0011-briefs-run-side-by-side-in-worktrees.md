# ADR-0011 — Briefs run side by side in worktrees of the development checkout

**Status:** accepted 2026-10-11 (adopted from the source project's ADR-0012 of 2026-10-10) ·
**Deciders:** the maintainer: in the source project, the five answers on its pull request #17
(worktrees, deny, skills, rule, leave), which its record keeps as points 1 to 5; in the kit, "migrate
that as well". Points 6 to 8 are choices made when brief 007 was written and read by the
maintainer with it, not answers the maintainer gave · **Supersedes in part:** ADR-0002, its rule
that briefs are not run through git worktrees and that one session owns a checkout

## Context
ADR-0002 kept worktrees out and made "one session per checkout" a rule that nothing enforced: in
the source project a session twice switched the branch under another one, and a planning session
once shared the development checkout with an implementer. Two briefs could be built at once only in
a second clone made by hand.

ADR-0002 kept worktrees out for two reasons: a worktree shares git hooks with its parent, and a
session in a worktree was said to read `.claude/settings.local.json` from the parent only. For
several briefs side by side, shared hooks are wanted. The second point was run in the source project
on 2026-10-10 (`docs/research/2026-10-10-sessions-in-a-worktree.md`): in a session started in a
worktree, the worktree's committed `.claude/settings.json`, its hooks, its Stop gate and its
transcript are its own, and its own `.claude/settings.local.json` is read; the development
checkout's `.claude/settings.local.json` and its auto-memory are shared with it as well.

GitHub does not honour a `merge=union` attribute: two branches that each append a row to a log file
are reported as conflicting there, and merge cleanly with local git
(`docs/research/2026-10-10-github-and-merge-union.md`).

## Decision
1. **A brief runs in a git worktree of the development checkout**, in a folder beside it:
   `make tree BRIEF=NNN` (`BRANCH=<name>` for a branch by name, `NEW=<name>` for a new branch from
   `origin/<base>`), then a session is started inside it. `make untree` removes the folder and keeps
   the branch, and refuses a tree with uncommitted files or with commits that are on no branch of
   `origin`. The development checkout stays on the base branch.
2. **One session at a time may edit in a tree.** `scripts/session_lock.py` keeps a lock in the
   tree's own git directory (session id and when last seen) and runs at `SessionStart` and before
   every tool. Before `Edit`, `Write` and `NotebookEdit` it refuses a second session; before any
   other tool it keeps the holder's time fresh, so a session that works in its shell for half an
   hour keeps its tree. A lock not seen for 30 minutes is free; one that cannot be read is free. It
   stops the editing tools of a second session; it does not stop its shell. An editing tool that
   names a file outside the session's tree is not an edit in it. The lock belongs to the tree the
   session was started in, not to the file: a session started elsewhere that edits a file of a held
   tree is not stopped. The hook costs about 0.1 s a call, once before each tool call of a session
   in a tree.
3. **A tree keeps its branch.** `git switch` and `git checkout` are deny rules, and the two allow
   rules for `git switch` are gone. A deny rule is a prefix match: `git -C . switch` is not seen by
   it.
4. **Two logs, one rule.** `.gitattributes` gives `docs/BACKLOG.md` and `docs/FRICTION.md`
   `merge=union`, so `git merge origin/<base>` keeps the rows both sides added, and
   `tests/harness/test_doc_tables.py` finds what a union merge can leave behind. Because GitHub
   reports such branches as conflicting, a branch is brought up to date with `git merge
   origin/<base>` and pushed, whenever the base has moved, before `gh pr ready`.
5. **A new session in a tree waits for the lock to age.** The lock is not released when a session
   ends. A session started again in the same tree, or a conversation continued under a new session
   id, is refused edits until 30 minutes after the last edit of the one that held it, or until the
   lock file in the tree's git directory is deleted by hand.

Choices of the planning session, in porting the change:

6. **`tree.py` has two knobs**, `BASE_BRANCH` and `BRANCH_PREFIX`. The source has one name that is
   the base branch and the prefix of a brief's branch at once; in a project made with
   `--branch-prefix` they differ. `BRIEF=NNN` looks for `origin/<prefix>-NNN-*`; `NEW=<name>`
   starts at `origin/<base>`.
7. **The lock's file is `kit-session.lock`**, not the source project's name.
8. **The two log templates hold no row.** The table check finds an empty row in a table that has
   three of them, as "the same row"; a project's logs start with a header and a separator each.

## Consequences
- Several briefs can be built at once, each with its own folder, branch, hooks and gate.
- The development checkout's `.claude/settings.local.json` applies in every tree: a rule or hook put
  there reaches all briefs. Per-tree rules go in the tree's own file.
- Auto-memory is shared by every tree; a transcript is the tree's own.
- Git refuses to check out one branch in two trees; the lock is the only guard against two sessions
  in one tree.
- The code is the source's, copied: its known gaps come with it. `untree` does not read the lock; the
  lock follows the folder a session started in, not the file it edits; a new session in a held tree
  waits for the lock to age. Each is a row of `docs/BACKLOG.md`.
- A branch prefix with a `/` (`feature/units`) is found by `make tree BRIEF=`, and cannot be named
  with `BRANCH=` or `NEW=`, which take one path segment.
- A pull request whose base has moved in a log file shows conflicts on GitHub until its branch has
  merged the base and been pushed. If that costs more than one merge each time, the logs move to one
  file per row, as a brief of its own.
- A project that takes this change has no `make tree` until the update has been applied: its first
  update runs in a tree made by hand with `git worktree add`.
- The reviewers keep their throwaway clones; `scripts/review.py` is unchanged.
- ADR-0002 stands for the deployment checkout, for the reviewers' clones, and for the rule that a
  branch switch changes what every process in a folder sees.
