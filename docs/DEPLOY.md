# Deployment — Hetzner (all-in-one) + Cloudflare R2

Single Hetzner host runs the whole stack with Docker Compose behind Caddy
(auto-HTTPS). Images are built in GitHub Actions, pushed to GHCR, and pulled
on the server. Images stay on Cloudflare R2.

```
            ┌────────────────────── Hetzner host ──────────────────────┐
 Internet → │ Caddy :443  ──/api/v1/*──►  backend (FastAPI)            │
   (DNS)    │             ──everything else──►  frontend (Next.js)     │
            │             worker (arq)   postgres   redis  [volumes]   │
            └───────────────────────────────────────────────────────────┘
                          images ↔ Cloudflare R2 (kept)
```

## 0. Prerequisites
- Hetzner server (CX22 / 2 vCPU / 4 GB is enough; CX32 for headroom). Ubuntu 24.04.
- A domain with an **A record** → the server's IP (and `www` if wanted).
- Cloudflare R2 bucket + keys (already used in dev).
- GitHub repo with Actions enabled.

## 1. One-time server setup
```bash
# as root, then create a deploy user with docker access
adduser deploy && usermod -aG sudo deploy
# Docker Engine + compose plugin
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy

# Firewall: SSH + HTTP/HTTPS only
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable

# Clone the repo to /opt/darija-ai
git clone https://github.com/YOUR_GH_USER/darija-ai.git /opt/darija-ai
cd /opt/darija-ai

# Create the production env (never commit it)
cp infra/.env.prod.example .env
nano .env   # fill every CHANGE_ME, set DOMAIN, BACKEND_IMAGE, FRONTEND_IMAGE
```
Generate strong secrets: `openssl rand -hex 32` for `ADMIN_JWT_SECRET` and
`NEXTAUTH_SECRET`.

If the GHCR packages are **private**, log in once so the server can pull:
```bash
echo <GHCR_PAT> | docker login ghcr.io -u YOUR_GH_USER --password-stdin
```
(Or make the two packages public in GitHub → Packages.)

## 2. CI/CD configuration (GitHub repo settings)
- **Variables** → `DOMAIN` = `darija-ai.com`
- **Secrets** → `SSH_HOST`, `SSH_USER` (`deploy`), `SSH_KEY` (private key whose
  public half is in the server's `~/.ssh/authorized_keys`)

`CI` runs lint/typecheck/test/build on every push + PR.
`Deploy` (push to `main` or manual) builds images → GHCR → SSHes in and runs
`git pull` + `compose pull` + `alembic upgrade head` + `up -d`.

## 3. First deploy (manual, before CI is wired)
On the server, after `.env` is filled:
```bash
cd /opt/darija-ai
# Build locally OR pull prebuilt images (set *_IMAGE in .env first):
docker compose -f infra/docker-compose.prod.yml --env-file .env pull
docker compose -f infra/docker-compose.prod.yml --env-file .env run --rm backend alembic upgrade head
docker compose -f infra/docker-compose.prod.yml --env-file .env run --rm backend python -m app.scripts.seed_site_settings
docker compose -f infra/docker-compose.prod.yml --env-file .env run --rm backend python -m app.scripts.seed_sources
docker compose -f infra/docker-compose.prod.yml --env-file .env up -d
```
Caddy provisions the TLS cert automatically once DNS points at the host.
Verify: `https://DOMAIN/health` (backend) and `https://DOMAIN/` (site).

## 4. Backups
```bash
chmod +x infra/scripts/backup-postgres.sh
crontab -e
# 30 3 * * * /opt/darija-ai/infra/scripts/backup-postgres.sh >> /var/log/darija-backup.log 2>&1
```
Offsite copy: install `rclone`, configure an `r2:` remote, set `R2_BACKUP_REMOTE`
in `.env` (e.g. `r2:darija-backups`).

Restore: `gunzip -c backups/darija_X.sql.gz | docker compose -f infra/docker-compose.prod.yml exec -T postgres psql -U darija -d darija_ai`.

## 5. Operations
```bash
docker compose -f infra/docker-compose.prod.yml logs -f backend worker
docker compose -f infra/docker-compose.prod.yml ps
docker compose -f infra/docker-compose.prod.yml restart backend
# run the pipeline once by hand
docker compose -f infra/docker-compose.prod.yml run --rm backend python -m app.scripts.process_pending
```

## Notes / limits
- Single host = single point of failure (acceptable for MVP). Take backups seriously.
- `ENVIRONMENT=prod` makes the backend refuse the dev default admin password / JWT secret.
- `NEXT_PUBLIC_*` are baked at **build time** (in CI build-args); `API_BASE_URL`,
  `NEXTAUTH_*`, `AUTH_TRUST_HOST` are read at **runtime** from `.env`.
- The worker + scheduler run as their own container (arq cron: fetch/30m, process/10m, retry/1h).
