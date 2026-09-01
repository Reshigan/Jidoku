.PHONY: setup test api web e2e
# `python` unversioned does not exist on macOS, and the bare `python3` on PATH is not where `make
# setup` put the packages — `make test` died on a machine whose tests had been green all along.
# So: the repo venv if there is one, else whatever python3 is on PATH. Override with PY=...
PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
setup:
	$(PY) -m pip install --break-system-packages -e packages/jidoka-core -e packages/jidoka-adapters -e packages/jidoka-os -e packages/jidoka-compiler -e packages/jidoka-insight -e services/api -e services/agent
test:
	$(PY) -m pytest packages/*/tests services/*/tests -q
api:
	$(PY) -m uvicorn jidoka_api.main:app --reload --port 8099 --app-dir services/api/src
web:
	cd apps/web && npm install && npm run dev
# The console is only proven against a live API; e2e assumes `make api` and `make web` are up.
e2e:
	cd apps/web && npx playwright test
