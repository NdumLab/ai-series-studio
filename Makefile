PYTHON ?= backend/.venv/bin/python
FRONTEND_PM ?= npx yarn@1.22.22
REACT_APP_BACKEND_URL ?= http://localhost:8000

export REACT_APP_BACKEND_URL

.PHONY: backend-test backend-http-test frontend-lint frontend-build dev-check

backend-test:
	$(PYTHON) -m pytest backend/tests/test_provider_layer.py backend/tests/test_phase2b_llm.py backend/tests/test_auth_helpers.py

backend-http-test:
	$(PYTHON) -m pytest backend/tests/backend_test.py

frontend-lint:
	cd frontend && $(FRONTEND_PM) lint

frontend-build:
	cd frontend && $(FRONTEND_PM) build

dev-check: backend-test frontend-lint frontend-build
