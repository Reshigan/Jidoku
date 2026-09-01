.PHONY: setup test api web e2e
setup:
	pip install --break-system-packages -e packages/jidoka-core -e packages/jidoka-adapters -e packages/jidoka-os -e packages/jidoka-compiler -e packages/jidoka-insight -e services/api -e services/agent
test:
	python -m pytest packages/*/tests services/*/tests -q
api:
	uvicorn jidoka_api.main:app --reload --port 8099 --app-dir services/api/src
web:
	cd apps/web && npm install && npm run dev
# The console is only proven against a live API; e2e assumes `make api` and `make web` are up.
e2e:
	cd apps/web && npx playwright test
