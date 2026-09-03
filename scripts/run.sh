#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python ]; then
  echo "venv não encontrado. Rode primeiro:" >&2
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/playwright install chromium" >&2
  exit 1
fi
exec .venv/bin/python -m minerador "$@"
