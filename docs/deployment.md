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
2. Inside the container, install: `nginx`, `curl`, a `deploy` user, and the
   native system libraries `pdf.py` needs to render PDFs via WeasyPrint
   (GLib/GObject, Pango, HarfBuzz, fontconfig - not pure Python, see
   "WeasyPrint's native dependency" below):
   ```
   apt update && apt install -y nginx curl rsync \
       libglib2.0-0 libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 \
       libharfbuzz-subset0 libfontconfig1
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
   else:
   ```
   echo 'deploy ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart invoice-system-api, /usr/bin/systemctl reload nginx, /usr/bin/systemctl daemon-reload, /usr/bin/systemctl enable invoice-system-api, /usr/bin/mv /tmp/invoice-system-api.service /etc/systemd/system/invoice-system-api.service, /usr/bin/mv /tmp/nginx-invoice-system.conf /etc/nginx/sites-available/invoice-system, /usr/bin/ln -sf /etc/nginx/sites-available/invoice-system /etc/nginx/sites-enabled/invoice-system, /usr/sbin/nginx -t' \
       | sudo tee /etc/sudoers.d/invoice-system-deploy
   ```
   (confirm the `systemctl`/`mv`/`ln`/`nginx` paths with
   `which systemctl mv ln nginx` on the container — distros occasionally
   differ, `nginx` in particular is often under `/usr/sbin` rather than
   `/usr/bin`.) Restarting the backend service and reloading/syncing
   nginx's config happen on *every* deploy; installing/enabling the
   systemd unit only happens once (see step 6).
6. Nothing left to copy in by hand — `deploy.sh` installs both
   `deploy/invoice-system-api.service` and
   `deploy/nginx-invoice-system.conf` itself. They behave differently,
   though:
   - **`invoice-system-api.service`** is installed once and never
     touched again — it never overwrites an already-installed unit, so
     edit it directly on the container, or delete
     `/etc/systemd/system/invoice-system-api.service` first, to have a
     later deploy pick up local changes to that file. You should still
     edit `INVOICE_SYSTEM_CORS_ORIGINS` in your local checked-out copy
     to your actual domain *before* your first deploy, since whatever's
     committed is what gets copied verbatim that first time.
   - **`nginx-invoice-system.conf`** is re-synced on *every* deploy — the
     committed file always wins. Edit `server_name` in it to your actual
     domain before deploying. See step 7 below for the consequence this
     has for TLS.
7. Put nginx behind TLS (certbot/Let's Encrypt or your own CA) if you want
   HTTPS — the example nginx config deliberately stops at plain HTTP
   rather than guessing how you manage certificates. **Important**: because
   `deploy.sh` re-syncs `nginx-invoice-system.conf` on every deploy (see
   step 6), running `certbot --nginx` (which edits the live config file in
   place to add `listen 443 ssl`/`ssl_certificate` lines) only survives
   until the *next* deploy, which will silently overwrite it back to plain
   HTTP. Either fold whatever certbot adds back into the committed
   `deploy/nginx-invoice-system.conf` yourself, or manage TLS via a
   separate file/mechanism nginx includes (e.g. a second `server {}` block
   in its own file under `/etc/nginx/sites-enabled/`, or a
   `certbot --nginx --pre-hook`/`--deploy-hook` that re-applies the TLS
   directives after every renewal) so it isn't sitting inside the file
   this pipeline overwrites.

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
5. **Install WeasyPrint's native dependencies on the agent itself** — the
   `Backend` stage runs `uv run pytest` (which imports `pdf.py`) directly
   on the Jenkins agent, not inside a fresh container the way a GitHub
   Actions runner works, so this is a one-time step here rather than a
   pipeline step in the `Jenkinsfile`:
   ```
   sudo apt-get update && sudo apt-get install -y --no-install-recommends \
       libglib2.0-0 libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 \
       libharfbuzz-subset0 libfontconfig1
   ```
   See "WeasyPrint's native dependency" below.

## WeasyPrint's native dependency

`pdf.py` renders quote/invoice/expense PDFs via
[WeasyPrint](https://weasyprint.org/) (HTML/CSS in, PDF bytes out) rather
than a pure-Python library — it needs several native system libraries
installed, not just something `uv sync`/`pip install` can pull in on its
own. This needs a step beyond the usual "sync dependencies" in every
environment that renders a PDF, not just the deployed backend:

- **GitHub Actions CI** (`.github/workflows/ci.yml`): an `apt-get install`
  step in both the `backend` job (runs `pytest`, which imports `pdf.py`
  directly) and the `e2e` job (the live backend it spins up serves `GET
  .../pdf` routes) — a fresh VM per run, so this has to be a workflow step,
  every run.
- **The Jenkins agent**: a one-time `apt-get install`, not a `Jenkinsfile`
  step — see "One-time Jenkins setup" above. The agent is long-lived, not
  ephemeral like a GitHub Actions runner.
- **The Proxmox LXC container**: part of the container's one-time
  provisioning — see "One-time Proxmox LXC container setup" above.

The current package list is `libglib2.0-0 libpango-1.0-0 libharfbuzz0b
libpangoft2-1.0-0 libharfbuzz-subset0 libfontconfig1` for Ubuntu/Debian.
**Don't take WeasyPrint's own install docs as the complete list** — they
were the starting point here and turned out to be missing `libglib2.0-0`
(providing `libgobject-2.0-0`) and `libfontconfig1`, only discovered when
a real deploy to a minimal Proxmox LXC container failed with `OSError:
cannot load library 'libgobject-2.0-0'`. GitHub Actions' `ubuntu-latest`
runner didn't catch this — it's a large, fully-provisioned VM image where
GLib and fontconfig are already present as dependencies of other
preinstalled software, so the (at-the-time incomplete) `apt-get install`
step there "worked" without actually proving the package list was
complete. A minimal container is the real test. The authoritative source
for the full list is WeasyPrint's own code, not its docs: the installed
package's `weasyprint/text/ffi.py` calls `_dlopen()` once per native
library it needs (`gobject`, `pango`, `harfbuzz`, `harfbuzz_subset`,
`fontconfig`, `pangoft2`, as of WeasyPrint 70) — re-check that function
directly against whatever version is pinned in `pyproject.toml` when
upgrading it, rather than trusting a docs page (either WeasyPrint's or
this one) to have kept up.

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
  installation) is manual, not Terraform/Ansible/cloud-init-managed. The
  systemd unit and the nginx site config are the two exceptions —
  `deploy.sh` installs/syncs both itself (see above) — but everything
  around them (the container existing at all, `uv` being on `$PATH` for
  the deploy user, nginx itself being installed) is still a manual
  one-time step.
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
