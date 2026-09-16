#!/usr/bin/env bash
# Deploys the backend and the already-built frontend (web/dist/) to the
# Proxmox LXC container named by $DEPLOY_HOST. Called from the Jenkinsfile's
# Deploy stage, which exports the DEPLOY_*/BACKEND_*/FRONTEND_* variables
# below and runs this from the repo root, inside a `withCredentials` block
# that exposes the deploy password as $SSHPASS - this is username/password
# auth (via `sshpass`), not an SSH key, so this script handles auth itself
# rather than assuming an agent already has a key loaded.
#
# Requires `sshpass` on the Jenkins agent (e.g. `apt-get install sshpass`
# on Debian/Ubuntu) - not installed inline here the way `uv` is in the
# Jenkinsfile's own Install stage, since that's a plain `curl | sh` into
# $HOME and this needs a system package manager (sudo) instead. See
# docs/deployment.md's one-time Jenkins setup.
#
# Assumes the container was already provisioned once by hand: password
# login enabled for $DEPLOY_USER (many distros' default sshd_config only
# permits key-based login - see docs/deployment.md), uv installed for
# that user, and passwordless sudo for exactly the two commands this
# script runs remotely (restarting the backend service, reloading nginx)
# - see docs/deployment.md for the full one-time setup, including
# invoice-system-api.service and nginx-invoice-system.conf in this
# directory as the starting point for that.
set -euo pipefail

: "${DEPLOY_HOST:?}"
: "${DEPLOY_USER:?}"
: "${SSHPASS:?}"
: "${BACKEND_DIR:?}"
: "${FRONTEND_DIR:?}"
: "${BACKEND_SERVICE:?}"

if ! command -v sshpass >/dev/null; then
    echo "sshpass is required for password-based deploy but isn't installed on this agent" >&2
    echo "(e.g. 'apt-get install sshpass' - see docs/deployment.md)" >&2
    exit 1
fi

target="$DEPLOY_USER@$DEPLOY_HOST"
# No BatchMode=yes here, unlike a key-based setup - that option makes ssh
# fail immediately instead of prompting for a password, which would leave
# sshpass nothing to answer and every connection would just fail.
ssh_opts=(-o StrictHostKeyChecking=accept-new)
ssh_cmd=(sshpass -e ssh "${ssh_opts[@]}")

echo "==> Ensuring target directories exist on $DEPLOY_HOST"
"${ssh_cmd[@]}" "$target" "mkdir -p '$BACKEND_DIR' '$FRONTEND_DIR'"

echo "==> Syncing backend source"
# --delete keeps the remote tree an exact mirror of what was just tested -
# an old module left behind from a since-removed file is exactly the kind
# of thing that works locally and breaks in prod. .venv/db files are the
# remote's own state, never the deploy's to touch.
rsync -az --delete \
    --exclude '.venv' --exclude '__pycache__' --exclude '*.db' --exclude '*.db-*' \
    -e "sshpass -e ssh ${ssh_opts[*]}" \
    src pyproject.toml uv.lock \
    "$target:$BACKEND_DIR/"

echo "==> Installing backend dependencies and migrating the database"
# --no-demo: this is a real deployment, not a throwaway dev/demo instance -
# see CLAUDE.md on why demo data must never land in a real database.
"${ssh_cmd[@]}" "$target" "
    set -euo pipefail
    cd '$BACKEND_DIR'
    export PATH=\"\$HOME/.local/bin:\$PATH\"
    uv sync --frozen --no-dev
    uv run invoice-system-cli init-db --no-demo
"

echo "==> Restarting the backend service"
"${ssh_cmd[@]}" "$target" "sudo systemctl restart '$BACKEND_SERVICE'"

echo "==> Syncing the built frontend"
rsync -az --delete -e "sshpass -e ssh ${ssh_opts[*]}" web/dist/ "$target:$FRONTEND_DIR/"

echo "==> Reloading nginx"
"${ssh_cmd[@]}" "$target" 'sudo systemctl reload nginx'

echo "==> Deploy complete"
