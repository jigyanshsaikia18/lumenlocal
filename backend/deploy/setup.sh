#!/usr/bin/env bash
# One-time VPS setup: venv, deps, migrations. Run from backend/ as the deploy user.
# Assumes Postgres and Redis are already running and DATABASE_URL/APP_DATABASE_URL
# in .env point to them. Re-run after a `git pull` to pick up new deps/migrations.
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

if [ ! -f .env ]; then
  echo "No .env found — copy .env.example from the repo root and fill in real values first." >&2
  exit 1
fi

.venv/bin/alembic upgrade head

echo "Setup complete. Install the systemd units in deploy/*.service, then:"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable --now lumenlocal-api lumenlocal-worker lumenlocal-beat"
