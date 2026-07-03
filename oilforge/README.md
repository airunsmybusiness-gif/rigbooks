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

## The yearly CIBC workflow (start here)

1. **Export the year from CIBC online banking** — chequing and credit card,
   CSV format. No editing needed: OilForge reads CIBC's headerless
   chequing layout (`Date, Description, Debit, Credit`), the credit-card
   layout with the masked card-number column, and other banks'
   single signed-amount exports. Upload both files on **Bank Import**.
2. **Review screen**: everything is auto-categorized (fuel cardlocks, parts,
   camp, WCB, meals…). Transfers to your personal account flag as
   *Owner Withdrawal*; your credit-card payments are auto-excluded so they
   never double count. Re-uploading skips duplicates.
3. **Bulk clean-up**: tick rows → set a category → Apply. Split mixed
   lines (part business / part personal) with the ✂ button — the original
   stays in the audit trail. Big purchases get the 🚚 button:
   one click creates a CCA asset (net of GST) on the depreciation schedule.
4. **Post the draws**: every flagged owner transfer gets ⇄'d onto the
   shareholder loan ledger in seconds.
5. **Tax Optimizer** page: see every exposure and missed claim — then
   **Reports → Year-end close** for the checklist and the accountant ZIP.

Historical data (pre-OilForge years) imports through
**Expenses → Import historical CSV** (template provided).

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
| **Tax Optimizer** | Deduction scanner (unposted draws, 15(2), capital-vs-expense, uncategorized lines, unbilled WIP, zero-activity reminders for PPE/training/camp/small tools), **T2 Schedule 1** working paper (50% meals add-back, recapture, terminal loss), **GRIP tracking** with Part III.1 warnings, **personal tax bridge** (dividends through federal + AB brackets with AMT/TOSI warnings) |
| **Year-end close** | 7-point checklist + one-click **accountant ZIP**: financials PDF, trial balance, categorized expenses, full bank audit trail, CCA Schedule 8 (with recapture/terminal loss), Schedule 1, GST34, journal entries, T5 figures, tax optimization memo |
| **Reports** | Income statement (tax estimate on the Schedule 1 base), **derived trial balance**, GST34 working copy, financial summary PDF, append-only audit trail, cash-flow forecast |
| **Backup** | Full JSON export/restore, optionally **encrypted** (PBKDF2-SHA256 600k iterations, per-file salt, AES/Fernet); conflict-safe restore; historical CSV import templates |

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

### CRA tips baked into the app

- **Meals are 50%**: full amount tracked, ITC at 50%, and the Schedule 1
  add-back computed automatically — never claim 100% by accident.
- **Capital vs expense**: purchases ≥ $2,500 sitting in repair/supply
  categories get flagged; tools under $500 are class 12 (100% write-off).
- **Own-account transfers** (credit-card payments) are excluded on import
  so expenses are never double-counted — a classic audit finding.
- **Recapture & terminal loss** are computed on disposals, not ignored.
- **GST on capital property**: full ITC in the purchase period when
  commercial use > 50% (note shown in the Tax Rules pack).
- **Receipt refs everywhere**: bank lines, expenses, fuel — CRA wants the
  paper; the app tracks where it is. (Receipt photo OCR is on the roadmap;
  today a receipt # or photo filename keeps you audit-ready.)

**Estimates are estimates** — T2 filing, GRIP/eligible-dividend
designations, AMT and passive-income grinds are your accountant's call. The
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
