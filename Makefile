PYTHON ?= python

.PHONY: governance test verify acceptance

governance:
	$(PYTHON) scripts/quality/check_governance.py

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

verify: governance test

acceptance:
	$(PYTHON) scripts/quality/check_governance.py --acceptance-ready $(MILESTONE)
