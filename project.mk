# Project-owned make targets, included by the kit's Makefile. `make help` lists them with the kit's.
# Add what your project needs here (run, deploy, migrate, …); a kit update never edits this file.
.PHONY: run eval

run: ## run the program (calls main())
	uv run python -c "import sys; from kitpkg.main import main; sys.exit(main())"

eval: ## model-graded evals, if the project has any; they cost money, so this refuses without KITPKG_EVAL_BUDGET_USD
	@test -n "$$KITPKG_EVAL_BUDGET_USD" || { echo "eval: refusing to run without KITPKG_EVAL_BUDGET_USD (evals cost money)" >&2; exit 2; }
	@echo "no evals yet"
