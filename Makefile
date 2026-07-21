PYTHON ?= python3
NPM ?= npm

.PHONY: governance secrets api-test web-test contract integration build test verify m0-smoke acceptance

governance:
	$(PYTHON) scripts/quality/check_governance.py

secrets:
	$(PYTHON) scripts/quality/check_secrets.py

api-test:
	cd services/api && $(PYTHON) -m pytest -q

web-test:
	$(NPM) run test --workspace @pcb-cdso/web -- --run

contract:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

integration:
	cd services/api && $(PYTHON) -m pytest tests/integration -q

build:
	cd services/api && $(PYTHON) -m ruff check src tests && $(PYTHON) -m mypy src
	$(NPM) run typecheck
	$(NPM) run build

test: api-test web-test contract

verify: governance secrets test build

m0-smoke:
	docker compose down --volumes --remove-orphans
	docker compose up --build --wait
	$(PYTHON) scripts/quality/verify_m0.py
	$(NPM) run e2e

acceptance:
	$(PYTHON) scripts/quality/check_governance.py --acceptance-ready $(MILESTONE)
