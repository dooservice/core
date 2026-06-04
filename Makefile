.PHONY: help install clean test lint lint-fix format format-check typecheck check \
        bump bump-patch bump-minor bump-major

.DEFAULT_GOAL := help

UV   := uv
RUFF := ruff

GREEN  := \033[0;32m
YELLOW := \033[1;33m
CYAN   := \033[0;36m
RED    := \033[0;31m
NC     := \033[0m

CURRENT_VERSION = $(shell grep '^version' pyproject.toml | sed 's/version = "//;s/"//')

help:
	@echo "$(GREEN)dooservice core — Development Commands$(NC)\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / \
	    {printf "  $(YELLOW)%-18s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo "\n$(CYAN)Current version: $(CURRENT_VERSION)$(NC)"

install: ## Install all packages in editable mode
	$(UV) sync

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

test: ## Run tests across all packages
	$(UV) run pytest -v --tb=short || [ $$? -eq 5 ]

lint: ## Run ruff linter
	$(UV) run $(RUFF) check packages/

lint-fix: ## Auto-fix lint issues
	$(UV) run $(RUFF) check --fix packages/

format: ## Format code
	$(UV) run $(RUFF) format packages/

format-check: ## Check formatting without changes
	$(UV) run $(RUFF) format --check packages/

typecheck: ## Run basedpyright
	$(UV) run basedpyright packages/

check: lint format-check ## Lint + format check

bump-patch: ## Bump patch version (1.0.0 → 1.0.1) and release
	@CURRENT=$(CURRENT_VERSION) ; \
	 MAJOR=$$(echo $$CURRENT | cut -d. -f1) ; \
	 MINOR=$$(echo $$CURRENT | cut -d. -f2) ; \
	 PATCH=$$(echo $$CURRENT | cut -d. -f3) ; \
	 NEW="$$MAJOR.$$MINOR.$$((PATCH+1))" ; \
	 echo "$(CYAN)Bumping $$CURRENT → $$NEW$(NC)" ; \
	 $(MAKE) bump VERSION=$$NEW

bump-minor: ## Bump minor version (1.0.0 → 1.1.0) and release
	@CURRENT=$(CURRENT_VERSION) ; \
	 MAJOR=$$(echo $$CURRENT | cut -d. -f1) ; \
	 MINOR=$$(echo $$CURRENT | cut -d. -f2) ; \
	 NEW="$$MAJOR.$$((MINOR+1)).0" ; \
	 echo "$(CYAN)Bumping $$CURRENT → $$NEW$(NC)" ; \
	 $(MAKE) bump VERSION=$$NEW

bump-major: ## Bump major version (1.0.0 → 2.0.0) and release
	@CURRENT=$(CURRENT_VERSION) ; \
	 MAJOR=$$(echo $$CURRENT | cut -d. -f1) ; \
	 NEW="$$((MAJOR+1)).0.0" ; \
	 echo "$(CYAN)Bumping $$CURRENT → $$NEW$(NC)" ; \
	 $(MAKE) bump VERSION=$$NEW

bump: ## Release a specific version: make bump VERSION=1.2.0
	@[ "$(VERSION)" != "" ] || { echo "$(RED)Set VERSION: make bump VERSION=1.2.0$(NC)"; exit 1; }
	@grep -q "## \[$(VERSION)\]" CHANGELOG.md || { \
	    echo "$(RED)Add ## [$(VERSION)] section to CHANGELOG.md before releasing$(NC)"; exit 1; }
	sed -i 's/^version = .*/version = "$(VERSION)"/' pyproject.toml
	git add -A
	git diff --cached --quiet || git commit -m "chore: bump core to $(VERSION)"
	git tag $(VERSION)
	git push origin HEAD
	git push origin $(VERSION)
	@echo "$(GREEN)✓ Core v$(VERSION) released — update agent and orchestrator to tag = \""$(VERSION)"\"$(NC)"
