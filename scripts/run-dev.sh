#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "缺少 .env：请先执行 cp .env.example .env 并填写 DEEPSEEK_API_KEY。"
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r backend/requirements.txt
pnpm install --frozen-lockfile

uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
trap 'kill "$BACKEND_PID" 2>/dev/null || true' EXIT

pnpm dev -- --host 0.0.0.0
