.DEFAULT_GOAL := help

.PHONY: help install fmt lint types test cov arch check mutate

# `make mutate MUTANTS="kitpkg.core.text.*"` limits the run to matching mutants.
MUTANTS ?=

help: ## list the targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-8s %s\n", $$1, $$2}'

install: ## create .venv from uv.lock (project + dev tools); fails if the lock is stale
	uv sync --locked --all-groups

fmt: ## rewrite files: ruff format + ruff autofix (deliberate, human-triggered)
	uv run ruff format .
	uv run ruff check --fix .

lint: ## ruff check + ruff format --check (changes nothing)
	uv run ruff check .
	uv run ruff format --check .

types: ## basedpyright, strict mode
	uv run basedpyright

# The marker expression is the gate's definition of "the tests". scripts/integrity.py collects with
# the same one; tests/harness/test_gate_lists.py keeps the two in step.
test: ## pytest, without the live, eval and prove tests
	uv run pytest -m "not live and not eval and not prove"

# The floor is `fail_under` in pyproject.toml ([tool.coverage.report]), the only place it is set.
cov: ## test + branch coverage; fails under the floor in pyproject.toml; writes coverage.xml
	uv run pytest -m "not live and not eval and not prove" --cov --cov-branch --cov-report=term-missing --cov-report=xml

arch: ## import-linter contracts (pyproject.toml, [tool.importlinter])
	uv run lint-imports

check: lint types arch cov ## THE GATE: lint + types + arch + cov

# Always from a clean cache: mutmut 3.8 keeps a mutant's verdict (and its test mapping) until the
# mutated function's source changes, so after a test-only change a warm cache reports stale
# survivors, or stale kills. A gate has to be right first and fast second; CI starts clean too.
# `set -f` passes patterns such as pkg.mod.* to mutmut instead of letting the shell expand them.
mutate: ## mutation testing from a clean cache; fails on survivors or untested mutants (MUTANTS="pattern" to filter)
	rm -rf mutants
	set -f; uv run mutmut run $(MUTANTS)
	uv run mutmut export-cicd-stats
	uv run python scripts/mutation_gate.py

# Project-owned targets (run, eval, deploy, …) live in project.mk. A kit update never touches it.
-include project.mk
