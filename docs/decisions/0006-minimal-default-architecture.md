# ADR-0006 — The default architecture is minimal: `core/` pure, `io/` boundaries, one contract

**Status:** accepted 2026-10-06 · **Deciders:** the maintainer

## Context
The project the kit was extracted from uses ports and adapters: `main → (adapters | app) → ports →
domain`, three import-linter contracts, empty subpackages from day one so the contracts are checkable.
That fits a daemon with several external systems. It is heavy for a CLI, a library or a data job, and
a kit that prescribes it would have every project start by deleting layers.

The gates, however, need *some* structure: the mutation gate wants a pure core to mutate cheaply and
meaningfully, and `make arch` needs at least one contract to enforce, or the architecture gate is
decorative.

## Decision
1. The sample package is `src/<pkg>/core/` (the decisions: pure, synchronous, no I/O, no clock, no
   `await`), `src/<pkg>/io/` (the boundaries), and `src/<pkg>/main.py` (wiring).
2. One contract, `Core is pure`: `<pkg>.core` may not import `<pkg>.io` or `<pkg>.main`.
   `include_external_packages = true` is set, so a project adds the I/O packages it uses to the
   forbidden list.
3. The mutation gate's scope in CI is `src/<pkg>/core`.
4. A project that needs ports and adapters adds the layers and the contracts (`layers`,
   `independence`) in `pyproject.toml`; `SETUP.md` says how. The source project's contracts are the
   worked example.

## Consequences
- Every project starts with a checkable architecture rule and a meaningful mutation scope, and with
  nothing to delete.
- "Core is pure" is a blacklist (what it may not import), not an allowlist: `import os` inside
  `core/` passes. An allowlist needs a custom contract type; it is on the backlog, as it was in the
  source project.
- Projects that grow a second boundary should add a contract, not a comment — `AGENTS.md` says so.
