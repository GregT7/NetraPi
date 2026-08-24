#!/usr/bin/env bash
# Cloud Agent bootstrap: Python venv with backend, DB, and headless edge-test deps.
# Idempotent. Does not start servers, run migrations, or run tests.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! python3 -c "import venv" 2>/dev/null; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-venv python3-dev
fi

VENV="${ROOT}/.venv"
if [ ! -x "${VENV}/bin/python" ]; then
  python3 -m venv "${VENV}"
fi

"${VENV}/bin/python" -m pip install --upgrade pip setuptools wheel
"${VENV}/bin/python" -m pip install \
  -r src/main/backend/requirements.txt \
  pytest \
  "numpy>=1.26,<2" \
  "opencv-python-headless>=4.8,<5" \
  joblib \
  "scikit-learn==1.6.1"

mkdir -p "${HOME}/.local/bin"
for tool in python python3 pip pytest uvicorn alembic; do
  if [ -x "${VENV}/bin/${tool}" ]; then
    ln -sfn "${VENV}/bin/${tool}" "${HOME}/.local/bin/${tool}"
  fi
done

echo "NetraPi cloud install complete: ${VENV}"
"${VENV}/bin/python" --version
"${VENV}/bin/python" -c "import fastapi, sqlmodel, alembic, numpy, cv2, pytest; print('imports ok')"
