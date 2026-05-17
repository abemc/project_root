#!/usr/bin/env bash
set -euo pipefail

# Setup script to install ddgs and optionally Tavily into the project virtualenv
# Usage: ./scripts/setup_search_providers.sh

VENV_DIR=".venv"
PIP="${VENV_DIR}/bin/pip"
PYTHON="${VENV_DIR}/bin/python"

if [ ! -x "${PIP}" ]; then
  echo "Virtualenv not found at ${VENV_DIR}. Activate your venv or create one with: python -m venv ${VENV_DIR}" >&2
  exit 1
fi

WITH_TAVILY=0
if [ "${1:-}" = "--with-tavily" ]; then
  WITH_TAVILY=1
fi

echo "Installing ddgs into ${VENV_DIR}..."
${PIP} install --upgrade pip
${PIP} install ddgs

if [ "${WITH_TAVILY}" -eq 1 ]; then
  echo "Attempting to install Tavily client into ${VENV_DIR}..."
  # The Tavily package name may vary; try common names. If unavailable, instruct user.
  if ${PIP} install tavily; then
    echo "Tavily package installed (tavily)."
  else
    echo "Failed to install package 'tavily' via pip. Please consult vendor docs for the correct package name and install manually." >&2
  fi
  echo "Remember to set TAVILY_API_KEY in your environment before running the app."
fi

echo
echo "Done. To verify ddgs run:" 
echo "  ${PYTHON} -c \"from ddgs.ddgs import DDGS; print('ddgs OK')\""
echo
echo "If you installed Tavily, verify import with:" 
echo "  ${PYTHON} -c \"from tavily import TavilyClient; print('tavily OK')\""

exit 0
