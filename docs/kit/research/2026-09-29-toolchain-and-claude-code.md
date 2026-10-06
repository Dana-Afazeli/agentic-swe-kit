# Research notes — Python toolchain and Claude Code CLI (verified 2026-09-29)

**Status:** snapshot (2026-09-29) — not edited; newer findings go in a new dated file.
Carried into the kit from the project it was extracted from; the project-specific sections (Agent
SDK, Telegram) were left behind. Version numbers are what PyPI had on that date; `uv.lock` has
what the kit ships.

How to read this: **docs-verified** means read in current official docs, source or changelogs on
2026-09-29. It is *not* spike-verified: anything load-bearing gets a spike before code relies on it.

## Claude Code CLI (installed 2.1.284) — dev harness facts
- **AGENTS.md** native since 2.1.277 (telemetry-off fix by 2.1.282). Read **only** when no `CLAUDE.md`,
  `.claude/CLAUDE.md` or `CLAUDE.local.md` exists in the cwd or any parent; a parent `AGENTS.md` loads at
  start; a subdirectory `AGENTS.md` loads on demand when a file there is read. `AGENTS.local.md` and
  `.agents/` are not read.
- **Settings precedence:** managed > `--settings` > `settings.local.json` > `settings.json` > user;
  hooks merge. Since 2.1.211, "Yes, don't ask again" writes `.claude/settings.local.json` at the
  repository root (subdirectory sessions included); **in a worktree it uses the main checkout's file**
  (one reason the kit says separate clones, not worktrees). Shared `settings.json` is read from the
  session's primary working directory.
- **Hooks:** Stop blocks with exit 2 or `{"decision": "block", "reason": …}`; `stop_hook_active` is in
  the input; the CLI overrides after 8 consecutive blocks (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`). Matchers:
  `Edit|Write` exact lists or regex; Stop ignores matchers; `MultiEdit` no longer exists. Handler types:
  command, http, mcp_tool, prompt, agent, async.
- **Permission rule paths:** `//abs/path` absolute, `~/…` home, `/path` relative to the project root,
  `path` relative to the current directory.
- **`/code-review`** is built in (`/review` alias): correctness plus reuse/simplification/efficiency;
  levels low|medium|high|xhigh|max|ultra; flags `--fix`, `--comment`, `--post`. `/simplify` and
  `/security-review` are separate.
- Skills hot-reload in the CLI (add/edit/remove applies mid-session; a top-level skills dir created
  after start needs `/reload-skills`).

## Python toolchain (versions on PyPI, 2026-09-29)
- **mutmut 3.8.0** (2026-09-12): py3.14 ok, src layout (`source_paths`; `paths_to_mutate` is the
  deprecated name), incremental, fork-only; macOS needs `use_setproctitle = false` (3.8 defaults it off
  there); **`mutmut run` exits 0 even with survivors** — gate on `mutmut export-cicd-stats` (writes
  `mutants/mutmut-cicd-stats.json` with `survived`, `no_tests`, `suspicious`). Other keys that matter:
  `pytest_add_cli_args` (arguments for every test run — the kit passes the gate's marker expression
  here), `pytest_add_cli_args_test_selection` (was `tests_dir`), `also_copy`, `do_not_mutate`.
  Cosmic Ray 8.7.0 has no changed-files mode and classifiers stop at 3.13.
- **import-linter 2.15** (2026-09-04): `layers` (`|` = independent siblings), `forbidden`
  (`include_external_packages = true` bans third-party imports), `independence`, `protected`,
  `acyclic_siblings`; config in `pyproject.toml` `[[tool.importlinter.contracts]]`; run `lint-imports`.
  tach 0.35.1 and pytestarch 4.0.1 are the alternatives.
- **coverage 7.16.2** (2026-09-27; fixes a 3.14 branch false positive), **pytest-cov 7.1.0**
  (subprocess measurement dropped in 7.0 — use `[run] patch = ["subprocess"]` if ever needed),
  **diff-cover 10.6.0** (`--branch-coverage` since 10.4.0; `--compare-branch`, `--fail-under`).
- **Type checkers:** pyright 1.1.414 (PyPI wrapper downloads Node); **basedpyright 1.40.1** (same
  semantics, bundles its runtime, `typeCheckingMode = "strict"`); ty 0.0.84 beta; pyrefly 1.3.2 stable
  but not the gate here.
- **ruff ≥ 0.16** formats Markdown files, including the Python blocks inside them: exclude `*.md` from
  `ruff format` or prose turns the lint gate red.
- **Hooks/secrets:** pre-commit 4.6.2; **prek 0.5.4** (Rust, reads `.pre-commit-config.yaml`, 0.x);
  lefthook 2.1.x; gitleaks 8.30.1 is "feature complete, security patches only" → **betterleaks**
  (same author; `betterleaks git --pre-commit --redact --staged`). betterleaks publishes no GitHub
  Action: CI downloads the pinned release binary and verifies its checksum.
- **hypothesis 6.168.3** (2026-09-28): py ≥ 3.10; Rust-backed wheels since 6.156.
- **Python 3.13**, pinned to the patch in `.python-version`: with `3.13` alone, two machines installed
  two different patch releases (3.13.12 and 3.13.14) — "same commands" is not "same interpreter".
