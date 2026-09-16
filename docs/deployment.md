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
2. Inside the container, install: `nginx`, `curl`, and a `deploy` user:
   ```
   apt update && apt install -y nginx curl rsync
   useradd -m -s /bin/bash deploy
   ```
3. As the `deploy` user, install `uv` (same installer as the Jenkins
   agent): `curl -LsSf https://astral.sh/uv/install.sh | sh`.
4. Add the Jenkins SSH public key to `~deploy/.ssh/authorized_keys`
   (create the matching private key as a Jenkins credential — see below).
5. Let `deploy` restart the backend service and reload nginx without a
   password, and nothing else:
   ```
   echo 'deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart invoice-system-api, /usr/bin/systemctl reload nginx' \
       | sudo tee /etc/sudoers.d/invoice-system-deploy
   ```
   (confirm the `systemctl` path with `which systemctl` on the container —
   distros occasionally differ.)
6. Copy in the example service unit and nginx site config from `deploy/`
   in this repo, following the setup comments at the top of each file:
   `deploy/invoice-system-api.service` and
   `deploy/nginx-invoice-system.conf`. Edit `server_name`/
   `INVOICE_SYSTEM_CORS_ORIGINS` in each to your actual domain.
7. Put nginx behind TLS (certbot/Let's Encrypt or your own CA) — the
   example nginx config deliberately stops at plain HTTP rather than
   guessing how you manage certificates.

## One-time Jenkins setup

1. Plugins: **NodeJS Plugin**, **SSH Agent Plugin**, **Timestamper**, and
   **Workspace Cleanup** (all common; likely already installed on most
   Jenkins instances — JUnit result publishing is bundled with Jenkins
   core, nothing extra needed for that one).
2. **Manage Jenkins → Tools** → add a NodeJS installation named exactly
   `NodeJS 24.21.0` (matching `web/.node-version` — see CLAUDE.md's Node
   version gotcha for why the pin matters; update both together if you
   bump it).
3. **Manage Jenkins → Credentials** → add the deploy user's SSH private
   key as an "SSH Username with private key" credential. Give it the ID
   `proxmox-lxc-ssh` (or change `DEPLOY_SSH_CRED_ID` in the Jenkinsfile to
   match whatever ID you actually used).
4. Create a **Multibranch Pipeline** job pointed at this repo (the
   Jenkinsfile's `when { branch 'main' }` deploy gate assumes
   `env.BRANCH_NAME` is populated, which only a Multibranch job — not a
   plain single-branch Pipeline job — does automatically).
5. Edit the `environment { }` block at the top of the `Jenkinsfile` for
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

## Where uploaded expense attachments live

Supplementary PDFs uploaded against an expense (see `docs/api.md`,
`CLAUDE.md`) are stored on the filesystem, not in SQLite —
`INVOICE_SYSTEM_ATTACHMENTS_DIR` (`invoice-system-api.service` points it at
`/opt/invoice-system/attachments`, a sibling of the two `.db` files, not
inside `src/`). `deploy.sh`'s rsync only ever syncs `src/`/`pyproject.toml`/
`uv.lock` with `--delete`, so — same as the database files — this directory
is never touched by a redeploy; it's something to back up alongside the
`.db` files, not something the pipeline manages. The nginx config's
`client_max_body_size` (`deploy/nginx-invoice-system.conf`) is set to match
the API's own per-file upload cap (`core.py`'s `MAX_ATTACHMENT_SIZE`, 10MB)
— raise both together if that limit ever changes.

## Not done yet

- Infrastructure provisioning (the container itself, `nginx`/`uv`
  installation, the systemd unit/nginx config) is manual, not
  Terraform/Ansible/cloud-init-managed.
- No rollback automation — redeploying the previous commit is the rollback
  path for now.
- No secrets management beyond the one SSH credential; `INVOICE_SYSTEM_*`
  environment variables live in the systemd unit file on the container,
  not a vault.
- No staging environment — `main` deploys straight to the one container
  described here.
