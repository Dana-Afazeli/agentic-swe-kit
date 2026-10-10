# Applying the kit, customising it, taking updates, maintaining it

**Status:** living · kit-owned (a kit update merges this file; a project's deviations go in
`docs/DELTAS.md`).

## 1. Prerequisites

On the machine that develops: `git`, [`uv`](https://docs.astral.sh/uv/) (0.11 or later), `gh`
(logged in: `gh auth status`), and the Claude Code CLI. Python itself is installed by uv from
`.python-version`; nothing is installed globally. The Bash tool runs the user's shell (zsh on a Mac);
the guard's tests ask every installed shell, so both zsh and bash are fine.

## 2. A new project

1. On GitHub: **Use this template** → a new repository with one commit holding the kit. (Or clone
   this repository and point `origin` at an empty one; `init` works the same.)
2. Clone it, then render the placeholders:
   ```sh
   python3 kit.py init --package <name> --maintainer "<Your Name>" [--base <branch>] [--branch-prefix <prefix>] [--python X.Y.Z] [--labels] [--hooks]
   ```
   - `--package`: a Python identifier; `src/kitpkg` becomes `src/<name>` and every knob site follows.
   - `--maintainer`: replaces the role phrase "the maintainer" in the texts the agents read.
   - `--base`: the branch PRs merge into (the kit's default is main); `--branch-prefix`: unit
     branches are `<prefix>-NNN-slug` (default = the base).
   - `--labels`: creates `brief-approved`, `gates-approved`, `checks-weakened-approved` and
     `scope-approved` with `gh`.
   - `--hooks`: `uv run prek install` — only in the development checkout.
   `init` seeds the project-owned files from `docs/templates/`, removes the kit-only files, writes
   `kit.lock`, runs `uv lock`, `uv sync --all-groups` and `make check`, and prints the next steps.
3. `make prove` — every gate shown red on a planted defect on *your* machine (a few minutes).
4. Commit, and push that commit **straight to the base branch** — the one time anything does. The
   template commit is not yet your project: CI's integrity check compares a PR with it and would
   show the kit's own tests (`test_kit.py`, the renamed sample tests) as vanished. (The Stop hook
   does not look at vanished tests — ADR-0008 — so a session in the checkout can stop; `init` from a
   terminal is still the simpler way.)
5. Open `README.md` (now your project's) and `docs/ROADMAP.md`; then run `/brief-writer` in a
   fresh session: it interviews you and opens the first brief as a draft PR. From here on, every
   change is a PR.

Checkouts: develop in one clone; if the project runs something, run it from a second clone pinned to
the base branch. Never two Claude Code sessions in one folder (`WORKFLOW.md`, "One session per
checkout"). Secrets live outside the repository (`~/.config/<name>/…`), never in it.

## 3. Day to day

- A unit of work starts as a brief in a draft PR (`/brief-writer`); the maintainer labels it
  `brief-approved`; a fresh session runs `/implementer NNN`; the review loop runs; the maintainer
  reads the page and merges. `WORKFLOW.md` has the loop. The roles are skills under
  `.claude/skills/`: editing one changes how that role works, in this project and after an update.
- `make check` is the gate; the Stop hook runs it. `make mutate` on `core/` changes. `make fmt`
  rewrites files on purpose; nothing else does.
- When a PR touches a gate file, CI is red until the maintainer labels `gates-approved` after
  reading the diff; a later push to a gate file removes the label again.
- When a test vanished or a skip or escape-hatch comment was added, CI's `integrity` job is red
  until the maintainer labels `checks-weakened-approved`. The Stop hook does not check this
  (ADR-0008): run `scripts/integrity.py --base origin/<base>` yourself before `gh pr ready`.
- Friction goes in `docs/FRICTION.md` as it happens; the weekly outer loop turns it into enforcement.

## 4. Customising — where things go

The rule that keeps updates painless: **never edit a kit-owned file to add project behaviour.**
(`HARNESS.md`, "File ownership", has the table.)

| You want to… | Do this |
|---|---|
| add a make target (`run`, `deploy`, `migrate`) | `project.mk` (included by the Makefile) |
| add a CI job | `.github/workflows/project.yml` — a workflow of its own |
| add a rule for the agents | the "Project rules" section at the end of `AGENTS.md` |
| allow another command for the agents | add to `permissions.allow` in `.claude/settings.json` (merges cleanly; it is a gate file, so `gates-approved`) |
| deviate from the kit's workflow or harness | write it in `docs/DELTAS.md` with the reason (and a decision record if it is a decision) |
| forbid an I/O package in `core/` | `forbidden_modules` of the contract in `pyproject.toml` |
| add an architecture contract | a new `[[tool.importlinter.contracts]]` table |
| raise a threshold | `fail_under` in `pyproject.toml`; `--fail-under` of diff-cover in `ci.yml`; `gates-approved` |
| widen the mutation scope beyond `core/` | the `-- src/<pkg>/core` path in `ci.yml`'s mutation job |
| add a dev dependency | `uv add --group dev <pkg>` (exempt from the guard; the lock is a gate file) |
| record a fact about a tool | `docs/research/<date>-<topic>.md`, dated, `Status: snapshot` |

Thresholds are starting points. Raise them from the friction log; never lower one in a feature PR.

## 5. Taking a kit update

```sh
git switch -c <prefix>-kit-update          # a branch; the update is a PR like any other
uv run python kit.py status                # your version, the newest tag, kit-owned files you changed
uv run python kit.py update [--to vX.Y.Z]  # default: the newest tag
```
`update` clones the kit, exports the version you have and the version you asked for, renders both
with the answers in `kit.lock` — each by the rules of its own `kit.py` — and three-way merges every
kit-owned file (`git merge-file`: base = the old kit rendered, yours = your file, theirs = the new
kit rendered). Then it writes the new
`kit.lock` (version and commit), prints the changelog sections between the two versions, stages
everything, re-locks and runs `make check`. It says how many files merged, and lists:
- **conflicts** — files with markers (`<<<<<<< yours` … `>>>>>>> kit X.Y.Z`): resolve them, then
  `make check`; the exit code is 1 until you do;
- **kept** — files the kit removed that you had changed (left in place: delete or keep);
- **missing** — kit-owned files you had deleted (not recreated);
- **not added** — files new in the kit where you already have another file;
- **not touched** — kit-owned paths that are symbolic links in your project (a merge would write
  through them, outside the diff).
Then `make prove`, open the PR, read the diff (it touches gate files: `gates-approved`), merge.

When the version you move to has another `kit.py`, `update` runs that one — from the export,
before anything is written — so the newer manifest decides what is kit-owned, and `kit.py` itself
is merged like every other kit-owned file. A project made from the kit before `update` existed has
a `kit.py` without the command: copy the kit's `kit.py` over yours first and commit, then run
`update`.

Two options for the unusual case. `--from <ref>`: the kit commit this project was rendered from,
when the lock has none and the kit has no tag for the lock's version (a project made from the kit
before its first release). `--to <ref>`: any kit ref — a tag, a branch, a commit — not only a
release; `update` refuses a target older than what you have. `--repo` points at another copy of
the kit (a local clone, a fork). `status` fetches the kit too, so both need the network.

What survives an update: your dependencies and `[project]` table, your additions to
`.claude/settings.json`, `project.mk`, your workflow file, `docs/DELTAS.md`, the "Project rules"
section, everything project-owned. What does not: an edit you made inside a kit-owned file where the
kit changed the same lines — that is the conflict `update` shows you.

## 6. The sample package

`src/kitpkg/core/text.py` (`truncate`), `src/kitpkg/io/console.py` and `src/kitpkg/main.py` exist so
that every gate has code to bite on from the first commit — the coverage floor, the contract, the
mutation gate and `make prove` all need something real. Replace them with your first unit; keep the
layout (`core/` pure, `io/` boundaries, `main.py` wiring) or change the contract deliberately.

## 7. Maintaining the kit itself

The kit is a project under its own harness: briefs, PRs, the review loop, `gates-approved`.
- A change is proven on the kit first (`make check`, `make prove`, CI), then released.
- `CHANGELOG.md` has an `Unreleased` section; every PR adds its line there.
- Release: bump `KIT_VERSION` in `kit.py`, move `Unreleased` under the version heading with the date,
  merge, tag `vX.Y.Z` on `main`, `gh release create vX.Y.Z --notes-from-tag`. A test asserts the
  changelog has a heading for `KIT_VERSION`.
- Renaming or removing a kit-owned file: `update` adds the new path and deletes the old one only
  where the project left it unchanged; say so in the changelog.
- A fix a project made to a kit-owned file reaches the kit as a PR here, not as a local edit that
  the next update will conflict with.
