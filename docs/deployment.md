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
4. Generate (or reuse) an SSH keypair for whichever OS user actually runs
   the Jenkins agent process, and add its public key to
   `~deploy/.ssh/authorized_keys` on the container. **No Jenkins
   credential or plugin is involved** — `deploy/deploy.sh` runs plain
   `ssh`/`rsync` and relies entirely on that agent user's own ambient SSH
   setup (`~/.ssh/id_ed25519`, `~/.ssh/config`, an `ssh-agent` already
   running for that account, etc.) to reach the container, exactly as
   running those commands by hand from that account would. Verify it
   directly before wiring up the pipeline — as the Jenkins agent's own
   user, `ssh deploy@<host> whoami` should succeed with no prompt.
5. Let `deploy` run exactly the commands `deploy.sh` needs, and nothing
   else — restarting the backend service and reloading nginx on every
   deploy, plus installing/enabling the systemd unit the first time only
   (see step 6):
   ```
   echo 'deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart invoice-system-api, /usr/bin/systemctl reload nginx, /usr/bin/systemctl daemon-reload, /usr/bin/systemctl enable invoice-system-api, /usr/bin/mv /tmp/invoice-system-api.service /etc/systemd/system/invoice-system-api.service' \
       | sudo tee /etc/sudoers.d/invoice-system-deploy
   ```
   (confirm the `systemctl`/`mv` paths with `which systemctl mv` on the
   container — distros occasionally differ.)
6. Copy in the example nginx site config from `deploy/` in this repo,
   following the setup comments at the top of the file:
   `deploy/nginx-invoice-system.conf`. Edit `server_name` to your actual
   domain. **The systemd service unit doesn't need this manual step** —
   `deploy.sh` installs `deploy/invoice-system-api.service` itself on the
   first deploy (and only the first: it never overwrites an
   already-installed unit, so edit it directly on the container, or
   delete `/etc/systemd/system/invoice-system-api.service` first, to have
   a later deploy pick up local changes to that file) — but you should
   still edit `INVOICE_SYSTEM_CORS_ORIGINS` in your local checked-out copy
   of `deploy/invoice-system-api.service` to your actual domain *before*
   that first deploy runs, since whatever's committed is what gets copied
   verbatim.
7. Put nginx behind TLS (certbot/Let's Encrypt or your own CA) — the
   example nginx config deliberately stops at plain HTTP rather than
   guessing how you manage certificates.

## One-time Jenkins setup

1. Plugins: **NodeJS Plugin**, **Timestamper**, and **Workspace Cleanup**
   (all common; likely already installed on most Jenkins instances — JUnit
   result publishing is bundled with Jenkins core, nothing extra needed
   for that one). No SSH-specific plugin is required — the Deploy stage
   shells out to plain `ssh`/`rsync` and relies on the agent's own ambient
   SSH setup, not a Jenkins-managed credential (see "One-time Proxmox LXC
   container setup" above).
2. **Manage Jenkins → Tools** → add a NodeJS installation named exactly
   `NodeJS 24.21.0` (matching `web/.node-version` — see CLAUDE.md's Node
   version gotcha for why the pin matters; update both together if you
   bump it).
3. Create a **Multibranch Pipeline** job pointed at this repo (the
   Jenkinsfile's `when { branch 'main' }` deploy gate assumes
   `env.BRANCH_NAME` is populated, which only a Multibranch job — not a
   plain single-branch Pipeline job — does automatically).
4. Edit the `environment { }` block at the top of the `Jenkinsfile` for
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
  installation, the nginx config) is manual, not
  Terraform/Ansible/cloud-init-managed. The systemd unit is the one
  exception — `deploy.sh` installs it itself on the first deploy (see
  above) — but everything around it (the container existing at all, `uv`
  being on `$PATH` for the deploy user, nginx installed and pointed at
  `nginx-invoice-system.conf`) is still a manual one-time step.
- No rollback automation — redeploying the previous commit is the rollback
  path for now.
- No Jenkins-managed secret at all for deploy auth — the SSH private key
  lives only in the Jenkins agent's own filesystem (`~/.ssh/`), outside
  Jenkins' credential store entirely, which also means it isn't rotatable
  or auditable through Jenkins the way a stored credential would be.
  `INVOICE_SYSTEM_*` environment variables live in the systemd unit file on
  the container, not a vault either.
- No staging environment — `main` deploys straight to the one container
  described here.
