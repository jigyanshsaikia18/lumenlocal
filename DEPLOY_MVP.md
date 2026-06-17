# Deploy the MVP demo to a public URL (VPS)

Stands up the full stack behind HTTPS so agencies can click a link and log in.
Demo-grade: real `SECRET_KEY`, rotated DB passwords, automatic TLS. Skips
rate-limiting, backups, and monitoring (add those before a real launch).

**Architecture:** Caddy (`:443`, auto Let's Encrypt) → Next.js frontend →
(internal) FastAPI backend + Celery + Postgres + Redis. Only Caddy is exposed.

---

## 0. Prerequisites
- A Linux VPS (Ubuntu 22.04+) with SSH access and a public IP.
- A domain (or subdomain) you control.

## 1. Point DNS at the VPS  *(do this first — TLS needs it)*
Create an **A record** for your domain → the VPS public IP. Verify it resolves
before continuing (TLS issuance fails otherwise):
```bash
dig +short demo.example.com   # should print your VPS IP
```

## 2. Install Docker on the VPS
```bash
ssh user@YOUR_VPS_IP
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # then log out/in so the group applies
```

## 3. Open the firewall (if ufw is on)
```bash
sudo ufw allow OpenSSH
sudo ufw allow 80,443/tcp
sudo ufw enable
```

## 4. Get the code on the VPS
```bash
git clone <your-repo-url> lumenlocal && cd lumenlocal
git checkout chore/mvp-docker-deploy
```

## 5. Create and fill the `.env`
```bash
cp .env.prod.example .env
# Generate secrets:
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -base64 24)"
echo "APP_DB_PASSWORD=$(openssl rand -base64 24)"
nano .env   # paste the above, set DOMAIN, ACME_EMAIL, FRONTEND_URL,
            # ALLOWED_ORIGINS, and DEMO_PASSWORD
```
`DOMAIN`, `ACME_EMAIL`, `SECRET_KEY`, `POSTGRES_PASSWORD`, `APP_DB_PASSWORD`
are required — compose refuses to start without them.

## 6. Build and start
```bash
docker compose -f docker-compose.vps.yml up -d --build
```
First start: Caddy fetches a Let's Encrypt cert (a few seconds once DNS is live).
Watch progress:
```bash
docker compose -f docker-compose.vps.yml logs -f caddy backend
```

## 7. Seed the demo login
```bash
docker compose -f docker-compose.vps.yml run --rm backend python -m scripts.seed_demo
```
Uses `DEMO_EMAIL` / `DEMO_PASSWORD` from `.env`.

## 8. Verify
Open `https://demo.example.com` — homepage redirects to `/dashboard`, which
bounces you to `/login`. Sign in with the seeded credentials and you land on the
dashboards.
```bash
curl -s -o /dev/null -w "%{http_code}\n" https://demo.example.com   # 307
```

---

## Operating it
```bash
# logs
docker compose -f docker-compose.vps.yml logs -f
# update after a git pull
git pull && docker compose -f docker-compose.vps.yml up -d --build
# stop / start
docker compose -f docker-compose.vps.yml down
docker compose -f docker-compose.vps.yml up -d
```

## Before a real (non-demo) launch
- Add rate limiting, automated Postgres backups, and uptime monitoring.
- Replace the in-memory token vault (`VAULT_URL`) with a real secret store.
- Rotate `SECRET_KEY` + DB passwords and remove the seeded demo account.
- Review `/docs/01_PRD.md §11.1` compliance caveats before enabling live scans.
```
