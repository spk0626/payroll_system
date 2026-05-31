#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Zero-downtime deployment script — Syntax Asia Salary System
#
# Run this from the server as syntax_app user after pushing code to Git.
# It pulls the latest code, installs deps, migrates, collects static,
# then restarts Gunicorn gracefully.
#
# Usage:
#   sudo -u syntax_app /var/www/syntax_asia/deploy/deploy.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

APP_DIR="/var/www/syntax_asia"
VENV="$APP_DIR/.venv"
PYTHON="$VENV/bin/python"
PIP="$VENV/bin/pip"

echo ""
echo "═══════════════════════════════════════════"
echo " Deploying Syntax Asia Salary System"
echo " $(date)"
echo "═══════════════════════════════════════════"
echo ""

cd "$APP_DIR"

# ── 1. Pull latest code ───────────────────────────────────────────────────────
echo "→ Pulling latest code..."
git pull origin main
echo "  Done. Current commit: $(git rev-parse --short HEAD)"

# ── 2. Install / update dependencies ─────────────────────────────────────────
echo "→ Installing dependencies..."
"$PIP" install -r requirements/production.txt --quiet
echo "  Done."

# ── 3. Run migrations ─────────────────────────────────────────────────────────
echo "→ Running database migrations..."
"$PYTHON" manage.py migrate --no-input
echo "  Done."

# ── 4. Collect static files ───────────────────────────────────────────────────
echo "→ Collecting static files..."
"$PYTHON" manage.py collectstatic --no-input --clear
echo "  Done."

# ── 5. Check Django system health ─────────────────────────────────────────────
echo "→ Running system check..."
"$PYTHON" manage.py check --deploy
echo "  Done."

# ── 6. Restart Gunicorn (graceful — waits for active requests) ────────────────
echo "→ Restarting Gunicorn..."
sudo systemctl restart syntax_asia
sleep 2

# ── 7. Verify service is up ───────────────────────────────────────────────────
if systemctl is-active --quiet syntax_asia; then
    echo "  Gunicorn is running ✓"
else
    echo "  ERROR: Gunicorn failed to start. Check: sudo journalctl -u syntax_asia -n 50"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════"
echo " Deployment complete ✓"
echo "═══════════════════════════════════════════"
echo ""
