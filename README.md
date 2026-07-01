# RigBooks v5 — Local CRA-Compliant Trucking Bookkeeping

Full local rebuild of the RigBooks Streamlit app: a FastAPI + SQLite engine
with a modern React dashboard, built for Canadian trucking / oilfield
owner-operators. No cloud, no Streamlit — your books live on your machine.

![stack](https://img.shields.io/badge/FastAPI-SQLite-blue) ![ui](https://img.shields.io/badge/React-Tailwind-38bdf8)

## Quick start

Requires **Python 3.11+**. (Node is only needed if you change the frontend —
a built copy ships in `frontend/dist`.)

```bash
pip install -r backend/requirements.txt
python run.py                     # opens http://localhost:8787
```

First launch shows a **create your account** screen (local auth — credentials
never leave the machine). Data is stored in `~/.rigbooks/rigbooks.db`
(override with `RIGBOOKS_DATA_DIR` or point `DATABASE_URL` at PostgreSQL,
e.g. `postgresql+psycopg://user:pass@host/rigbooks`).

## What's inside

| Area | Features |
|---|---|
| **Dashboard** | Revenue/expense/net KPIs, GST position, monthly P&L chart, **profit-per-km** trend, expense mix, business-use %, dark/light mode, mobile-first |
| **Bank import** | CSV upload (Date, Description, Debit, Credit), auto-classification with user-editable regex rules, idempotent re-import, inline category/status edits with live ITC recalculation |
| **Revenue & invoicing** | Quick revenue entry with GST split-out, customers, line-item invoices with professional PDF, paid invoices auto-book revenue |
| **Expenses** | Cash / personal-account / vehicle / other sources, business-use %, receipt refs, vendor tracking for T4A |
| **Fuel & IFTA** | Litres + jurisdiction per fill-up, quarterly IFTA apportionment (fleet km/L → taxable litres → net tax per jurisdiction) |
| **Trips & mileage** | CRA logbook (date/route/purpose/odometer), business-use %, tiered per-km allowance, per-jurisdiction km for IFTA |
| **Meals & per diem** | Simplified (flat rate/meal) or detailed method, **80% long-haul** vs 50% standard, applied automatically |
| **Home office & phone** | Workspace-in-home by year (ITC excludes GST-exempt costs), phone bills at business % |
| **Reports** | Accountant summary (PDF), Form **GST34** working copy, **T2125** line-level CSV, **IFTA** quarterly, **T4A box 048** candidates (> $500 fees, incl. CCPCs), append-only **audit trail**, full JSON backup/restore |
| **CRA rules engine** | Per-year JSON rule packs, editable in-app; provisional-year fallback with visible warning |

## CRA compliance & annual updates

All tax math flows through `backend/rigbooks/cra/engine.py` using per-year
rule packs in `backend/rigbooks/cra/rules/<year>.json`:

- GST/HST rates per province (AB 5% … NS 14% from Apr 2025)
- ITC recoverability per category (meals 50%/80%, insurance & bank fees 0%, …)
- Mileage tiers ($0.72 / $0.66 after 5,000 km for 2025; $0.70/$0.64 for 2024)
- Meal rates ($23/meal simplified, 3/day max, long-haul 80%)
- T4A threshold ($500, box 048), GST registration threshold ($30,000)
- IFTA fuel-tax $/L per jurisdiction (update quarterly from iftach.org)
- CCA classes (incl. class 16 — 40% for heavy freight trucks), 6-year record retention

**When CRA publishes new rates:** edit them in the **CRA Tax Rules** page
(persisted as overrides, shipped packs stay pristine), or drop in a new
`rules/<year>.json` and restart. Years without a pack fall back to the
latest one and every report shows a *provisional* warning.

## Development

```bash
# Backend (API on :8787)
cd backend && uvicorn rigbooks.main:app --reload --port 8787

# Frontend dev server (hot reload on :5173, proxies /api)
cd frontend && npm install && npm run dev

# Tests — CRA math + full API flows (37 tests)
cd backend && python -m pytest tests

# Production frontend build (output served by the backend)
cd frontend && npm run build
```

### Architecture

```
backend/rigbooks/
  cra/engine.py        # ALL tax math: ITC, mileage, meals, IFTA, T4A, GST34
  cra/rules/*.json     # per-year CRA rule packs (the thing you update yearly)
  classifier.py        # bank-description → category rules (editable in UI)
  models.py            # SQLAlchemy models (SQLite default, PostgreSQL-ready)
  routers/             # auth, transactions, invoices, reports, CRUD factory
  reports/             # aggregation + PDF (reportlab) + CSV exports
frontend/src/
  components/          # UI kit, layout, charts (Recharts), generic CRUD page
  pages/               # dashboard, transactions, invoices, reports, tax rules…
run.py                 # one-command launcher
app.py                 # legacy Streamlit v4 (kept for reference)
```

## Packaging as a desktop app

- **Simplest:** `python run.py` — single process, opens the browser.
- **Single-file exe:** `pip install pyinstaller` then
  `pyinstaller --onefile --add-data "frontend/dist:frontend/dist" --add-data "backend/rigbooks/cra/rules:rigbooks/cra/rules" run.py`
- **Native shell:** wrap the same server with Tauri/Electron pointing at
  `http://localhost:8787` — the API is UI-agnostic.

## Data safety

- SQLite in WAL mode at `~/.rigbooks/` — copy that folder for a full backup,
  or use **Reports → Backup** for a portable JSON export/restore.
- Every create/update/delete/import/export is written to an append-only
  audit log (CRA requires records kept 6+ years).

---
Built for Canadian owner-operators 🇨🇦 — verify current rates at
[canada.ca](https://www.canada.ca/en/revenue-agency.html) before filing.
