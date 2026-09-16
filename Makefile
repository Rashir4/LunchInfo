PY := .venv/bin/python

.PHONY: setup scrape fixtures test serve all refresh cron

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

scrape:
	$(PY) -m scraper.main

fixtures:
	$(PY) -m scraper.main --save-fixtures

test:
	$(PY) -m pytest

serve:
	@echo "→ http://localhost:8017"
	$(PY) -m http.server 8017 --directory site

all: scrape test serve

# Refresh this week's menus and fail loudly if the result is unusable.
refresh:
	$(PY) -m scraper.main
	$(PY) -m pytest tests/test_output_schema.py -q

cron:
	@echo "# Refresh menus every weekday at 07:15 — add with: crontab -e"
	@echo "15 7 * * 1-5 cd $(CURDIR) && $(CURDIR)/.venv/bin/python -m scraper.main >> /tmp/lunchmeny.log 2>&1"
