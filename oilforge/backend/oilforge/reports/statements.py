"""Financial aggregation: dashboard KPIs, income statement, derived trial
balance and accountant summary. Everything tax-flavored goes through the
CRA engine with the fiscal year's rule pack.
"""
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session, joinedload

from .. import shareholder as sh
from ..cra import engine as cra
from ..helpers import get_province, rules_for_year
from ..models import (BankTransaction, DividendDeclaration, Equipment,
                      Expense, Invoice, Job, JobEntry, MaintenanceLog,
                      Shareholder)

REVENUE_CATEGORY = "Revenue - Contract Services"


def _assets_for_cca(db: Session) -> list[dict]:
    out = []
    for e in db.query(Equipment).filter(Equipment.acquired.isnot(None)):
        out.append({"cca_class": e.cca_class, "cost": e.cost,
                    "acquired_year": e.acquired.year,
                    "disposed_year": e.disposed.year if e.disposed else None,
                    "proceeds": e.disposal_proceeds})
    return out


def cca_for_year(db: Session, year: int) -> dict:
    return cra.cca_schedule(_assets_for_cca(db), year,
                            lambda y: rules_for_year(db, y))


def collect(db: Session, start: date, end: date) -> dict:
    year = end.year
    rules = rules_for_year(db, year)
    province = get_province(db)
    rate = cra.gst_rate(rules, province)

    # ---- Revenue: invoices (accrual) + uninvoiced bank revenue ----------
    invoices = (db.query(Invoice)
                .options(joinedload(Invoice.lines))
                .filter(Invoice.date >= start, Invoice.date <= end,
                        Invoice.status != "void").all())
    invoiced_revenue = sum(i.subtotal for i in invoices)
    gst_collected = sum(i.gst for i in invoices)
    ar_outstanding = sum(i.amount_due_now for i in invoices if i.status != "paid")
    holdbacks_receivable = sum(i.holdback for i in invoices
                               if not i.holdback_released)

    bank_rows = (db.query(BankTransaction)
                 .filter(BankTransaction.date >= start,
                         BankTransaction.date <= end).all())
    bank_revenue_gross = sum(t.credit for t in bank_rows
                             if t.category == REVENUE_CATEGORY)
    # Bank deposits are GST-included; keep as memo, not double-counted:
    # invoiced revenue is the book figure.

    # ---- Expenses --------------------------------------------------------
    expense_by_category: dict[str, float] = defaultdict(float)
    itcs = 0.0
    bank_expenses = 0.0
    for t in bank_rows:
        if t.status == "business" and t.debit > 0:
            expense_by_category[t.category] += t.debit
            bank_expenses += t.debit
            itcs += t.itc
    expenses = (db.query(Expense)
                .filter(Expense.date >= start, Expense.date <= end).all())
    direct_expenses = 0.0
    for x in expenses:
        expense_by_category[x.category] += x.amount
        direct_expenses += x.amount
        itcs += x.itc
    maint = (db.query(MaintenanceLog)
             .filter(MaintenanceLog.date >= start, MaintenanceLog.date <= end).all())
    maint_cost = sum(m.cost for m in maint)
    if maint_cost:
        expense_by_category["Equipment Repairs & Parts"] += maint_cost

    total_expenses = round(bank_expenses + direct_expenses + maint_cost, 2)

    # ---- CCA & income ----------------------------------------------------
    cca = cca_for_year(db, year)
    ebitda = round(invoiced_revenue - total_expenses, 2)
    income_before_tax = round(ebitda - cca["total_cca"], 2)
    tax_est = cra.corporate_tax_estimate(income_before_tax, rules, province)

    # ---- Shareholder & dividends ----------------------------------------
    loan_total = sum(sh.balance(db, s.id, end) for s in db.query(Shareholder))
    dividends = (db.query(DividendDeclaration)
                 .filter(DividendDeclaration.date >= start,
                         DividendDeclaration.date <= end).all())
    dividends_total = sum(d.amount for d in dividends)

    # ---- Cash & jobs -----------------------------------------------------
    all_bank = db.query(BankTransaction).filter(BankTransaction.date <= end).all()
    cash_position = round(sum(t.credit - t.debit for t in all_bank), 2)

    active_jobs = db.query(Job).filter(Job.status == "active").count()
    unbilled = sum(e.quantity * e.rate for e in
                   db.query(JobEntry).filter(JobEntry.invoice_id.is_(None)))

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "year": year},
        "rules_year": rules["year"],
        "rules_provisional": rules.get("provisional", False),
        "province": province,
        "gst_rate": rate,
        "revenue": {
            "invoiced": round(invoiced_revenue, 2),
            "bank_deposits_memo": round(bank_revenue_gross, 2),
            "gst_collected": round(gst_collected, 2),
            "ar_outstanding": round(ar_outstanding, 2),
            "holdbacks_receivable": round(holdbacks_receivable, 2),
            "unbilled_work": round(unbilled, 2),
        },
        "expenses": {
            "total": total_expenses,
            "by_category": {k: round(v, 2) for k, v in
                            sorted(expense_by_category.items(), key=lambda x: -x[1])},
        },
        "itcs": round(itcs, 2),
        "gst34": cra.gst_return(invoiced_revenue, gst_collected, itcs),
        "cca": {"total": cca["total_cca"], "ucc_closing": cca["total_ucc_closing"]},
        "income": {
            "ebitda": ebitda,
            "cca": cca["total_cca"],
            "before_tax": income_before_tax,
            "tax_estimate": tax_est["estimated_tax"],
            "after_tax_estimate": tax_est["after_tax"],
            "small_business_rate": tax_est["small_business_rate"],
        },
        "shareholder": {
            "loan_balance_total": round(loan_total, 2),
            "dividends_declared": round(dividends_total, 2),
        },
        "kpis": {
            "cash_position": cash_position,
            "active_jobs": active_jobs,
        },
    }


def monthly_cash_flow(db: Session, year: int) -> list[dict]:
    """Cash in/out by month from the bank feed (the honest cash view)."""
    months = [{"month": date(year, m, 1).strftime("%b"),
               "cash_in": 0.0, "cash_out": 0.0} for m in range(1, 13)]
    for t in db.query(BankTransaction).filter(
            BankTransaction.date >= date(year, 1, 1),
            BankTransaction.date <= date(year, 12, 31)):
        b = months[t.date.month - 1]
        b["cash_in"] += t.credit
        b["cash_out"] += t.debit
    running = 0.0
    for m in months:
        m["cash_in"] = round(m["cash_in"], 2)
        m["cash_out"] = round(m["cash_out"], 2)
        m["net"] = round(m["cash_in"] - m["cash_out"], 2)
        running = round(running + m["net"], 2)
        m["cumulative"] = running
    return months


def job_margins(db: Session, limit: int = 10) -> list[dict]:
    """Top jobs by earned value with margin — dashboard chart feed."""
    jobs = (db.query(Job).options(joinedload(Job.client))
            .filter(Job.status.in_(["active", "complete", "closed"])).all())
    out = []
    for job in jobs:
        earned = sum(e.quantity * e.rate for e in
                     db.query(JobEntry).filter_by(job_id=job.id))
        costs = sum(x.amount for x in db.query(Expense).filter_by(job_id=job.id))
        if earned == 0 and costs == 0:
            continue
        out.append({"job": f"{job.number} {job.title}".strip()[:32],
                    "earned": round(earned, 2), "costs": round(costs, 2),
                    "margin": round(earned - costs, 2),
                    "margin_pct": round((earned - costs) / earned * 100, 1)
                    if earned else 0.0})
    out.sort(key=lambda j: -j["earned"])
    return out[:limit]


def equipment_utilization(db: Session, year: int) -> list[dict]:
    """Hours billed per equipment unit (from job entries) + running costs."""
    hours: dict[int, float] = defaultdict(float)
    for e in (db.query(JobEntry)
              .filter(JobEntry.equipment_id.isnot(None),
                      JobEntry.date >= date(year, 1, 1),
                      JobEntry.date <= date(year, 12, 31))):
        qty = e.quantity * (10 if e.kind == "day" else 1)  # day ≈ 10 field hours
        hours[e.equipment_id] += qty
    costs: dict[int, float] = defaultdict(float)
    for m in (db.query(MaintenanceLog)
              .filter(MaintenanceLog.date >= date(year, 1, 1),
                      MaintenanceLog.date <= date(year, 12, 31))):
        costs[m.equipment_id] += m.cost
    for x in (db.query(Expense)
              .filter(Expense.equipment_id.isnot(None),
                      Expense.date >= date(year, 1, 1),
                      Expense.date <= date(year, 12, 31))):
        costs[x.equipment_id] += x.amount
    out = []
    for eq in db.query(Equipment).all():
        h, c = round(hours.get(eq.id, 0.0), 1), round(costs.get(eq.id, 0.0), 2)
        if h == 0 and c == 0 and eq.status != "active":
            continue
        out.append({"equipment": eq.name, "hours": h, "running_costs": c,
                    "status": eq.status})
    out.sort(key=lambda r: -r["hours"])
    return out


def trial_balance(db: Session, start: date, end: date) -> dict:
    """Derived trial balance for accountant review (single-entry source data,
    so equity is the balancing figure)."""
    s = collect(db, start, end)
    rows: list[dict] = []

    def add(account: str, debit: float = 0.0, credit: float = 0.0):
        if abs(debit) < 0.005 and abs(credit) < 0.005:
            return
        rows.append({"account": account, "debit": round(debit, 2),
                     "credit": round(credit, 2)})

    add("Cash - Operating", debit=max(s["kpis"]["cash_position"], 0),
        credit=max(-s["kpis"]["cash_position"], 0))
    add("Accounts Receivable", debit=s["revenue"]["ar_outstanding"])
    add("Holdbacks Receivable", debit=s["revenue"]["holdbacks_receivable"])
    ucc = s["cca"]["ucc_closing"]
    add("Equipment (UCC)", debit=ucc)
    loan = s["shareholder"]["loan_balance_total"]
    if loan >= 0:
        add("Due from Shareholder", debit=loan)
    else:
        add("Due to Shareholder", credit=-loan)
    gst_net = s["gst34"]["line_109_net_tax"]
    add("GST/HST Payable" if gst_net >= 0 else "GST/HST Receivable",
        credit=max(gst_net, 0), debit=max(-gst_net, 0))
    add("Revenue - Contract Services", credit=s["revenue"]["invoiced"])
    for cat, amt in s["expenses"]["by_category"].items():
        add(f"Expense - {cat}", debit=amt)
    add("CCA Expense", debit=s["cca"]["total"])
    add("Dividends Declared", debit=s["shareholder"]["dividends_declared"])

    total_dr = round(sum(r["debit"] for r in rows), 2)
    total_cr = round(sum(r["credit"] for r in rows), 2)
    plug = round(total_dr - total_cr, 2)
    add("Retained Earnings / Equity (balancing figure)",
        debit=max(-plug, 0), credit=max(plug, 0))
    return {"period": s["period"], "rows": rows,
            "total_debits": round(sum(r["debit"] for r in rows), 2),
            "total_credits": round(sum(r["credit"] for r in rows), 2),
            "note": ("Derived from single-entry records for accountant review - "
                     "equity is the balancing figure, not a posted balance.")}
