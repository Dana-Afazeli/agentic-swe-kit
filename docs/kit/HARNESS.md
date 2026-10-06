# The harness

**Status:** living · kit-owned (a kit update merges this file; a project's deviations go in
`docs/DELTAS.md`).

What each piece of the harness does, where it runs, and how it was proven. The reasoning is in
`PHILOSOPHY.md`; applying and customising it is in `SETUP.md`.

## 1. Toolchain

Versions are pinned by `uv.lock`; `make install` refuses a stale lock. The ones the kit ships
(2026-10-06): uv 0.11 · Python 3.13.12 · ruff 0.16 · basedpyright 1.40 · pytest 9.1 + pytest-asyncio
+ pytest-cov · coverage 7.16 · hypothesis 6.168 · import-linter 2.15 · mutmut 3.8 · diff-cover 10.6
· prek 0.5 · betterleaks 1.9.

| Tool | Role | Why this one |
|---|---|---|
| uv | environment + lockfile | `uv run` means no global installs; the lock is the single source of versions |
| Python, pinned to the patch in `.python-version` | interpreter | local and CI run the same interpreter; a patch bump is a one-line PR |
| ruff | format + lint | one tool; `*.md` excluded from `ruff format`, which formats Markdown code blocks since 0.16 |
| basedpyright, `strict` | types | pyright semantics without a Node install; strict is the point |
| pytest + hypothesis | tests | property tests for pure code; a `gate` profile with fixed examples so the gate answers the same everywhere |
| coverage + pytest-cov | branch coverage | floor `fail_under = 90` in `pyproject.toml`, the only place it is set |
| diff-cover | changed-lines coverage | `--branch-coverage --fail-under=95` on PRs (CI only) |
| import-linter | architecture contracts | contracts in `pyproject.toml`; `lint-imports` |
| mutmut | mutation testing | **exits 0 even with survivors** — the gate reads `mutmut export-cicd-stats`; its cache goes stale on test-only changes, so `make mutate` starts clean |
| prek | git hooks | runs `.pre-commit-config.yaml` from the uv-managed environment |
| betterleaks | secret scan | gitleaks' successor; a bare AWS key ID is **not** flagged, a key ID with its secret is |

## 2. Make targets

| Target | Runs | Budget |
|---|---|---|
| `install` | `uv sync --locked --all-groups` | — |
| `fmt` | `ruff format` + `ruff check --fix` (deliberate, human-triggered) | s |
| `lint` | `ruff check` + `ruff format --check` | s |
| `types` | `basedpyright` | s |
| `test` | `pytest -m "not live and not eval and not prove"` | s |
| `cov` | `test` with branch coverage, floor from `pyproject.toml`, XML + terminal report | s |
| `arch` | `lint-imports` | s |
| **`check`** | `lint` + `types` + `arch` + `cov` — **the gate** | < 60 s, or split fast/slow |
| `mutate` | clean `mutants/` → `mutmut run` (+ `MUTANTS=` filter) → `export-cicd-stats` → `scripts/mutation_gate.py` | min |
| `prove` | every gate shown red on a planted defect in a throwaway clone, then green (`tests/prove/`, marker `prove`) | min |
| `help` | lists targets with their `##` comments, project ones included | — |

Project-owned targets (`run`, `eval`, deploy, …) live in `project.mk`, which the Makefile includes
and a kit update never touches. The marker expression in `test` and `cov` is the gate's definition of
"the tests"; `scripts/integrity.py` collects with the same one, and `tests/harness/test_gate_lists.py`
keeps them in step.

## 3. Gates — what, where, threshold, proof

| Gate | Threshold | Stop hook | pre-commit | CI (PR) | Planted defect (`make prove`) |
|---|---|---|---|---|---|
| ruff format / lint | clean | ✓ | ✓ | ✓ | an unformatted line; an unused import |
| basedpyright strict | 0 errors | ✓ | ✓ | ✓ | an unannotated parameter (strict rejects it, the other modes do not) |
| pytest | all pass | ✓ | ✓ | ✓ | `assert 1 == 2` |
| branch coverage (global) | ≥ 90 % | ✓ | ✓ | ✓ | a function with an `if` no test calls |
| import-linter contract | 0 violations | ✓ | ✓ | ✓ | an import from `io` inside `core/` |
| diff-cover (changed lines) | ≥ 95 %, branch | — | — | ✓ | same defect, PR-scoped |
| mutation (changed `core/` modules) | 0 survivors unless `# pragma: no mutate` + reason (which needs the label) | — | — | ✓ (`make mutate` locally) | a test that calls the function and asserts nothing |
| secret scan | none | — | ✓ | ✓ | a fake AWS key ID **with** a secret access key beside it |
| gate-guard | label `gates-approved` present when gate files change; removed by a push that touches one | — | — | ✓ | a PR touching `Makefile` without the label |
| test integrity | no test ID gone, no new skip/xfail, unless `checks-weakened-approved` | ✓ (`integrity.py --tests-only`, after `make check`; the hook reads the label) | — | ✓ (job `integrity`) | delete a `def test_` → the stop is blocked with the vanished ID; committed → CI red without the label |
| escape hatches | no added `# noqa`, `# ruff: disable`, `# type: ignore`, `# pyright: …`, `# pragma: no cover` / `no branch` / `no mutate`, `# fmt: off/skip`, `# isort: skip/off`, unless `checks-weakened-approved` | — | — | ✓ (job `integrity`) | `# noqa` on a line under `src/` |
| the Bash guard | refuses: `rm` on a tracked path, `rm -r/-f` outside the repo and the temp directory, a shell write to a gate file, `git commit --no-verify`, a force-push, a push that lands on the base branch, a label change, `gh api` writes other than PR comments/reviews/thread resolution, `gh alias set` | PreToolUse on Bash | — | — (CI's `gate-guard` and `integrity` are the wall behind it) | `rm -rf ~/x` → exit 2; `rm -r mutants` → allowed |

Thresholds are starting points: raise them from the friction log; never lower one in a feature PR
(it is a gate-file change, so it needs `gates-approved` anyway).

## 4. Architecture contract

The kit ships one contract, in `pyproject.toml`:

```
Core is pure    <pkg>.core may not import <pkg>.io or <pkg>.main
```

`core/` holds the decisions — pure, synchronous, no I/O, no clock; `io/` holds the boundaries;
`main.py` wires them. Add the I/O packages your project uses to `forbidden_modules` (`httpx`,
`sqlalchemy`, `boto3`, …) and add contracts (`layers`, `independence`) as the architecture grows.
`include_external_packages = true` is already set. The contract is what makes `core/` the right
scope for the mutation gate: pure code mutates fast and meaningfully.

## 5. Mutation gate

`mutmut` is configured for `src/<pkg>`, the tests under `tests/`, and the gate's marker expression
(`pytest_add_cli_args`), so the live, eval and prove tests never run inside a mutant run. `make
mutate` deletes `mutants/` first: mutmut keeps a mutant's verdict until the mutated function
changes, so after a test-only change a warm cache reports stale results. `scripts/mutation_gate.py`
reads the stats JSON written by `mutmut export-cicd-stats` and exits non-zero unless every mutant
was killed or timed out: it fails on `survived`, `no_tests`, `suspicious`, `segfault`, an interrupted
check, and on zero mutants — because `mutmut run` itself exits 0. CI mutates only the `core/`
modules changed in the PR, and skips with a message when none of them defines a function.

Three kinds of survivor are usually equivalent mutants, and the answer is to restructure, not to
add `# pragma: no mutate`: a flag read only for its truth and initialised to a value nothing reads;
a bound that a later check re-verifies (compute the exact value instead); a comparison at a boundary
where both branches give the same result (remove the branch).

## 6. CI (`.github/workflows/ci.yml`)

On `pull_request` to the base branch and `push` to it. `$BASE` is `origin/<base>` on a PR and the
previous tip on a push. CI runs the same commands as a developer machine; if the two can disagree,
the gate is worthless.

1. `check`: pinned `setup-uv`, `uv python install` (reads `.python-version`), `make install`, `make
   check`, then `diff-cover coverage.xml --compare-branch="$BASE" --fail-under=95 --branch-coverage`
   (needs `fetch-depth: 0`).
2. `mutation`: changed files under `src/<pkg>/core` that define a function → `make mutate
   MUTANTS=…`; skipped with a message otherwise.
3. `secrets`: betterleaks over the commits of the PR or push (pinned release binary, checksum verified;
   betterleaks publishes no GitHub Action). The version lives in `.pre-commit-config.yaml` and in
   `ci.yml`: keep them in step.
4. `integrity`: `scripts/integrity.py --base "$BASE"`, the script the Stop hook runs; red on a
   vanished test, a new skip, or a new escape hatch unless the PR carries `checks-weakened-approved`.
   If the comparison cannot be made, red regardless of the label.
5. `gate-guard`: red when the PR touches a gate file and lacks `gates-approved`. The approval covers
   what was read: a push (`synchronize`) that touches a gate file the PR itself changes removes the
   label first. A merge of the base into the branch does not expire it for files the PR leaves alone.
   The job is in no concurrency group, so a newer run never cancels an expiry. The gate-file list is
   one regex, kept in step with `GATE_FILES` in `scripts/guard_bash.py` and the `ask` rules in
   `.claude/settings.json` by `tests/harness/test_gate_lists.py`.
6. `prove`: `make prove`.

Known limits, inherent without server-side branch protection: a PR can edit `ci.yml` and delete a
job (it runs from the PR's own workflow); the maintainer's read of the diff is what catches it.

## 7. Git hooks (`.pre-commit-config.yaml`, run by prek)

`ruff format --check` and `ruff check` on staged Python, betterleaks, and `make check` as a local
hook. Hooks check; they never rewrite files (`make fmt` does that). Install with `uv run prek install`
in the development checkout only.

## 8. Claude Code harness

**`AGENTS.md`** — root, ≤ 100 lines, loaded at session start (Claude Code ≥ 2.1.277 reads it
natively, but only when no `CLAUDE.md` exists in the directory or any parent — so never create one).
Order: the gate · the TDD protocol · architecture · work protocol · where things live · facts and
state · models and cost · habits · project rules. Everything above "Project rules" is kit-owned.

**`.claude/settings.json`** (committed; the dev-session allowlist belongs in the repo, versioned and
reviewed; `.claude/settings.local.json` stays gitignored for machine-only tweaks):
- allow: `make`, `uv run|sync|add|lock|python`, read-only git, `git fetch|pull|add|commit`, `git
  switch [-c] <prefix>-*`, `git push [-u] origin <prefix>-*`, `gh pr create --base <base>`, `gh pr
  view|checks|ready|diff`, `gh run view`.
- ask: `gh pr merge`, and an `Edit(...)` rule for every gate file. Only `Edit(path)` rules are matched
  for files, and they cover every editing tool (`Write(path)` rules match nothing).
- deny: force-push, the plain spellings of a push to the base branch, `git reset --hard`, `git commit
  --no-verify`, `gh label`, `gh pr edit --add-label|--remove-label`, `rm -rf ~…`. A deny rule matches
  a spelling; the Bash guard catches the flag wherever it sits. Beware a prefix deny that also covers
  the unit branches: `Bash(git push origin main:*)` would refuse `git push origin main-001-slug`.
- env: `CLAUDE_CODE_SUBAGENT_MODEL` = Sonnet (built-in subagents; a spawn that names a model wins).
- hooks — Python, typed and tested, in `scripts/`, each run as `uv run --project
  "$CLAUDE_PROJECT_DIR" python "$CLAUDE_PROJECT_DIR/scripts/<name>.py"` because hook commands start in
  the session's current directory, which follows `cd`:
  - `PreToolUse` on `Bash` → `guard_bash.py`: the refusals in the gates table. The command line is read
    in one pass the way the shell reads it (quotes, comments, `$( … )`, backticks, here-documents);
    a substitution is judged as a command line of its own; what cannot be read that way is refused.
    The shell is the user's — zsh on a Mac, bash on CI — and the guard's tests ask each installed
    shell whether they agree. If the guard itself fails, the command is refused.
  - `PostToolUse` on `Edit|Write` → `fmt_hook.py`: `ruff format` only, on the edited `.py` (an autofix
    would delete an import added in one edit and used in the next). Never blocks.
  - `Stop` → `stop_gate.py` (timeout 180 s): exit 0 if nothing changed under `src/`, `tests/`,
    `scripts/` or in the gate's config files (working tree, or this branch against `origin/<base>`);
    else `make check`, and on failure exit 2 with the last 40 lines; then `integrity.py --tests-only`,
    and on a vanished or skipped test exit 2 with the list and the label name — unless the branch's PR
    carries `checks-weakened-approved`, read with `gh pr view` as the CI job reads it. Labels it cannot
    read: it blocks. Any failure inside the hook: it blocks (an uncaught exception would exit 1, which
    does not block). **No `stop_hook_active` bypass**: the CLI stops after eight consecutive blocks,
    and that is the only way out.
- Claude Code picks up hook edits while a session runs (file watcher); agent definitions
  (`.claude/agents/*.md`) load at session start. A hook that cannot start does not block: check
  `/hooks` after a change.

**`.claude/agents/plan-reviewer.md`** (`model: sonnet`, `effort: medium`, read-only tools): input =
brief path + PR number. Reports only: a criterion with no test that would fail without the change; a
change outside the brief's scope; a walkthrough the diff contradicts; a `Status: living` document the
diff made stale. Constrained on purpose — an unconstrained reviewer invents work.

**`.claude/skills/review-loop/`** + **`scripts/review.py`**: one command starts each reviewer as a
`claude -p` process with `--model`, `--effort`, a spending cap, a time limit, no advisor, no MCP
servers, in a clone of the PR's head whose `origin` has no push address and whose pre-push hook
refuses every push. The record of each run is a PR comment; records are the memory between rounds.
`--expire <reviewer>` says that a green no longer counts. No default model or effort.

**`.github/pull_request_template.md`**: brief link · **Next steps for the maintainer** (every action
only the maintainer can take, in order, as checkboxes) · **Walkthrough for the maintainer** (≤ 15
lines) · TDD evidence (red output; `make check` green — verbatim, collapsed, trimmed lines marked
`[…]`) · the proofs the brief names · out of scope, noticed · docs made stale and fixed · gate files
changed (`gates-approved`) · checks weakened (`checks-weakened-approved`).

## 9. File ownership — what a kit update touches

| Owner | Files | On `kit.py update` | How a project extends it |
|---|---|---|---|
| **kit-owned** | `kit.py` · `Makefile` · `.claude/**` · `.github/workflows/ci.yml` · `.github/pull_request_template.md` · `.pre-commit-config.yaml` · `scripts/**` · `tests/harness/**` · `tests/prove/**` · `AGENTS.md` · `.gitignore` · `.python-version` · `docs/kit/**` · `docs/briefs/000-TEMPLATE.md` · `docs/decisions/0000-TEMPLATE.md` | three-way merge: base = the old kit rendered with your answers, ours = your file, theirs = the new kit rendered; conflicts stay as markers and are listed | add, don't edit: `project.mk`, `.github/workflows/project.yml`, `docs/DELTAS.md`, the "Project rules" section of `AGENTS.md`; added permission rules merge |
| **mixed** | `pyproject.toml` (your dependencies, the kit's tool configuration) | three-way merge; the kit edits `[tool.*]`, you edit `[project]` and the dependency groups | edit freely; a collision is visible |
| **project-owned** | `README.md` · `project.mk` · `src/<pkg>/**` · `tests/conftest.py` · `tests/test_*.py` · `docs/DELTAS.md` · `docs/ROADMAP.md` · `docs/FRICTION.md` · `docs/BACKLOG.md` · `docs/decisions/NNNN-*.md` · `docs/research/**` · `uv.lock` · `kit.lock` | never touched (`kit.lock` is rewritten; `uv.lock` is re-locked) | yours |
| **kit-only** | the kit's `README.md`, `CHANGELOG.md`, `LICENSE` (copied to `docs/kit/LICENSE`), the kit's own decisions, briefs, friction log, backlog, roadmap, `docs/templates/**` | removed by `init`; never present in a project | — |

The list lives in `kit.py` (`CATEGORIES`, `SEEDS`); `tests/harness/test_kit.py` checks that every
tracked file of the kit has an owner and every pattern names a file. Two exceptions inside the
categories: `kit.py` is copied **verbatim** (its constants are the kit's placeholders; rendering it
would rewrite them), and `tests/harness/test_kit.py` is kit-only (it tests the kit's own tree).

## 10. Knobs — what `kit.py init` rewrites

| Knob | Kit value | Flag | Where |
|---|---|---|---|
| package | `kitpkg` | `--package` | `src/<pkg>/`; `pyproject.toml` (`name`, hatch path, coverage source, contract modules, mutmut paths); `ci.yml` mutation path; `review.py` work dir; `project.mk`; tests |
| base branch | main (the kit's default) | `--base` | `stop_gate.py`, `guard_bash.py`, `ci.yml` `branches:`, `settings.json` rules, `AGENTS.md`, the skill texts |
| branch prefix | = base | `--branch-prefix` | `settings.json` rules, `review.py`, `AGENTS.md`, the brief template |
| maintainer | `the maintainer` | `--maintainer` | `AGENTS.md`, the PR template, the skill texts, the documents — never a `.py` file: hook messages keep the role phrase, so a rename cannot change how code is formatted |
| python | `3.13.12` | `--python` | `.python-version`, `requires-python`, basedpyright `pythonVersion` |

Each site in a Python, YAML or TOML file carries a `# knob: <name>` comment; JSON rules are rewritten
by exact text. `tests/harness/test_gate_lists.py` asserts that every site names the same value, in
the kit and after `init`. Thresholds and the mutation scope are not knobs: change them in
`pyproject.toml` and `ci.yml` (gate files; `gates-approved`).
