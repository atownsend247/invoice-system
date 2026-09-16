#!/usr/bin/env bash
# Launched by playwright.config.ts as the first webServer entry. Builds a
# throwaway backend (fresh SQLite files under e2e/.tmp/, one seeded login
# user) and execs uvicorn - see CLAUDE.md for why the domain db and the auth
# db are separate files. E2E_BACKEND_PORT / E2E_EMAIL / E2E_PASSWORD come
# from constants.ts via playwright.config.ts's webServer env, not defaulted
# here, so there's one source of truth for the test credentials.
#
# Everything persistent lives under one INVOICE_SYSTEM_STORAGE_DIR (see
# paths.py) - db/invoice_system.db, db/auth.db, and attachments/ all under
# $DATA_DIR - rather than three separate env vars pointed at the same
# directory by hand.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="$SCRIPT_DIR/.tmp"

: "${E2E_BACKEND_PORT:?E2E_BACKEND_PORT must be set}"
: "${E2E_EMAIL:?E2E_EMAIL must be set}"
: "${E2E_PASSWORD:?E2E_PASSWORD must be set}"

rm -rf "$DATA_DIR"
mkdir -p "$DATA_DIR/db"

cd "$REPO_ROOT"

# SqliteAuthStore.open() creates its own schema on first use - no separate
# migration step needed, same as build_application() does for the domain db
# inside the API's own startup below.
uv run python -c "
from sessionkit import AuthService, SqliteAuthStore
AuthService(SqliteAuthStore.open('$DATA_DIR/db/auth.db')).create_user('$E2E_EMAIL', '$E2E_PASSWORD')
"

exec env \
  INVOICE_SYSTEM_STORAGE_DIR="$DATA_DIR" \
  uv run uvicorn invoice_system.api.app:app --host 127.0.0.1 --port "$E2E_BACKEND_PORT"
