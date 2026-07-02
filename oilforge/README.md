# OilForge — Corporate Bookkeeping for Oilfield Contractors

Local-first accounting engine + desktop-grade web app for an **incorporated
Canadian contract oilfield operator** who takes compensation as **dividends,
not payroll**. FastAPI + SQLite backend, React + Tailwind frontend, one
command to run, fully offline.

## Quick start

Requires **Python 3.11+** (Node only needed to modify the frontend — a
built copy ships in `frontend/dist`).

```bash
pip install -r backend/requirements.txt
python run.py                     # opens http://localhost:8899
```

First launch creates your local account. Data lives in `~/.oilforge/`
(override with `OILFORGE_DATA_DIR`, or set
`DATABASE_URL=postgresql+psycopg://…` for PostgreSQL).

## The dividend workflow (the heart of the app)

1. **Bank Import** — statements auto-classify; e-transfers/ATM draws to
   personal accounts flag as *Owner Withdrawal*.
2. **One-click posting** puts each draw on the **shareholder loan ledger**
   (running balance, corporation's perspective).
3. The dashboard and Dividends page show **ITA 15(2) exposure** (repay
   within 1 year of fiscal year-end) and **s.80.4 imputed interest** at the
   prescribed rate.
4. At year-end, **declare a dividend settled against the loan** — the
   balance clears, the resolution reference is recorded.
5. Hand the accountant: **T5 slip figures** (boxes 10/11/12 & 24/25/26 with
   gross-up and dividend tax credit), the **dividend register PDF**, and a
   **double-entry journal CSV** (DR/CR accounts for every draw, contribution
   and declaration).

## Everything else

| Area | Features |
|---|---|
| **Jobs & field tickets** | Clients → well sites (LSD) → work orders: day-rate/hourly/fixed, mobilization fees, **holdback %**; field-ticket entries billed straight to progress invoices; live per-job margin |
| **Invoices** | Generated from unbilled entries, GST on full consideration, holdback withheld until released, professional PDF |
| **Equipment & CCA** | Asset registry by CCA class, maintenance logs, full **UCC simulation** per class (AIIP first-year factor, disposals/recapture clamp), utilization hours from field tickets |
| **Expenses** | Corporate categories (camp, PPE, subcontractors, WCB…), ITCs per year-pack, job/equipment tagging for costing |
| **Dashboard** | Cash position, income before tax after CCA, GST line 109, shareholder loan, dividends, monthly cash flow, job margins, equipment hours; dark/light; mobile-first |
| **Reports** | Income statement, **derived trial balance** (balanced, equity plug flagged), GST34 working copy, financial summary PDF, append-only audit trail |
| **Backup** | Full JSON export/restore, optionally **encrypted** (PBKDF2 + Fernet) — plus a data-migration endpoint stub for future QuickBooks/Wave imports |

## CRA rules engine (yearly updatable)

All tax math flows through `backend/oilforge/cra/engine.py` with per-year
packs in `backend/oilforge/cra/rules/<year>.json`:

- Corporate tax rates (federal small-business 9% + provincial; $500k SBD limit)
- Dividend gross-ups (15% / 38%) and federal dividend tax credits
- Shareholder-loan parameters (15(2) window, quarterly **prescribed rate**)
- CCA classes (incl. 38 for power-operated movable equipment) + AIIP factor
- GST/HST rates per province, ITC recoverability per category
- Oilfield deduction guidance (camp/ITA 6(6), PPE, remote travel)

Update rates in the **Tax Rules** page (stored as overrides) or drop in a
new JSON pack. Missing years fall back with a visible *provisional* badge.

**Estimates are estimates** — T2 filing, GRIP/eligible-dividend
designations, and passive-income grinds are your accountant's call. The
app's job is clean records and audit-ready exports (keep 6+ years).

## Development

```bash
cd backend && uvicorn oilforge.main:app --reload --port 8899   # API
cd frontend && npm install && npm run dev                      # UI :5173
cd backend && python -m pytest tests                           # 30 tests
cd frontend && npm run build                                   # ship UI
```

## Packaging

- `python run.py` — single process, opens the browser.
- PyInstaller: `pyinstaller --onefile --add-data "frontend/dist:frontend/dist" --add-data "backend/oilforge/cra/rules:oilforge/cra/rules" run.py`
- Tauri/Electron: point a webview at `http://localhost:8899`.

## Splitting into its own repository

OilForge is fully self-contained in this directory. To make it a
standalone repo with history:

```bash
pip install git-filter-repo
git clone <this-repo> oilforge-repo && cd oilforge-repo
git filter-repo --subdirectory-filter oilforge
git remote add origin <new-repo-url> && git push -u origin main
```

---
Built for incorporated Canadian oilfield operators 🇨🇦 — verify current
rates at canada.ca before filing.
