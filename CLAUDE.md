# CLAUDE.md — Tulsi Tiffins POS build rules

Standing rules for every task in this repo. Read `design_handoff_tulsi_tiffins_pos/README.md` first — it is the source of truth for scope, data model, API and business rules.

## Stack (do not substitute)
Python 3.11 · FastAPI · PostgreSQL 16 · SQLAlchemy 2.x + Alembic · python-jose (JWT) · passlib[bcrypt] · qrcode · pytest · React 18 + Vite + TypeScript (react-router-dom, TanStack Query) · Docker Compose. This stack is a graded requirement.

The frontend is TypeScript under `strict`: all sources are `.ts`/`.tsx` (never `.jsx`), and every API payload is typed in `frontend/src/types.ts`, which mirrors the Pydantic schemas in `backend/app/schemas/`. Change a schema on the server and change its type there in the same commit. `npm run build` typechecks first, so a mismatch fails the build.

## Non-negotiable rules
1. **Layering (NFR-16):** routers are thin HTTP only → call services → services own business logic and are the only layer that touches models/session. Never query the ORM from a router.
2. **Atomic billing (FR-22, NFR-04/05):** bill + lines + payment + stock moves + stock decrement commit in ONE transaction, or none. Lock product rows with `SELECT ... FOR UPDATE` before checking/decrementing. Keep the DB `CHECK (stock >= 0)`. This is the most important code in the project — implement once in `services/billing.py`.
3. **Ledger is truth (NFR-06):** stock changes ONLY by inserting an append-only `StockMove`. Never UPDATE/DELETE a move. `product.stock` is a cached mirror updated in the same transaction.
4. **Money is Decimal (TR-04):** NUMERIC in the DB, `Decimal` in Python — never float. GST = 5%, round half-up to 2dp.
5. **Price-at-sale (FR-25):** copy `unit_price` onto each BillLine at creation; later product price edits must not change historical bills.
6. **Auth everywhere (NFR-07/11):** every endpoint except `POST /api/auth/login` needs a valid JWT (401 if missing/expired); role checked server-side (403 on wrong role) — never rely on the UI hiding a tab.
7. **No plaintext PINs (FR-07, NFR-09):** bcrypt salted hashes only.
8. **Server-side validation (NFR-10):** all input through Pydantic models.
9. **Migrations only (NFR-17):** schema changes via Alembic; never auto-create tables in prod.

## Scope discipline
Build only the MVP in the README. Do NOT build: automated UPI gateway/webhooks, supplier purchase orders, analytics/charts, table/reservation management. If tempted, log it for a later phase.

## Definition of done for each work package
- Endpoints match the API contract in README Section 5 (status codes included).
- Tests for that WP pass (README Section 9). Concurrency (NFR-04) and rollback (NFR-05) tests are release gates and must stay green.
- `docker compose up` still brings up a working app.

## Prototype
`design_handoff_tulsi_tiffins_pos/Cafe POS.dc.html` + `photos/` are a visual reference only. Recreate the five screens as React components matching the tokens in README Section 7. Do not ship the HTML; do not keep app state in memory — use the API + Postgres.
