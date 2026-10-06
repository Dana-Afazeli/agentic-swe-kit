# Brief 002 — `kit.py update` and `status`: a project takes a newer kit with one command

**Execute in a fresh Claude Code session started in the development checkout.** You need no context
beyond this file and the repository. This brief is a draft PR on branch `main-002-update`
(`brief-approved`): `git fetch && git switch main-002-update`, work there, and mark the PR ready when
done. Sessions: implementer — the planning session itself, by the maintainer's decision of
2026-10-06 · reviewers: `plan-reviewer` sonnet/medium, `/code-review` opus/xhigh, 3 rounds.

## Context
`kit.py init` (brief 001) renders the kit's placeholders with a project's answers and records them
in `kit.lock` with `KIT_VERSION`. The maintainer's requirement: "if I use this in my repo and an
update comes out, it should be updatable easily." ADR-0007 decided the mechanism: render the kit at
the project's recorded version and at the new one with the same answers, and three-way merge every
kit-owned file (`git merge-file`), so what the project never touched updates cleanly, its additions
survive, and a real collision is a visible conflict. `render_text`, `render_path`, `category()` and
`SEEDS` exist and are tested; `update` composes them.

## Objective
`kit.py update [--to vX.Y.Z] [--no-sync]` three-way merges the kit-owned and mixed files between the
recorded kit version and the requested one, rewrites `kit.lock`, prints the changelog between the
two versions and what needs a hand; `kit.py status` says where a project stands.

## Out of scope — do not do these
- `make prove` (brief 003); `init` behaviour (brief 001, merged).
- Any network call other than fetching the kit repository with git; no GitHub API.
- Merging project-owned files, or touching `src/`, `tests/test_*.py`, `README.md`, `project.mk`,
  `docs/DELTAS.md`, the project's roadmap, friction log, backlog, decisions, research.

## Inputs
- `kit.py` (the manifest, `render_tree`, `read_lock`/`write_lock`); `docs/kit/HARNESS.md` §9;
  `docs/kit/SETUP.md` §5 and §7; ADR-0001, ADR-0007; `git merge-file --help`.

## Interface
`kit.py`:
- `fetch_kit(repo: str, into: Path) -> None` — `git clone --quiet` (the URL from `kit.lock`).
- `kit_versions(clone: Path) -> list[str]` — the tags `vX.Y.Z`, sorted by version.
- `export(clone: Path, ref: str, into: Path) -> None` — `git archive <ref> | tar -x`; refuses an
  unknown ref with exit 2.
- `plan_update(base: Path, theirs: Path, project: Path) -> UpdatePlan` — per managed path (kit-owned
  or mixed in either version): `merge` (in both, project has it) · `add` (new in the kit) ·
  `remove_clean` (gone from the kit, project unchanged against base) · `remove_kept` (gone from the
  kit, project changed it) · `missing` (kit-owned, project deleted it) · `blocked_add` (new in the
  kit, project has an unrelated file there).
- `apply_update(plan, base, theirs, project) -> UpdateResult` — writes merged files
  (`git merge-file -p --diff3 ours base theirs`, exit code > 0 = conflicts kept as markers), copies
  additions, deletes `remove_clean`, leaves the rest; returns the lists.
- `update(args)`: reads `kit.lock`; refuses without it, on a dirty tree, or on the base branch;
  fetches; picks `--to` or the newest tag (and refuses a version older than the recorded one);
  exports and renders both versions with the lock's answers (`render_tree` into temp dirs, so
  `kit.py` itself is verbatim and the maintainer knob is prose-only, as at `init`); plans; applies;
  writes the new lock; prints the `CHANGELOG.md` sections between the versions (from the new kit,
  `## vA` … `## vB` headings, Unreleased excluded); stages everything; unless `--no-sync`: `uv lock`,
  `uv sync --all-groups`, `make check`; prints "Next steps": the conflicts to resolve, `make prove`,
  the PR, `gates-approved`. Exit 0 clean, 1 conflicts or a red gate, 2 refused.
- `status(args)`: version in the lock, newest tag available (fetch), and the kit-owned files whose
  content differs from the recorded version rendered (ours ≠ base), as a list.
- `KIT_VERSION` bumps to `0.1.0` stays; the test fixture builds kit versions in a temp repository
  with tags, so no real tag is needed.

## Acceptance criteria — concrete cases; write them as failing tests first
1. A fake kit repository (the kit's own tracked files, committed, tagged `v0.1.0`; then a second
   commit changing a line in `scripts/fmt_hook.py`, adding `docs/kit/NEW.md`, removing
   `docs/kit/research/2026-09-29-toolchain-and-claude-code.md`, changing `[tool.ruff.lint] select` in
   `pyproject.toml`, tagged `v0.2.0`) and a project made from `v0.1.0` with `init --package demo
   --no-sync` (lock says 0.1.0). `update --to v0.2.0 --no-sync`:
   - `scripts/fmt_hook.py` has the new line; no conflict markers anywhere (`<<<<<<<` absent).
   - `docs/kit/NEW.md` exists, rendered (no `kitpkg`); the removed research note is gone.
   - `pyproject.toml` has the new `select` **and** a dependency the project added before the update
     (`"httpx"` in `dependencies`): both sides merged.
   - `kit.lock` says `0.2.0`; `git diff --name-only` is empty (everything staged); exit 0.
2. A collision: the project edited the same line of `scripts/fmt_hook.py` before the update → the
   file holds `<<<<<<<`/`>>>>>>>` markers, the run prints it under "conflicts", exit 1; `kit.lock`
   still says `0.2.0` (the update is applied; the conflict is the maintainer's).
3. A local edit elsewhere in a merged file (another line of `fmt_hook.py`) survives, with the kit's
   change beside it.
4. The removed research note had been edited by the project → kept, listed under "kept (the kit
   removed it, you had changed it)".
5. A kit-owned file the project deleted (`docs/kit/SETUP.md`) → listed under "missing (you deleted
   a kit-owned file; not recreated)", not recreated.
6. Refusals (exit 2, a sentence): no `kit.lock`; dirty tree; `--to v0.0.1` older than the lock;
   `--to v9.9.9` unknown; the project's package name differs from the lock (someone edited the lock).
7. `status` prints the lock's version, the newest tag, and the names of kit-owned files that differ
   from the rendered recorded version (after a local edit to `Makefile`: exactly `Makefile`).
8. The changelog excerpt printed is the text between `## v0.2.0` and the next `## ` heading (or the
   end), from the new kit's `CHANGELOG.md`; `## Unreleased` is never printed.
9. The three-way merge uses the rendered trees: with answers `--base develop --branch-prefix unit`
   recorded in the lock, an updated `.claude/settings.json` reads `unit-:*` and `--base develop`.
10. `make check` green; `kit.py` still stdlib only (a test imports it with `sys.modules` patched to
    hide `tomllib`? no — `tomllib` is stdlib; the test asserts no third-party import by reading the
    import block).

## Proofs to paste into the PR
- The failing tests before `update` exists (red), `make check` green after, with exit codes.
- The real thing once: a project rendered from this branch's parent commit, then `kit.py update
  --to <this branch's head>` (a ref works where a tag would) with one local edit that collides and
  one that does not; paste the run's output.

## Output contract
As the template says. `CHANGELOG.md` Unreleased gets its lines; `docs/ROADMAP.md` ticks unit 2;
`docs/kit/SETUP.md` §5 is checked against what the command actually prints. Do not merge.

## One caution
`git merge-file` writes conflict markers into the file and exits with the number of conflicts; it is
not an error to trap. The trap is the base: it must be the *old kit rendered with the project's
answers*, never the project's current file or the raw kit — or every knob line conflicts.
