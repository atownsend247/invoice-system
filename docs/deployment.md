# Deployment

**Status: implemented, basic.** A `Jenkinsfile` at the repo root builds and
tests both the backend and the web client, then (on `main` only) deploys
both to a Proxmox LXC container over SSH. It assumes the container was
already provisioned once by hand — this pipeline deploys code, it doesn't
create infrastructure.

## What the pipeline does

1. **Checkout**.
2. **Install uv** on the Jenkins agent (`curl -LsSf https://astral.sh/uv/install.sh | sh` — idempotent, safe to re-run every build).
3. **Test**, backend and frontend in parallel — the same commands
   `.github/workflows/ci.yml` already runs (`ruff check`, `ruff format
   --check`, `pytest --cov` for the backend; `npm run lint`, `npm test`,
   `npm run build` for the frontend), plus JUnit output so Jenkins gets
   test-result trend graphs.
4. **End-to-end**: the Playwright suite, after the fast unit suites pass —
   same reasoning as `docs/testing-and-ci.md`'s CI shape.
5. On `main` only: **rebuild the frontend** with `VITE_API_BASE_URL` set to
   the production value (the Test stage's build used the default, dev-ish
   one), then **deploy** — `deploy/deploy.sh` over SSH (see below).

A PR or a branch other than `main` runs steps 1–4 and stops there; nothing
is deployed.

## One-time Proxmox LXC container setup

Not automated by this pipeline — do this once per container:

1. Create an LXC container (a Debian/Ubuntu template is simplest), with
   networking such that the Jenkins agent can reach it by hostname/IP over
   SSH. If Jenkins can only reach the Proxmox *host*, not the container
   directly, you'll need `pct exec <vmid> -- <command>` wrapping instead of
   the direct `ssh` calls in `deploy/deploy.sh` — a small adjustment to
   that script, not the Jenkinsfile.
2. Inside the container, install: `nginx`, `curl`, and a `deploy` user (or
   use an existing account, e.g. `root` — whatever you set `DEPLOY_USER`
   to in the Jenkinsfile):
   ```
   apt update && apt install -y nginx curl rsync
   useradd -m -s /bin/bash deploy
   ```
3. As `$DEPLOY_USER`, install `uv` (same installer as the Jenkins agent):
   `curl -LsSf https://astral.sh/uv/install.sh | sh`.
4. **Enable password login for `$DEPLOY_USER` and set its password** —
   this pipeline authenticates with a username/password (via `sshpass`),
   not an SSH key (see `deploy/deploy.sh`):
   ```
   passwd <deploy-user>   # sets the password Jenkins will use to log in
   ```
   Most distros already allow password auth for an ordinary user
   (`PasswordAuthentication yes` in `/etc/ssh/sshd_config`, usually the
   default) — only edit that file if connections get refused. If
   `DEPLOY_USER` is `root` (the Jenkinsfile's own placeholder value),
   you'll also need `PermitRootLogin yes` there specifically — many
   distros default to `PermitRootLogin prohibit-password`, which allows a
   root SSH key but silently rejects a root password — then
   `systemctl restart sshd`. Store that password as a Jenkins credential,
   not a keypair — see "One-time Jenkins setup" below.
5. Let `$DEPLOY_USER` restart the backend service and reload nginx without
   a password, and nothing else:
   ```
   echo 'deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart invoice-system-api, /usr/bin/systemctl reload nginx' \
       | sudo tee /etc/sudoers.d/invoice-system-deploy
   ```
   (substitute your actual `$DEPLOY_USER` for `deploy` above, and confirm
   the `systemctl` path with `which systemctl` on the container — distros
   occasionally differ. Skip this step entirely if `DEPLOY_USER` is
   `root`, which needs no sudo grant to run these commands itself.)
6. Copy in the example service unit and nginx site config from `deploy/`
   in this repo, following the setup comments at the top of each file:
   `deploy/invoice-system-api.service` and
   `deploy/nginx-invoice-system.conf`. Edit `server_name`/
   `INVOICE_SYSTEM_CORS_ORIGINS` in each to your actual domain.
7. Put nginx behind TLS (certbot/Let's Encrypt or your own CA) — the
   example nginx config deliberately stops at plain HTTP rather than
   guessing how you manage certificates.

## One-time Jenkins setup

1. Plugins: **NodeJS Plugin**, **Credentials Binding Plugin**,
   **Timestamper**, and **Workspace Cleanup** (all common; Credentials
   Binding and JUnit result publishing are typically bundled with Jenkins
   core/its default plugin set already — only install manually if
   `withCredentials` isn't recognized in the Deploy stage).
2. **Manage Jenkins → Tools** → add a NodeJS installation named exactly
   `NodeJS 24.21.0` (matching `web/.node-version` — see CLAUDE.md's Node
   version gotcha for why the pin matters; update both together if you
   bump it).
3. Install `sshpass` on the Jenkins **agent** (not the controller, unless
   they're the same machine) — e.g. `apt-get install sshpass` on
   Debian/Ubuntu. `deploy/deploy.sh` shells out to it for password-based
   SSH/rsync and fails fast with a clear message if it's missing.
4. **Manage Jenkins → Credentials** → add the deploy password as a
   **"Secret text"** credential (not "Username with password" — the
   username lives in the Jenkinsfile's own `DEPLOY_USER`, not the
   credential, so a plain secret string is all that's needed). Give it the
   ID `invoices-lxc-password` (or change `DEPLOY_CRED_ID` in the
   Jenkinsfile to match whatever ID you actually used).
5. Create a **Multibranch Pipeline** job pointed at this repo (the
   Jenkinsfile's `when { branch 'main' }` deploy gate assumes
   `env.BRANCH_NAME` is populated, which only a Multibranch job — not a
   plain single-branch Pipeline job — does automatically).
6. Edit the `environment { }` block at the top of the `Jenkinsfile` for
   your actual container hostname/paths — everything under "Proxmox LXC
   deploy target" there.

## Why demo data is never deployed

`deploy.sh` runs `invoice-system-cli init-db --no-demo` explicitly, not
plain `init-db` — `init-db` seeds a year of demo data (including a demo
login with a published password) by default, which is exactly right for a
fresh dev clone and exactly wrong for a real deployment. See CLAUDE.md and
`docs/data-model.md`'s "Demo data" section. Re-running the deploy is safe
either way — migrations are forward-only and idempotent regardless of
`--no-demo`, only the seeding step is skipped.

## Where persistent data lives

Both SQLite databases and uploaded expense-attachment PDFs (supplementary
files uploaded against an expense — see `docs/api.md`, `CLAUDE.md`) live
under one directory, `INVOICE_SYSTEM_STORAGE_DIR` (see `paths.py`) —
`invoice-system-api.service` points it at `/opt/invoice-system/storage`, a
sibling of `src/`, not inside it: `storage/db/invoice_system.db`,
`storage/db/auth.db`, `storage/attachments/`, and (reserved for future
logging output, unused today) `storage/logs/`. `deploy.sh`'s rsync only
ever syncs `src/`/`pyproject.toml`/`uv.lock` with `--delete`, so this whole
directory is never touched by a redeploy — it's something to back up as a
unit, not something the pipeline manages.
`INVOICE_SYSTEM_DB`/`INVOICE_SYSTEM_AUTH_DB`/`INVOICE_SYSTEM_ATTACHMENTS_DIR`
still exist as individual overrides (e.g. putting attachments on different
storage than the databases) if `INVOICE_SYSTEM_STORAGE_DIR`'s one-directory
default isn't the right shape for a particular deployment. The nginx
config's `client_max_body_size` (`deploy/nginx-invoice-system.conf`) is set
to match the API's own per-file upload cap (`core.py`'s
`MAX_ATTACHMENT_SIZE`, 10MB) — raise both together if that limit ever
changes.

## Not done yet

- Infrastructure provisioning (the container itself, `nginx`/`uv`
  installation, the systemd unit/nginx config) is manual, not
  Terraform/Ansible/cloud-init-managed.
- No rollback automation — redeploying the previous commit is the rollback
  path for now.
- No secrets management beyond the one deploy-password credential;
  `INVOICE_SYSTEM_*` environment variables live in the systemd unit file on
  the container, not a vault.
- Password-based SSH auth (rather than a key) is a deliberate tradeoff for
  this deployment, not a default recommendation — it's generally weaker
  (no passphrase-protected key, brute-forceable if exposed, no easy
  per-credential revocation the way removing a key from
  `authorized_keys` is) and needs `sshpass` on the Jenkins agent as an
  extra piece of infrastructure. Switching back to a key (`sshagent` +
  an "SSH Username with private key" credential, reverting
  `deploy/deploy.sh`'s `sshpass -e ssh ...` calls to plain `ssh`/`rsync`
  and restoring `-o BatchMode=yes`) remains the more conventional choice
  if that's ever revisited.
- No staging environment — `main` deploys straight to the one container
  described here.
