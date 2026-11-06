# Thin wrapper for Linux and WSL. run_all.py is the real entry point on every platform.
PYTHON ?= python3

.PHONY: tools smoke test corpus e0

tools:
	$(PYTHON) tools/fetch_tools.py

smoke:
	$(PYTHON) run_all.py --smoke

test:
	$(PYTHON) -m pytest -q

corpus:
	PYTHONPATH=src $(PYTHON) -m ota_verifier.formal.research_corpus

e0:
	$(PYTHON) run_all.py --experiment e0_small_campaign
