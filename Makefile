PYTHON ?= python

.PHONY: check test ledger-check projects-validate projects-list projects-check queue help

## check: verify the HARNESS (ledger + config + own tests). Fast, offline.
check: ledger-check projects-validate test
	@echo "HARNESS CHECKS PASSED"

## test: the harness's own tests (pure stdlib, no deps)
test:
	$(PYTHON) -m unittest discover -s tests -q

## ledger-check: consistency gate over registry/approaches.jsonl
ledger-check:
	$(PYTHON) scripts/ledger.py check

## projects-validate: registered project paths exist and are git repos
projects-validate:
	$(PYTHON) scripts/projects.py validate

## projects-list: show registered projects
projects-list:
	$(PYTHON) scripts/projects.py list

## projects-check: run EACH project's own check command (slow, leaves this repo)
projects-check:
	$(PYTHON) scripts/projects.py check

## queue: pending forced-scout / ceiling re-challenge items
queue:
	$(PYTHON) scripts/ledger.py queue

help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //'
