"""Shareholder ledger service — the heart of dividend-based compensation.

Builds the running shareholder-loan ledger (explicit transactions + dividends
settled against the loan), T5 summaries, and accountant journal entries.
"""
from datetime import date

from sqlalchemy.orm import Session

from .cra import engine as cra
from .models import DividendDeclaration, Shareholder, ShareholderTxn

TXN_LABELS = {
    "withdrawal": "Owner withdrawal",
    "personal_expense": "Personal expense paid by corp",
    "contribution": "Shareholder contribution",
    "corp_expense_paid_personally": "Corp expense paid personally",
    "loan_repayment": "Loan repayment",
    "dividend_applied": "Dividend applied to loan",
}


def ledger(db: Session, shareholder_id: int,
           as_of: date | None = None) -> list[dict]:
    """Chronological ledger with running balance.
    Positive balance = shareholder owes the corporation (ITA 15(2) risk)."""
    rows: list[dict] = []
    q = db.query(ShareholderTxn).filter(ShareholderTxn.shareholder_id == shareholder_id)
    if as_of:
        q = q.filter(ShareholderTxn.date <= as_of)
    for t in q:
        rows.append({"date": t.date, "type": t.type,
                     "label": TXN_LABELS.get(t.type, t.type),
                     "memo": t.memo, "amount": t.amount,
                     "signed": cra.loan_direction(t.type) * t.amount,
                     "source": "txn", "id": t.id})
    dq = (db.query(DividendDeclaration)
          .filter(DividendDeclaration.shareholder_id == shareholder_id,
                  DividendDeclaration.settlement == "loan"))
    if as_of:
        dq = dq.filter(DividendDeclaration.date <= as_of)
    for d in dq:
        rows.append({"date": d.date, "type": "dividend_applied",
                     "label": f"Dividend declared ({d.kind.replace('_', '-')}) "
                              "applied to loan",
                     "memo": d.resolution_ref or d.notes, "amount": d.amount,
                     "signed": -d.amount, "source": "dividend", "id": d.id})
    rows.sort(key=lambda r: (r["date"], r["source"], r["id"]))
    balance = 0.0
    for r in rows:
        balance = round(balance + r["signed"], 2)
        r["balance"] = balance
        r["date"] = r["date"].isoformat()
    return rows


def balance(db: Session, shareholder_id: int, as_of: date | None = None) -> float:
    rows = ledger(db, shareholder_id, as_of)
    return rows[-1]["balance"] if rows else 0.0


def dividends_by_kind(db: Session, shareholder_id: int, year: int) -> dict[str, float]:
    """Actual dividends for a calendar year (T5 is calendar-year based)."""
    out = {"eligible": 0.0, "non_eligible": 0.0}
    q = (db.query(DividendDeclaration)
         .filter(DividendDeclaration.shareholder_id == shareholder_id,
                 DividendDeclaration.date >= date(year, 1, 1),
                 DividendDeclaration.date <= date(year, 12, 31)))
    for d in q:
        out[d.kind] = out.get(d.kind, 0.0) + d.amount
    return out


def journal_entries(db: Session, start: date, end: date) -> list[dict]:
    """Double-entry journal for the accountant (CSV-ready).

    Withdrawal:            DR Shareholder Loan   / CR Cash
    Personal expense:      DR Shareholder Loan   / CR Cash
    Contribution:          DR Cash               / CR Shareholder Loan
    Corp exp. paid pers.:  DR <Expense>          / CR Shareholder Loan
    Loan repayment:        DR Cash               / CR Shareholder Loan
    Dividend (loan):       DR Retained Earnings  / CR Shareholder Loan
    Dividend (cash):       DR Retained Earnings  / CR Cash
    """
    names = {s.id: s.name for s in db.query(Shareholder).all()}
    entries: list[dict] = []

    def add(d: date, memo: str, debit_acct: str, credit_acct: str, amount: float):
        entries.append({"date": d.isoformat(), "memo": memo,
                        "debit_account": debit_acct, "credit_account": credit_acct,
                        "amount": round(amount, 2)})

    for t in (db.query(ShareholderTxn)
              .filter(ShareholderTxn.date >= start, ShareholderTxn.date <= end)):
        who = names.get(t.shareholder_id, f"Shareholder {t.shareholder_id}")
        loan = f"Due from Shareholder - {who}"
        memo = f"{TXN_LABELS.get(t.type, t.type)} - {who}" + (f" ({t.memo})" if t.memo else "")
        if t.type in ("withdrawal", "personal_expense"):
            add(t.date, memo, loan, "Cash - Operating", t.amount)
        elif t.type in ("contribution", "loan_repayment"):
            add(t.date, memo, "Cash - Operating", loan, t.amount)
        elif t.type == "corp_expense_paid_personally":
            add(t.date, memo, "Operating Expenses", loan, t.amount)

    for d in (db.query(DividendDeclaration)
              .filter(DividendDeclaration.date >= start,
                      DividendDeclaration.date <= end)):
        who = names.get(d.shareholder_id, f"Shareholder {d.shareholder_id}")
        loan = f"Due from Shareholder - {who}"
        memo = (f"Dividend declared ({d.kind.replace('_', '-')}) - {who}"
                + (f" [{d.resolution_ref}]" if d.resolution_ref else ""))
        credit = loan if d.settlement == "loan" else "Cash - Operating"
        add(d.date, memo, "Retained Earnings - Dividends Declared", credit, d.amount)

    entries.sort(key=lambda e: e["date"])
    return entries
