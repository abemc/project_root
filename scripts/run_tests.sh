#!/usr/bin/env bash
set -euo pipefail

PYTHONPATH=. export

if [ "${1:-}" = "real" ]; then
  echo "Running full (real-model) tests"
  TRANSFORMERS_OFFLINE=0 HF_DATASETS_OFFLINE=0 \
    /home/abemc/project_root/.venv/bin/python -m pytest -q
else
  echo "Running mock-vision (fast) tests"
  USE_MOCK_VISION=1 TRANSFORMERS_OFFLINE=1 HF_DATASETS_OFFLINE=1 \
    pytest -q -k "not integration and not e2e and not distributed"
fi
