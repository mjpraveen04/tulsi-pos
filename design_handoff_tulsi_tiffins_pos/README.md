# Handbook: Tulsi Tiffins POS — Full-Stack Build

**A developer handbook for building the production system with Claude Code.**

This bundle turns the Phase‑1 conception report and the clickable HTML prototype into a step‑by‑step build guide. Hand the whole folder to Claude Code and work through it work‑package by work‑package.

---

## 0. How to use this bundle with Claude Code

1. Create an empty git repo and drop this whole `design_handoff_tulsi_tiffins_pos/` folder inside it (or open it directly).
2. Copy `CLAUDE.md` to the **root** of your repo. It holds the standing rules Claude Code must follow on every task.
3. Open Claude Code in the repo and paste the **WP1** prompt from `prompts.md`. Build one work package at a time, in order (WP1 → WP9). Do not skip ahead — later packages depend on earlier ones.
4. After each package, run the tests listed in Section 9 before moving on. The concurrency and rollback tests (NFR‑04 / NFR‑05) are **release gates** — the build is not done until they pass.

### About the files in this bundle
- `Cafe POS.dc.html` and `photos/` are a **design reference** — an HTML prototype showing the intended look, layout and behaviour. **Do not ship the HTML.** Rebuild every screen as React components in the Vite app described here.
- The prototype is **high‑fidelity** for visuals: colours, type, spacing and copy are final. Recreate them faithfully, then wire them to the real API.
- This README is the single source of truth for scope, data model, API and rules. Where the prototype and this document disagree, **this document wins** (e.g. the prototype keeps state in memory; the real app must use PostgreSQL through the API).

---

## 1. What we are building

A self‑hosted, tablet‑friendly POS + inventory web app for a single‑counter café, priced and taxed in **INR (₹)**. It unifies five jobs behind one PIN login: **Register, Inventory, Orders, Staff, Payments.** Every sale updates stock atomically and is recorded with a full audit trail.

**Two roles.** `MANAGER` (full access) and `CASHIER` (Register + payments only). Role is enforced **server‑side on every endpoint**, not just hidden in the UI.

**The core guarantee:** stock can never go negative, even under concurrent billing, and every bill + its lines + its stock movements are written in one all‑or‑nothing transaction.

### In scope (MVP)
PIN login + 2 roles · staff management · product/inventory CRUD with an append‑only stock ledger · stock‑aware Register · atomic transactional billing · cash (with change) + UPI static‑QR payments · searchable order history with receipt view.

### Explicitly out of scope (do not build — deferred)
Automated UPI gateway/webhook verification · supplier purchase orders · analytics/charts dashboards · table & reservation management. If asked to add these, log them for a later phase instead.

---

## 2. Technology stack (locked — from the report, Table 8)

Do not substitute. This stack is a graded requirement.

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11 (backend), JavaScript/JSX (frontend) | |
| Frontend | **React 18 + Vite** | SPA, five screens. `react-router-dom` for routing, **TanStack Query** for data fetching. |
| Backend | **FastAPI** | REST, async, Pydantic request/response models (NFR‑10). |
| Database | **PostgreSQL 16** | ACID + row‑level locking underpin the no‑oversell guarantee. |
| ORM / migrations | **SQLAlchemy 2.x + Alembic** | Versioned schema history (NFR‑17). |
| Auth / hashing | **python‑jose** (JWT) + **passlib[bcrypt]** (PIN hashing) | Salted hashes only; no plaintext PINs (FR‑07, NFR‑09). |
| UPI QR | **qrcode** (Python) | Render the café's static UPI QR at checkout. No external gateway. |
| Testing | **pytest** + manual test cases | Concurrency & rollback tests are release gates. |
| Packaging | **Docker Compose** | One command brings up web + api + db (NFR‑14/15). |
| Tooling | Git + GitHub, VS Code | Track each WP against its FR IDs. |
| Hosting (final) | Same Compose stack on a small VM (Lightsail / DigitalOcean / Hetzner) | Public URL for the demo. |

---

## 3. Repository structure

Keep routing, business logic and data access in **distinct layers** (NFR‑16). Frontend and backend are independently deployable and talk **only over REST** (NFR‑15).

```
tulsi-tiffins-pos/
├── docker-compose.yml
├── CLAUDE.md
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml            # or requirements.txt
│   ├── alembic/                  # migrations
│   ├── app/
│   │   ├── main.py               # FastAPI app + router registration
│   │   ├── config.py             # settings from env (JWT secret, DB URL, UPI ID)
│   │   ├── db.py                 # engine, session dependency
│   │   ├── models/               # SQLAlchemy models (data-access layer)
│   │   ├── schemas/              # Pydantic request/response models
│   │   ├── routers/              # HTTP routes only — thin (auth, staff, products, stock, bills, orders)
│   │   ├── services/             # business logic — auth, inventory, billing, ledger, payment
│   │   ├── security.py           # JWT issue/verify, PIN hash/verify, role dependency
│   │   └── seed.py               # demo users + café menu
│   └── tests/                    # pytest: money maths, deduction, concurrency, rollback, RBAC
└── frontend/
    ├── Dockerfile
    ├── index.html
    ├── vite.config.js
    ├── package.json
    └── src/
        ├── main.jsx
        ├── api/client.js         # single axios/fetch client that attaches the JWT
        ├── auth/                 # auth context, PIN login, route guards
        ├── components/           # shared UI (buttons, cards, modal, toast)
        ├── screens/              # Login, Register, Inventory, Orders, Staff
        └── theme.js              # design tokens (Section 7)
```

**Layering rule (enforce in review):** routers never touch the ORM directly — they call services; only services use the models/session. This satisfies NFR‑16 and keeps the billing transaction in one place.

---

## 4. Data model (domain model → schema)

The **StockMove ledger is the single source of truth for stock.** `product.stock` is a cached convenience column kept in step with the ledger inside the same transaction; every reconciliation test compares the sum of moves to it (NFR‑06).

### Entities

**User**
- `id` PK · `name` · `role` enum(`MANAGER`,`CASHIER`) · `pin_hash` (bcrypt, salted) · `is_active` bool (default true) · `created_at`
- Never store the PIN in plaintext (FR‑07). `is_active=false` blocks login but keeps history (FR‑11).

**Product**
- `id` PK · `name` · `category` · `price` **NUMERIC(10,2)** · `stock` INT · `reorder_level` INT (default 5) · `photo_url` nullable · `is_archived` bool (default false) · `created_at`
- Archived products are hidden from the Register but remain on old bills (FR‑14).
- **CHECK (`stock` >= 0)** — a database‑level backstop for the no‑oversell guarantee (TR‑01).

**Bill**
- `id` PK · `bill_no` INT unique sequential (FR‑24) · `cashier_id` FK→User · `subtotal` NUMERIC(10,2) · `gst` NUMERIC(10,2) · `total` NUMERIC(10,2) · `created_at`
- One Bill has many BillLines and exactly one Payment.

**BillLine**
- `id` PK · `bill_id` FK · `product_id` FK · `qty` INT · `unit_price` NUMERIC(10,2) — **price‑at‑time‑of‑sale**, copied on create so later price edits never change history (FR‑25). · `line_total` NUMERIC(10,2)

**Payment**
- `id` PK · `bill_id` FK unique · `method` enum(`CASH`,`UPI`) · `tendered` NUMERIC(10,2) nullable (cash only) · `change_due` NUMERIC(10,2) nullable · `created_at`

**StockMove** (append‑only ledger — never UPDATE or DELETE)
- `id` PK · `product_id` FK · `delta` INT (signed: +receive, −remove, −sale) · `reason` enum(`RECEIVE`,`REMOVE`,`SALE`,`OPENING`) · `bill_id` FK nullable (set for SALE moves) · `user_id` FK (who did it) · `created_at`
- Auditability: every move records acting user + timestamp (NFR‑18).

### Money rule
Use **Decimal / NUMERIC everywhere for money — never float** (TR‑04). GST is **5%**. `subtotal = Σ line_total`, `gst = round(subtotal * 0.05, 2)`, `total = subtotal + gst`. Round half‑up to 2 dp.

---

## 5. API contract

All routes are under `/api`. Every endpoint **except `POST /api/auth/login`** requires a valid JWT (NFR‑07); missing/expired tokens → **401**, wrong role → **403** (FR‑04/06, NFR‑11). Token lifetime ≈ 8 h / one shift (NFR‑08). All input validated server‑side with Pydantic (NFR‑10).

Legend: 🔓 any authenticated user · 🟢 MANAGER only.

### Auth — FR‑01…08
- `POST /api/auth/login` — body `{ user_id, pin }` → `{ access_token, user:{id,name,role} }`. Invalid PIN → 401, no session (FR‑01). JWT carries user id + role (FR‑02).
- `GET  /api/auth/me` 🔓 — current user from token.
- `POST /api/auth/logout` 🔓 — client discards token; endpoint exists for symmetry (FR‑08).
- `GET  /api/users/pin-targets` — list of `{id,name,role}` for the login screen picker (no hashes).

### Staff — FR‑09…11 🟢
- `GET    /api/users` — list staff.
- `POST   /api/users` — `{ name, role, pin }` → creates user; new PIN works immediately (FR‑09).
- `PATCH  /api/users/{id}` — change name/role, or `{ pin }` to reset (old PIN stops working) (FR‑10).
- `PATCH  /api/users/{id}/deactivate` — sets `is_active=false` (FR‑11). Guard: cannot deactivate self or the last active manager.

### Products & inventory — FR‑12…18
- `GET    /api/products` 🔓 — query `?q=&category=&include_archived=false`. Returns active products for the Register grid; search/filter within 2 s (FR‑16, NFR‑01).
- `POST   /api/products` 🟢 — `{ name, category, price, opening_stock, reorder_level }`. Creates the product **and** an `OPENING` stock move for `opening_stock` (FR‑12).
- `PATCH  /api/products/{id}` 🟢 — edit details; historical bills keep old price (FR‑13).
- `PATCH  /api/products/{id}/archive` 🟢 — hide from Register, keep in history (FR‑14).
- `POST   /api/products/{id}/stock` 🟢 — `{ delta, reason }` where reason ∈ RECEIVE/REMOVE. One‑tap receive/remove; writes a ledger row and updates cached stock **in one transaction** (FR‑15). Reject if it would drive stock < 0.

### Register / billing — FR‑19…25
- `GET  /api/register/menu` 🔓 — active products grouped/filterable by category with live stock + low‑stock flag (FR‑17/19).
- `POST /api/bills` 🔓 — **the atomic sale.** Body:
  ```json
  {
    "lines": [{ "product_id": 1, "qty": 2 }, ...],
    "payment": { "method": "CASH", "tendered": 500.00 }   // tendered only for CASH
  }
  ```
  Server logic (all inside **one SQLAlchemy transaction**, see Section 6):
  1. `SELECT ... FOR UPDATE` each product row (row‑level lock).
  2. For each line, check `qty <= stock`; if any fails → **rollback**, HTTP 409 `{"detail":"Insufficient stock: only N left"}`, nothing persisted (FR‑23, TC‑03).
  3. Copy `unit_price` from the product now (price‑at‑sale, FR‑25).
  4. Compute subtotal, 5% GST, total (Decimal).
  5. Allocate the next sequential `bill_no` (FR‑24).
  6. Insert Bill, BillLines, Payment; insert a `SALE` StockMove per line (`delta = −qty`, `bill_id` set); decrement `product.stock`.
  7. For CASH, compute `change_due = tendered − total` and require `tendered >= total`.
  8. Commit; return the receipt payload (bill_no, lines with unit_price, subtotal, gst, total, method, change_due, cashier, timestamp).

### Orders / history — FR‑29…30
- `GET /api/bills` 🔓 — query `?date=&bill_no=`; returns matching bills (list) (FR‑29).
- `GET /api/bills/{bill_no}` 🔓 — full receipt with original line prices (FR‑25/29, TC‑08).
- `GET /api/reports/daily-total` 🟢 — `{ date, total }` = sum of that day's bills (FR‑30, Could‑have).

---

## 6. The atomic billing transaction (most important rule)

This is the heart of the system and the top technical risk (TR‑01/02, NFR‑04/05). Implement it once, in `services/billing.py`, and test it hard.

**Requirements:**
- Wrap **bill + lines + payment + stock moves + stock decrement** in a single transaction. Either all rows commit or none (FR‑22, NFR‑05).
- Prevent concurrent oversell: lock each product row with `SELECT ... FOR UPDATE` before checking/decrementing, so two simultaneous bills on the same dish serialise (NFR‑04). Keep the `CHECK (stock >= 0)` constraint as a final backstop.
- On any failure (insufficient stock, DB error), roll back the whole transaction and return a clear, human‑readable message (FR‑23, NFR‑13).
- Do all money maths in `Decimal` (TR‑04).

**Do a technical spike on this first** (report risk TR‑02): a tiny script that fires two simultaneous bills for the last unit and asserts exactly one succeeds. That test is a permanent release gate.

---

## 7. Screens & design tokens (from the prototype)

The prototype (`Cafe POS.dc.html`) is high‑fidelity. Rebuild these five screens in React, matching the visual spec below, then wire to the API. Open the prototype in a browser to see interactions.

### Design tokens (`theme.js`)
```
--bg-app:        #f4f3ef   /* app background (warm off-white) */
--surface:       #ffffff   /* cards, panels, top bar */
--surface-sunk:  #f6f5f1 / #f0efe9   /* insets, chips, steppers */
--ink:           #1a1a18   /* primary text */
--ink-soft:      rgba(0,0,0,.45)      /* secondary text */
--accent:        oklch(0.58 0.11 152) /* brand green — primary buttons, active states */
--accent-ink:    oklch(0.42–0.5 0.11 152) /* green text on light green */
--accent-tint:   oklch(0.96 0.03 152)     /* light green fills */
--warn:          oklch(0.5–0.62 0.14 40–60) /* low-stock amber/orange */
--danger:        oklch(0.5 0.16 30)         /* sold-out / delete red */
Font family:     'Public Sans', system-ui, sans-serif  (weights 400–800)
Radius:          cards 13–18px · pills 20–22px · controls 8–11px
Shadow (card):   0 1px 2px rgba(0,0,0,.04);  modal: 0 20px 60px rgba(0,0,0,.28)
Currency:        ₹, en-IN grouping, 2dp on money
```

### 7.1 Login (FR‑01/02)
Centered card on a soft radial background. Logo tile (green, "तु") + "Tulsi Tiffins / Point of Sale · Staff sign in". A **staff picker** (avatar + name + role, one selectable per row from `GET /users/pin-targets`), a 4‑digit **PIN** field (`type=password`, centered, letter‑spaced), an inline error line, and a full‑width green **Sign in**. On success, store the JWT and route to the role's home (Cashier → Register; Manager → Register with all tabs).

### 7.2 Register / POS (FR‑18…28) — the primary screen
Two panes; on narrow/tablet widths the cart wraps below.
- **Top bar:** logo + name, a tab group (Register always; **Inventory / Orders / Staff only for Manager**), and a right‑side chip showing the signed‑in name + **Sign out**.
- **Menu (left):** category filter chips (All + each category); a responsive grid of product cards. Each card = photo (drop‑in `image-slot` in the prototype; a real `<img src={photo_url}>` in production), category label, **stock badge** (green "N in stock" / amber "N left" at/under reorder / red "SOLD OUT"), name, price. Tapping adds to cart; sold‑out is disabled. The quantity stepper must **stop at available stock** (FR‑18).
- **Cart (right):** "Current Order · #bill_no · cashier", line rows with − / qty / + steppers and line totals, a Clear action, then **Subtotal / GST (5%) / Total** and a full‑width **Charge ₹total** button (disabled when empty).

### 7.3 Payment flow (FR‑26…28) — modal after Charge
Stage 1 **Choose method:** big Cash / UPI buttons + total.
- **Cash:** show Total, an **Amount received** field, and **live Change to return** (`tendered − total`); block "Payment received" until `tendered >= total` (FR‑27, TC‑04).
- **UPI:** show the café's **static UPI QR** (generated from the UPI ID via the `qrcode` lib / an `<img>` of the QR) + the UPI handle; cashier taps **Payment received** to confirm manually (FR‑28, TC‑07).

Only **on "Payment received"** call `POST /api/bills` (this is where stock deducts and the bill is recorded — never before). Then show the **receipt** (items, subtotal/GST/total, method, "Paid by cash/UPI") with **Print receipt** (`window.print()`, receipt‑only print CSS) and **Done**. Cash receipts show no QR.

### 7.4 Inventory (FR‑12…17) — Manager only
"Add a menu item" form (name, category, price ₹, opening stock) → `POST /api/products`. A **Stock levels** table: item, price, in‑stock (amber when ≤ reorder level), and per‑row quantity field + **+ Receive** / **− Remove** → `POST /api/products/{id}/stock`. Include product edit/archive (FR‑13/14) and a **× remove/archive** control. A right‑hand **Activity** feed mirrors recent stock moves (from the ledger) with actor + time.

### 7.5 Orders (FR‑29/30) — Manager only
Summary cards (orders today, items sold, sales total) from `GET /api/reports/daily-total`. An **order history** list searchable by date / bill number (`GET /api/bills`); each row shows #, item summary, time, cashier, total. Opening a bill shows the receipt at **price‑at‑sale** (FR‑25/29).

### 7.6 Staff (FR‑09…11) — Manager only
"Add a team member" (name, role, 4‑digit PIN) → `POST /api/users`. A team list with inline **role** change and PIN **reset** (FR‑10) and **deactivate** (FR‑11). Guard in the UI *and* server: cannot remove yourself or the last active manager.

---

## 8. Build order (work packages — report Table 7)

Build strictly in this order; respect the dependencies. Must‑have work is front‑loaded.

| WP | Scope | Requirements | Depends on |
|---|---|---|---|
| **WP1** | Repo, Docker Compose (web+api+db), .env, Alembic init, seed script, CI | foundation | — |
| **WP2** | Auth & roles: PIN login, JWT issue/verify, bcrypt hashing, role dependency, 401/403 | FR‑01…08, NFR‑07…11 | WP1 |
| **WP3** | Staff management CRUD + guards | FR‑09…11 | WP2 |
| **WP4** | Products + **append‑only stock ledger**, receive/remove, reconciliation | FR‑12…18, NFR‑06 | WP1 |
| **WP5** | Register + **atomic billing transaction** (the spike lives here) | FR‑19…25, NFR‑02 | WP4 |
| **WP6** | Payments: cash change + UPI static QR | FR‑26…28 | WP5 |
| **WP7** | Orders / bill history + daily total | FR‑29…30, NFR‑18 | WP5 |
| **WP8** | Testing & hardening (unit, concurrency, rollback, RBAC, load) | NFR‑01…13 | WP2–WP7 |
| **WP9** | Deployment & docs: clean‑machine Compose, cloud host, README | NFR‑14…17 | WP1, WP8 |

WP4 can run in parallel with WP2/WP3 (it only needs the schema). WP8 runs continuously — test each module as it lands, then a final hardening pass.

---

## 9. Testing (report Section 9)

Automated with **pytest**, committed alongside source, plus the manual UI cases below. Every Must‑have requirement has at least one test. **NFR‑04 (no negative stock under concurrency) and NFR‑05 (full rollback) are release gates.**

### Automated (write these)
- **Money maths:** subtotal/GST/total with Decimal, half‑up rounding (FR‑21).
- **Stock deduction + ledger:** a sale writes a `SALE` move and decrements cached stock; sum of moves == stock (FR‑15/22, NFR‑06).
- **Concurrency gate:** fire two simultaneous bills for the last unit → exactly one succeeds, stock ≥ 0 (NFR‑04).
- **Rollback gate:** inject a failure mid‑transaction → no bill/line/move rows written (NFR‑05).
- **RBAC:** cashier token to a manager endpoint → 403; no token → 401 (FR‑04, NFR‑07/11).
- **Price stability:** edit a product's price after a sale → old bill still shows price‑at‑sale (FR‑25).

### Manual test cases (report Table 9 — use the prototype's figures)
| ID | Req | Scenario | Steps | Expected |
|---|---|---|---|---|
| TC‑01 | FR‑04 | Role enforcement | Log in as Cashier; open Products | Register only; Products blocked (403) |
| TC‑02 | FR‑21 | GST & totals | Add 2× Dosa ₹90, 1× Coffee ₹40, 3× Chai ₹25 | Subtotal ₹295.00, GST ₹14.75, **Total ₹309.75** |
| TC‑03 | FR‑22/23 | Insufficient‑stock rollback | Item X has 3; add 5× and confirm | Rejected "Insufficient stock: only 3 left"; stock still 3; nothing written |
| TC‑04 | FR‑27 | Cash change | Total ₹309.75; tender ₹500 | Change **₹190.25**; bill saved as Cash |
| TC‑05 | FR‑15/22 | Stock deduction & ledger | Dosa=24; sell 2× | Qty→22; a −2 SALE move referencing the bill |
| TC‑06 | FR‑24 | Unique bill number | Confirm two bills | Second = first + 1; no duplicates |
| TC‑07 | FR‑26/28 | UPI payment | Select UPI; QR shows; Mark paid | Bill saved method=UPI; stock deducted; receipt shown |
| TC‑08 | FR‑29/25 | History & price stability | Change price later; open old bill | Receipt shows original price‑at‑sale |

---

## 10. Deployment (NFR‑14…17)

- **Docker Compose** brings up three services: `db` (Postgres, named volume), `api` (FastAPI/uvicorn, runs Alembic migrations on start), `web` (Vite build served by nginx, proxying `/api` to the api service). `docker compose up` from a clean machine must produce a working app (NFR‑14).
- Config via `.env` (see `.env.example`): `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_HOURS=8`, `UPI_ID`, `GST_RATE=0.05`.
- Migrations only via **Alembic** — never auto‑create tables in prod (NFR‑17).
- Seed a manager (PIN 1234) + a couple of cashiers + the café menu so the demo works immediately. **Change/remove demo PINs before any real deployment.**
- Final phase: deploy the same Compose stack to a small VM for a public demo URL.

---

## 11. Requirement → build map (quick index)

- **Auth/RBAC:** FR‑01…08, NFR‑07…11 → Section 5 (Auth), Section 6 guards, WP2, TC‑01.
- **Staff:** FR‑09…11 → Section 5 (Staff), Section 7.6, WP3.
- **Inventory + ledger:** FR‑12…18, NFR‑06/18 → Section 4, Section 5 (Products), Section 7.4, WP4, TC‑05.
- **Billing:** FR‑19…25, NFR‑02/04/05 → **Section 6**, Section 7.2, WP5, TC‑02/03/05/06/08.
- **Payments:** FR‑26…28 → Section 7.3, WP6, TC‑04/07.
- **Orders:** FR‑29/30, NFR‑18 → Section 5 (Orders), Section 7.5, WP7, TC‑08.
- **Deploy:** NFR‑14…17 → Section 10, WP9.

---

*Source of scope & requirements: "Tulsi Tiffins POS — Phase 1 Conception Report" (Praveen M J, 3 Aug 2026). Where this handbook and the report differ, follow the report's requirement IDs; where the handbook and the HTML prototype differ, follow the handbook.*
