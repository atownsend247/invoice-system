#!/usr/bin/env bash
# Deploys the backend and the already-built frontend (web/dist/) to the
# Proxmox LXC container named by $DEPLOY_HOST. Called from the Jenkinsfile's
# Deploy stage, which exports the DEPLOY_*/BACKEND_*/FRONTEND_* variables
# below and runs this from the repo root. This script doesn't handle SSH
# auth itself - it assumes the Jenkins agent already has working key-based
# SSH access to $DEPLOY_USER@$DEPLOY_HOST (no Jenkins-managed credential
# or plugin involved; `-o BatchMode=yes` below means it fails fast rather
# than hanging on a password prompt if that's not actually set up yet) -
# see docs/deployment.md for how to set that up on the agent.
#
# Assumes the container was already provisioned once by hand: the deploy
# user's public key in ~/.ssh/authorized_keys, uv installed for that user,
# and passwordless sudo for exactly the two commands this script runs
# remotely (restarting the backend service, reloading nginx) - see
# docs/deployment.md for the full one-time setup, including
# invoice-system-api.service and nginx-invoice-system.conf in this
# directory as the starting point for that.
set -euo pipefail

: "${DEPLOY_HOST:?}"
: "${DEPLOY_USER:?}"
: "${BACKEND_DIR:?}"
: "${FRONTEND_DIR:?}"
: "${BACKEND_SERVICE:?}"

target="$DEPLOY_USER@$DEPLOY_HOST"
ssh_opts=(-o StrictHostKeyChecking=accept-new -o BatchMode=yes)

echo "==> Ensuring target directories exist on $DEPLOY_HOST"
ssh "${ssh_opts[@]}" "$target" "mkdir -p '$BACKEND_DIR' '$FRONTEND_DIR'"

echo "==> Syncing backend source"
# --delete keeps the remote tree an exact mirror of what was just tested -
# an old module left behind from a since-removed file is exactly the kind
# of thing that works locally and breaks in prod. .venv/db files are the
# remote's own state, never the deploy's to touch.
rsync -az --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude '*.db' --exclude '*.db-*' \
    src pyproject.toml uv.lock \
    "$target:$BACKEND_DIR/"

echo "==> Installing backend dependencies and migrating the database"
# --no-demo: this is a real deployment, not a throwaway dev/demo instance -
# see CLAUDE.md on why demo data must never land in a real database.
ssh "${ssh_opts[@]}" "$target" "
    set -euo pipefail
    cd '$BACKEND_DIR'
    export PATH=\"\$HOME/.local/bin:\$PATH\"
    uv sync --frozen --no-dev
    uv run invoice-system-cli init-db --no-demo
"

echo "==> Restarting the backend service"
ssh "${ssh_opts[@]}" "$target" "sudo systemctl restart '$BACKEND_SERVICE'"

echo "==> Syncing the built frontend"
rsync -az --delete web/dist/ "$target:$FRONTEND_DIR/"

echo "==> Reloading nginx"
ssh "${ssh_opts[@]}" "$target" 'sudo systemctl reload nginx'

echo "==> Deploy complete"
