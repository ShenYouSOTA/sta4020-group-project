PYTHON ?= /home/Sota/research/data-analysis/STA4020/.venv/bin/python
TAG ?= latest
COST_BPS ?= 10

.PHONY: help test sample evaluate clean

help:
	@echo "make test            run the unit tests"
	@echo "make sample          end-to-end smoke test on the mock artifacts"
	@echo "make evaluate        run Part 4 on the canonical artifacts (TAG=latest COST_BPS=10)"

test:
	$(PYTHON) -m pytest tests -q

sample:
	$(PYTHON) scripts/run_sample_pipeline.py --cost-bps $(COST_BPS) --tag sample

evaluate:
	$(PYTHON) -m sta4020_project.cli --tag $(TAG) --cost-bps $(COST_BPS)

clean:
	rm -rf part4_evaluation/reports/sample .pytest_cache
