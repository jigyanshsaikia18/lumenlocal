# LumenLocal

Agency-first, GEO-native multi-tenant SaaS for Google Business Profile optimization.
Specs live in [`/docs`](./docs) (start with `00_START_HERE.md`); project rules in [`CLAUDE.md`](./CLAUDE.md).

## Layout

```
backend/     FastAPI (Python 3.11+, Poetry) — app/, tests/
frontend/    Next.js App Router + TypeScript + Tailwind — src/
docs/        Product, architecture, schema, API, backlog specs
docker-compose.yml   Postgres 15 + Redis 7
```

## Quickstart (P0-1 scaffold)

Prerequisites: Docker, Python 3.11+ with Poetry, Node 20+.

### 1. Environment

```bash
cp .env.example .env
cp frontend/.env.local.example frontend/.env.local
```

### 2. Start infrastructure (Postgres + Redis)

```bash
docker compose up -d
docker compose ps        # both services should be "healthy"
```

### 3. Backend (FastAPI on :8000)

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload
# verify: open http://localhost:8000/health  → postgres/redis report "ok"
poetry run pytest        # in a second shell
```

### 4. Frontend (Next.js on :3000)

```bash
cd frontend
npm install
npm run dev
# verify: open http://localhost:3000
```

### Shut down

```bash
docker compose down       # add -v to also drop the data volumes
```
