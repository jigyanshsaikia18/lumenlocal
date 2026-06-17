# Deploying the LumenLocal MVP (Docker Compose on a VPS)

This runs the whole stack — Postgres, Redis, the FastAPI API, the Celery worker
and beat scheduler, and the Next.js frontend — on a single host with one command.
Only the frontend is exposed publicly; it proxies API calls to the backend over
the internal Docker network, so the browser only ever talks to one origin.

## Prerequisites
- A Linux VPS (e.g. Hetzner CX22, DigitalOcean 2 GB) with Docker Engine + the
  Compose plugin installed.
- Ports 80 (and 443 if you add TLS) open.
- Optional: a domain pointed at the server's IP.

## 1. Get the code and configure
```bash
git clone <your-repo-url> lumenlocal && cd lumenlocal
cp .env.example .env
```
Edit `.env` and set, at minimum:
- `SECRET_KEY` — generate with `openssl rand -hex 32` (the API refuses to start otherwise).
- `POSTGRES_PASSWORD` — a strong password.
- `ENVIRONMENT=production`, `DEBUG=false`.
- `FRONTEND_URL` — your public URL (e.g. `https://app.example.com`).

You can leave the `localhost` hosts in the connection URLs as-is — compose
overrides the DB/Redis hosts to the internal service names automatically.

## 2. Launch
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
This builds the images, starts Postgres + Redis, runs `alembic upgrade head`
once (the `migrate` service — it also provisions the RLS-scoped `lumen_app`
role), then starts the API, worker, beat, and frontend.

Check status and logs:
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
```
The app is now at `http://<server-ip>/` → redirects to `/dashboard` →, if not
authenticated, to `/login`.

Backend liveness (from the host):
```bash
docker compose -f docker-compose.prod.yml exec backend \
  python -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8000/health').read())"
```

## 3. Updating after a `git pull`
```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
```
The `migrate` service re-runs `alembic upgrade head` and applies any new migrations.

## 4. TLS / custom domain (recommended next step)
For HTTPS, put a reverse proxy in front. The smallest path is Caddy (automatic
Let's Encrypt): point a `caddy` service at `frontend:3000`, or run Caddy on the
host. Until then the MVP serves plain HTTP on port 80.

## Security notes before a real launch
- **Rotate the app-role password.** `lumen_app` is created with a dev password in
  `alembic/versions/9029056a7245_tenant_isolation_rls.py`; `APP_DATABASE_URL` in
  `docker-compose.prod.yml` matches it. Change both before going live, and prefer
  injecting it via secrets rather than committing it.
- **Keep `.env` out of git** — it is gitignored; never commit real secrets.
- Postgres and Redis are not published to the host in this compose file; they are
  reachable only on the internal Docker network. Keep it that way.
- OAuth token storage uses the vault `token_ref` indirection per CLAUDE.md — no
  raw tokens land in Postgres.
