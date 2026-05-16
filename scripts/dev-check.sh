#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON:-backend/.venv/bin/python}"

"${PYTHON_BIN}" -m pytest backend/tests/test_provider_layer.py backend/tests/test_phase2b_llm.py

(
  cd frontend
  if [[ -n "${FRONTEND_PM:-}" ]]; then
    ${FRONTEND_PM} lint
    ${FRONTEND_PM} build
  elif command -v yarn >/dev/null 2>&1; then
    yarn lint
    yarn build
  elif [[ -x node_modules/.bin/eslint && -x node_modules/.bin/craco ]]; then
    node_modules/.bin/eslint src --max-warnings=0
    node_modules/.bin/craco build
  else
    npx yarn@1.22.22 lint
    npx yarn@1.22.22 build
  fi
)
