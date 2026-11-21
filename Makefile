# Prefer the project virtualenv when it exists, otherwise the python3 on PATH.
# Nothing here hardcodes a home directory: create the venv with 'make setup'.
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PYTHON_VERSION ?= python3
TAG ?= latest
COST_BPS ?= 10
COST_SWEEP ?= 0,10,30,50

# Let 'python -m sta4020_project...' work without installing the package.
export PYTHONPATH := src

.PHONY: help setup test part3 sample evaluate check-data check-artifacts clean

help:
	@echo "make setup           create .venv and install the package plus pytest"
	@echo "make test            run the unit tests"
	@echo "make part3           build the portfolios from the real artifacts"
	@echo "make sample          end-to-end smoke test on the mock artifacts"
	@echo "make evaluate        run Part 4 on the real artifacts (TAG=latest COST_BPS=10)"
	@echo "make check-data      verify the raw data files are present"
	@echo "make check-artifacts validate the CSVs the other parts deliver"
	@echo "make clean           remove generated reports and caches"

setup:
	$(PYTHON_VERSION) -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests -q

part3:
	$(PYTHON) part3_portfolio/Part3.py

sample:
	$(PYTHON) scripts/run_sample_pipeline.py --cost-bps $(COST_BPS) --tag sample

evaluate:
	$(PYTHON) -m sta4020_project.cli --tag $(TAG) --cost-bps $(COST_BPS) --cost-sweep $(COST_SWEEP)

check-data:
	$(PYTHON) scripts/check_data.py

check-artifacts:
	$(PYTHON) scripts/check_artifacts.py

clean:
	rm -rf part4_evaluation/reports/sample .pytest_cache
