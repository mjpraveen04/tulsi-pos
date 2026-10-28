# Tulsi Tiffins POS

A self-hosted, tablet-friendly point-of-sale and inventory web app for a single-counter café,
priced and taxed in INR (₹). Five screens behind one PIN login — **Register, Inventory, Orders,
Staff, Payments** — where every sale updates stock atomically and leaves a full audit trail.

**The core guarantee:** stock can never go negative, even under concurrent billing, and every
bill + its lines + its payment + its stock movements are written in one all-or-nothing
transaction.

Scope, data model, API contract and business rules come from
[`design_handoff_tulsi_tiffins_pos/README.md`](design_handoff_tulsi_tiffins_pos/README.md),
which remains the source of truth. Build rules live in [`CLAUDE.md`](CLAUDE.md).

---

## Quick start

Requires Docker with Compose v2. From a clean checkout:

```bash
cp .env.example .env      # optional — compose has safe defaults for every value
docker compose up --build
```

Then open **http://localhost:5173** and sign in with a demo PIN below.

Three services come up: `db` (Postgres 16 on a named volume), `api` (FastAPI/uvicorn, which
applies Alembic migrations and seeds demo data on start), and `web` (the Vite build served by
nginx, proxying `/api` and `/media` to the api container).

| Service | URL |
|---|---|
| Web app | http://localhost:5173 |
| API | http://localhost:8000/api |
| API docs (Swagger) | http://localhost:8000/docs |

### Demo logins

Seeded automatically on first start, alongside the café menu.

| Name | Role | PIN |
|---|---|---|
| Anita R. | MANAGER | `1234` |
| Ravi K. | CASHIER | `1111` |
| Priya M. | CASHIER | `2222` |

> **Change or remove these demo PINs — and `JWT_SECRET` — before any real deployment.**

---

## Configuration

All config is environment-driven (`.env` at the repo root; see `.env.example`). Every value has
a default baked into `docker-compose.yml`, so `docker compose up` works without a `.env` file.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://tulsi:tulsi@db:5432/tulsi_pos` | Postgres connection |
| `JWT_SECRET` | `dev-secret-change-me` | Token signing key — **change in production** |
| `JWT_EXPIRE_HOURS` | `8` | Token lifetime ≈ one shift |
| `UPI_ID` / `UPI_PAYEE_NAME` | `tulsitiffins@upi` / `Tulsi Tiffins` | Encoded into the static UPI QR |
| `GST_RATE` | `0.05` | GST applied to every bill |
| `WEB_PORT` / `API_PORT` / `DB_PORT` | `5173` / `8000` / `5432` | Host port mappings |

Product photos are uploaded at runtime and stored in PostgreSQL (`product_photos`), so they
survive rebuilds and hosts with a throwaway filesystem. They are deliberately not committed to the repo.

---

## Architecture

```
tulsi-tiffins-pos/
├── docker-compose.yml
├── backend/
│   ├── alembic/            # versioned migrations — the only way the schema changes
│   └── app/
│       ├── models/         # SQLAlchemy models — data access
│       ├── schemas/        # Pydantic request/response validation
│       ├── routers/        # thin HTTP layer — no ORM access
│       ├── services/       # all business logic (billing, inventory, auth, orders…)
│       ├── security.py     # JWT issue/verify, bcrypt PIN hashing, role dependency
│       └── seed.py         # demo staff + café menu
└── frontend/
    └── src/
        ├── api/client.js   # single fetch client that attaches the JWT
        ├── auth/           # auth context + route guards
        ├── components/     # shared UI (modal, payment flow, photo picker)
        ├── screens/        # Login, Register, Inventory, Orders, Staff
        └── theme.js        # design tokens
```

**Layering (NFR-16):** routers are HTTP-only and call services; services own the business logic
and are the only layer that touches models or the session. Frontend and backend talk purely
over REST.

### The invariants this codebase is built around

1. **Atomic billing (FR-22, NFR-04/05)** — `services/billing.py` wraps bill + lines + payment +
   stock moves + stock decrement in a single transaction. Product rows are locked with
   `SELECT … FOR UPDATE` before stock is checked and decremented, so two simultaneous bills for
   the last unit serialise. A DB-level `CHECK (stock >= 0)` is the final backstop.
2. **The ledger is truth (NFR-06)** — stock only ever changes by appending a `StockMove`. Moves
   are never updated or deleted; `product.stock` is a cached mirror written in the same
   transaction. The sum of moves always equals cached stock.
3. **Money is Decimal (TR-04)** — `NUMERIC` in the database, `Decimal` in Python, never float.
   GST is 5%, rounded half-up to 2dp.
4. **Price-at-sale (FR-25)** — `unit_price` is copied onto each bill line at creation, so later
   price edits never rewrite history.
5. **Auth on every endpoint (NFR-07/11)** — everything except `POST /api/auth/login` requires a
   valid JWT (401 without one), and roles are enforced server-side (403), never by hiding a tab.
6. **No plaintext PINs (FR-07)** — bcrypt salted hashes only.

---

## API

All routes are under `/api`. 🔓 = any authenticated user, 🟢 = MANAGER only.

**Auth** — `POST /auth/login` (the only public route) · `GET /auth/me` 🔓 ·
`POST /auth/logout` 🔓 · `GET /users/pin-targets` (login screen picker, no hashes)

**Staff** 🟢 — `GET /users` · `POST /users` · `PATCH /users/{id}` (rename, change role, or reset
PIN) · `PATCH /users/{id}/deactivate` (guarded: never yourself, never the last active manager)

**Products & inventory** — `GET /products` 🔓 (`?q=&category=&include_archived=`) ·
`POST /products` 🟢 (creates the product *and* its `OPENING` ledger move) ·
`PATCH /products/{id}` 🟢 · `PATCH /products/{id}/archive` 🟢 ·
`POST /products/{id}/stock` 🟢 (`{delta, reason}`, reason ∈ `RECEIVE`/`REMOVE`) ·
`POST|DELETE /products/{id}/photo` 🟢 · `GET /products/stock-moves` 🟢 (activity feed)

**Register** — `GET /register/menu` 🔓 (active products by category with live stock and
low-stock flags) · `GET /register/upi-qr` 🔓 (static UPI QR as a PNG data URI) ·
`POST /bills` 🔓 — **the atomic sale**; returns the receipt, or **409** with
`Insufficient stock: only N left` and nothing persisted.

**Orders** — `GET /bills` 🔓 (`?date=&bill_no=`) · `GET /bills/{bill_no}` 🔓 (receipt at
price-at-sale) · `GET /reports/daily-total` 🟢

Interactive docs are at http://localhost:8000/docs while the stack is running.

---

## Testing

The suite runs against a **real PostgreSQL 16** — the release gates exercise `SELECT … FOR
UPDATE`, a real `CHECK` constraint and genuinely concurrent transactions, none of which SQLite
can prove. The test database is created and migrated with Alembic, exactly like production.

```bash
# 1. a Postgres to test against (the compose db is fine)
docker compose up -d db

# 2. a Python environment
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 3. run
.venv/bin/python -m pytest -q
```

If your `db` is published on a non-default host port (`DB_PORT` in `.env`), point the tests at
it:

```bash
TEST_DATABASE_URL="postgresql+psycopg2://tulsi:tulsi@localhost:5433/tulsi_pos_test" \
  .venv/bin/python -m pytest -q
```

**Release gates** (`tests/test_billing_gates.py`) — these must stay green:

- **Concurrency (NFR-04)** — two simultaneous bills for the last unit; exactly one succeeds and
  stock never goes negative.
- **Rollback (NFR-05)** — a failure injected mid-transaction leaves no bill, line, payment or
  stock-move rows behind.

The rest of the suite covers money maths and half-up rounding, stock deduction and
ledger reconciliation, RBAC (401 vs 403), price stability after a price edit, cash change and
UPI payment, photo upload, and order history.

---

## Deployment

The same Compose stack runs unchanged on a small VM (Lightsail / DigitalOcean / Hetzner):

1. Install Docker and Compose, clone the repo.
2. Write a `.env` with a strong `JWT_SECRET`, a real `POSTGRES_PASSWORD`, and the café's real
   `UPI_ID`.
3. `docker compose up -d --build`.
4. Remove or re-PIN the seeded demo staff before going live.
5. Put a TLS-terminating reverse proxy in front of the `web` container for a public URL.

Migrations run automatically on api start (`alembic upgrade head`); the schema is never
auto-created. Seeding is idempotent and controlled by `SEED_ON_START`. Database data,
including uploaded photos, persists on the `tulsi_db_data` volume.
