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

## Getting started (first 30 minutes)

1. **Install & run**: `pip install -r backend/requirements.txt` then
   `python run.py` → create your local account.
2. **Settings**: corporation name, province, fiscal year-end, GST number.
3. **Migrate history** (Settings → *Migration wizard*): work the seven
   steps top-to-bottom — clients, equipment, jobs, prior-year bank
   statements, expenses, shareholder loan history (opening balance =
   your first rows), past dividends. Each step has a downloadable CSV
   template with an example row; imports are additive and duplicate-safe.
4. **Upload this year's CIBC files** (Bank Import) — see the workflow below.
5. **Month to month**: field tickets on the Field Entry page (photos
   attach from the truck), invoices from jobs, ⇄ draws to the ledger.
6. **Year-end**: Tax Optimizer → clear the findings → Reports →
   *Year-end close* → download the accountant ZIP.

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

## T2 preparation & year-end close

The **Reports → T2 year-end** tab builds the working papers:

- **Schedule 1** book-to-tax reconciliation (automatic add-back of the
  non-deductible 50% of meals, CCA deduction)
- **Schedule 8** CCA in T2 layout (CSV export)
- **Schedule 50** shareholder information (holdings, dividends, loans)
- **Schedule 125** GIFI-coded income statement (CSV export)
- **Retained-earnings reconciliation** and a suggested **tax provision
  journal entry** (DR Income Tax Expense / CR Income Taxes Payable)
- **Close fiscal year** snapshots the figures (audit-logged) and rolls
  closing RE into next year's opening RE

## Personal Tax Bridge

The corporate numbers flow into a **T1 preview** for the owner: dividends
(grossed up, with federal + Alberta dividend tax credits), the ITA 80.4
imputed-interest benefit on any outstanding loan, plus manually entered
employment/other income and RRSP/other deductions. Shows federal and
provincial tax, marginal/average rates, a simplified **2024+ AMT check**,
and the **combined corporate + personal** effective rate on each dollar of
corporate income. Preview only — brackets are simplified (no CPP/EI or
clawbacks); the accountant files the real T1.

## GST/HST filing detail

**Reports → GST/HST filing**: ITCs split **operating vs capital property**
(equipment acquisitions listed individually), per-category and quarterly
breakdowns, a memo of GST embedded in unreleased holdbacks, RC4616
closely-related-election recording, and a filing-ready CSV export.

## Field operations

- **Field Entry page** — mobile-first ticket entry with big touch targets,
  **camera photo attachments** on tickets, and an **offline queue**:
  entries made without signal are stored locally and auto-sync when the
  network returns.
- **Parts inventory** (Equipment → Parts): stock levels, unit costs,
  low-stock flags, one-tap receive/use.
- **Safety & compliance registry** (Equipment → Safety): certificates,
  inspections, permits with expiry countdown badges.

## Accountant handoff

One click (**Reports → Accountant package**) downloads a ZIP containing the
financial summary PDF, complete T2 working papers, GST filing summary,
double-entry shareholder journal, T5 figures per shareholder, and the full
audit log. CSV **import tools** (with downloadable templates) cover
expenses, clients and equipment for migrating old records.

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
cd backend && python -m pytest tests                           # 51 tests
cd frontend && npm run build                                   # ship UI
```

## Security

- Local auth (PBKDF2, 260k iterations) with **login rate limiting**
  (5 failures → 5-minute lockout).
- **Encrypted backups** (PBKDF2 + Fernet) via a password on export.
- Attachments are type- and size-restricted (photos/PDF, 15 MB).
- Append-only audit log with **CSV export** for the reviewer.
- Encrypted backups use a **per-file random salt** (600k PBKDF2
  iterations); older fixed-salt backups still restore.
- Full-database encryption at rest, pick one:
  1. *Simplest*: keep `~/.oilforge` on an encrypted volume
     (FileVault / BitLocker / LUKS). Zero code changes.
  2. *SQLCipher*: `pip install sqlcipher3-binary sqlalchemy-sqlcipher`,
     then `DATABASE_URL="sqlite+pysqlcipher://:YOURKEY@/$HOME/.oilforge/oilforge.db"` —
     the app is dialect-agnostic, everything goes through SQLAlchemy.
  3. *PostgreSQL* with server-side disk encryption via `DATABASE_URL`.

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
