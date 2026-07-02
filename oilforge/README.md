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
cd backend && python -m pytest tests                           # 51 tests
cd frontend && npm run build                                   # ship UI
```

## Security

- Local auth (PBKDF2, 260k iterations) with **login rate limiting**
  (5 failures → 5-minute lockout).
- **Encrypted backups** (PBKDF2 + Fernet) via a password on export.
- Attachments are type- and size-restricted (photos/PDF, 15 MB).
- Append-only audit log with **CSV export** for the reviewer.
- Full-database encryption at rest: keep `~/.oilforge` on an encrypted
  volume (FileVault/BitLocker/LUKS) — SQLCipher can be swapped in via
  `DATABASE_URL` if needed.

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
