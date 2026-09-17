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
# and passwordless sudo for exactly the commands this script runs remotely
# (restarting the backend service, reloading/testing nginx, syncing the
# nginx config on every deploy, and - the first time only, see below -
# installing the systemd unit) - see docs/deployment.md for the full
# one-time setup, including invoice-system-api.service and
# nginx-invoice-system.conf in this directory as the starting point for
# that.
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

echo "==> Ensuring the systemd service is installed"
# Only installs it if it's missing - never overwrites an already-installed
# unit file, so hand edits made directly on the container (or a
# deliberately different config) survive every later deploy. Delete
# /etc/systemd/system/$BACKEND_SERVICE.service on the container yourself
# first if you want a newer deploy/invoice-system-api.service to actually
# take effect there.
service_file="/etc/systemd/system/$BACKEND_SERVICE.service"
if ssh "${ssh_opts[@]}" "$target" "test -f '$service_file'"; then
    echo "    Already installed, skipping"
else
    echo "    Not found - installing deploy/$BACKEND_SERVICE.service"
    rsync -az -e "ssh ${ssh_opts[*]}" "deploy/$BACKEND_SERVICE.service" "$target:/tmp/$BACKEND_SERVICE.service"
    # enable, not enable --now (unlike the manual command in the .service
    # file's own header comment) - this runs before the code is even
    # synced yet (see below), so nothing should start it early; the
    # "Restarting the backend service" step further down starts it for
    # real, once there's actually something deployed to run.
    ssh "${ssh_opts[@]}" "$target" "
        set -euo pipefail
        sudo mv '/tmp/$BACKEND_SERVICE.service' '$service_file'
        sudo systemctl daemon-reload
        sudo systemctl enable '$BACKEND_SERVICE'
    "
fi

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
    uv run invoice-system-cli init-db 
"

echo "==> Restarting the backend service"
ssh "${ssh_opts[@]}" "$target" "sudo systemctl restart '$BACKEND_SERVICE'"

echo "==> Syncing the built frontend"
rsync -az --delete web/dist/ "$target:$FRONTEND_DIR/"

echo "==> Syncing nginx config"
# Unlike the systemd unit above, this one *does* overwrite on every
# deploy - whatever's committed in deploy/nginx-invoice-system.conf is
# what ends up live. If TLS (or anything else) ever gets added by editing
# this file directly on the container - e.g. certbot's --nginx plugin -
# that config needs to live in the committed file too, or the next deploy
# will silently overwrite it back out.
rsync -az -e "ssh ${ssh_opts[*]}" deploy/nginx-invoice-system.conf "$target:/tmp/nginx-invoice-system.conf"
ssh "${ssh_opts[@]}" "$target" "
    set -euo pipefail
    sudo mv /tmp/nginx-invoice-system.conf /etc/nginx/sites-available/invoice-system
    sudo ln -sf /etc/nginx/sites-available/invoice-system /etc/nginx/sites-enabled/invoice-system
    sudo nginx -t
"

echo "==> Reloading nginx"
ssh "${ssh_opts[@]}" "$target" 'sudo systemctl reload nginx'

echo "==> Deploy complete"
