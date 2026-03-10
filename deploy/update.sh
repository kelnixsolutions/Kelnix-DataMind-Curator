#!/usr/bin/env bash
set -euo pipefail

# ── Kelnix DataMind Curator — update deployment ────────────────────────

APP_DIR="/opt/datamind-curator"

cd "$APP_DIR"
echo "=== Pulling latest code ==="
git pull origin main

echo "=== Updating dependencies ==="
source .venv/bin/activate
pip install -r requirements.txt

echo "=== Restarting service ==="
systemctl restart datamind

echo "=== Checking health ==="
sleep 2
curl -s http://localhost:8001/health
echo ""
echo "✅ Update complete!"
