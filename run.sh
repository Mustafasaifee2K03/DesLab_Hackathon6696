#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d ".venv" ]]; then
  /usr/bin/python -m venv .venv
fi

source .venv/bin/activate
python -m pip install -r requirements.txt
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
