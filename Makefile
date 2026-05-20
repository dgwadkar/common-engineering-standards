# Phase-6 developer-facing automation (docs/02-implementation-plan.md §9 task 6).
#
# Targets:
#
#   make update-golden         Regenerate every `tests/golden/<fixture>/` tree
#                              from the live `source/` corpus. Run this AFTER
#                              an intentional source-rule edit; commit the
#                              resulting `tests/golden/` diff alongside the
#                              source change.
#
#   make explain-golden-diff   Summarize the per-rule delta when the golden
#                              tests fail. Useful for triaging large diffs in
#                              the four concatenated targets (Copilot, Claude
#                              ~2200 lines each).
#
#   make test                  Run the full pytest suite.
#
#   make golden-test           Run only `tests/test_compiler_golden.py`.
#
#   make help                  Print this index.
#
# Phase-6 lesson: the `update-golden` recovery instruction is surfaced in the
# `tests/test_compiler_golden.py` failure message — keep this Makefile in
# lock-step with that text.

PYTHON ?= python
PYTHONPATH := $(PWD)
export PYTHONPATH

# Auto-detect the local venv if present (matches the Phase-2 onward convention).
VENV_PYTHON := $(PWD)/.venv-phase2/bin/python
ifneq (,$(wildcard $(VENV_PYTHON)))
PYTHON := $(VENV_PYTHON)
endif

# Fixture → stack id binding (mirrors tests/test_compiler_golden.py::_FIXTURE_TO_STACK).
GOLDEN_FIXTURES := spring-boot-3-2:java-spring-boot-3 \
                   spring-boot-2-7-legacy:java-spring-boot-2 \
                   nestjs-10:typescript-nestjs-10 \
                   fastapi-0-110:python-fastapi-0-110

.PHONY: help test golden-test update-golden explain-golden-diff release-dry-run

help:
	@echo "Phase-6 developer targets:"
	@echo "  make update-golden         Regenerate tests/golden/* from source/."
	@echo "  make explain-golden-diff   Summarize per-rule deltas after a golden failure."
	@echo "  make test                  Run the full pytest suite."
	@echo "  make golden-test           Run only the golden snapshot tests."
	@echo ""
	@echo "Phase-7 developer targets:"
	@echo "  make release-dry-run       Compute the next version + render CHANGELOG/README"
	@echo "                             previews WITHOUT committing/tagging/pushing. Mirrors"
	@echo "                             the workflow_dispatch dry-run=true branch."

test:
	$(PYTHON) -m pytest tests/ -v

golden-test:
	$(PYTHON) -m pytest tests/test_compiler_golden.py -v

update-golden:
	@echo "Regenerating tests/golden/ from the live source/ corpus..."
	@for pair in $(GOLDEN_FIXTURES); do \
	  fixture=$${pair%%:*}; \
	  stack=$${pair##*:}; \
	  echo "  → fixture=$$fixture  stack=$$stack"; \
	  rm -rf tests/golden/$$fixture; \
	  $(PYTHON) -m compiler --stack $$stack --target all --out tests/golden/$$fixture 2>/dev/null || { \
	    echo "    FAILED for stack $$stack (fixture $$fixture)"; exit 1; \
	  }; \
	done
	@echo "Done. Review the diff with: git diff -- tests/golden/"

explain-golden-diff:
	$(PYTHON) tools/explain_golden_diff.py

# Phase-7 dry-run: compute next version, render CHANGELOG + README into /tmp/
# without touching the live dist/ tree. Useful for previewing what a release
# would produce locally before dispatching release.yml in the GitHub UI.
release-dry-run:
	@set -e; \
	prev=$$(git describe --tags --abbrev=0 --match 'v*' 2>/dev/null || echo "none"); \
	next=$$($(PYTHON) tools/compute_semver_bump.py --print-rationale 2>/dev/null); \
	echo "Previous tag: $$prev"; \
	echo "Next version: $$next"; \
	tmp=$$(mktemp -d); \
	echo "Compiling --all-stacks --target all into $$tmp..."; \
	$(PYTHON) -m compiler --all-stacks --target all --out $$tmp 2>/dev/null; \
	echo ""; \
	echo "=== CHANGELOG.md preview ==="; \
	$(PYTHON) tools/generate_changelog.py --new-version $$next --previous-tag $$prev --dry-run; \
	echo ""; \
	echo "=== README.md preview ==="; \
	$(PYTHON) tools/generate_dist_readme.py --version $$next --dist-root $$tmp --dry-run | head -40; \
	echo ""; \
	echo "(Full preview written to $$tmp — inspect with: ls -la $$tmp)"
