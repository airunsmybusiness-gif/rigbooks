"""Shareholder loan & dividend module: transactions, declarations, running
ledger, ITA 15(2) assessment, T5 summaries, journal export, and one-click
posting of bank withdrawals to the ledger."""
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import shareholder as sh
from ..audit import log
from ..auth import current_user
from ..cra import engine as cra
from ..db import get_db
from ..helpers import fiscal_year_end, parse_period, rules_for_year
from ..models import (BankTransaction, DividendDeclaration, Shareholder,
                      ShareholderTxn, User)
from .crud_factory import make_crud_router, serialize

router = APIRouter(prefix="/api/shareholder", tags=["shareholder"])

txn_router = make_crud_router(ShareholderTxn, "shareholder-txns",
                              search_fields=("memo",))
dividend_router = make_crud_router(DividendDeclaration, "dividends",
                                   search_fields=("resolution_ref", "notes"))


@router.get("/{shareholder_id}/ledger")
def ledger(shareholder_id: int, as_of: str | None = None,
           db: Session = Depends(get_db), user: User = Depends(current_user)):
    holder = db.get(Shareholder, shareholder_id)
    if holder is None:
        raise HTTPException(404, "Shareholder not found")
    cutoff = date.fromisoformat(as_of) if as_of else None
    rows = sh.ledger(db, shareholder_id, cutoff)
    bal = rows[-1]["balance"] if rows else 0.0
    year = (cutoff or date.today()).year
    rules = rules_for_year(db, year)
    fye = fiscal_year_end(db, year)
    assessment = cra.shareholder_loan_assessment(bal, fye.isoformat(), rules)
    return {"shareholder": serialize(holder), "rows": rows,
            "balance": bal, "assessment": assessment}


@router.post("/post-from-bank", status_code=201)
def post_from_bank(payload: dict, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    """Turn a bank line (owner e-transfer / ATM draw / personal charge) into
    a shareholder-loan entry. Idempotent per bank transaction."""
    txn = db.get(BankTransaction, int(payload.get("bank_txn_id", 0)))
    holder = db.get(Shareholder, int(payload.get("shareholder_id", 0)))
    if txn is None or holder is None:
        raise HTTPException(404, "Bank transaction or shareholder not found")
    if txn.posted_shareholder_txn_id:
        raise HTTPException(409, "Already posted to the shareholder ledger")
    txn_type = payload.get("type") or ("withdrawal" if txn.debit > 0 else "contribution")
    if cra.loan_direction(txn_type) == 0:
        raise HTTPException(422, f"Unknown transaction type {txn_type!r}")
    entry = ShareholderTxn(shareholder_id=holder.id, date=txn.date,
                           type=txn_type, amount=txn.debit or txn.credit,
                           memo=txn.description[:120], bank_txn_id=txn.id)
    db.add(entry)
    db.flush()
    txn.posted_shareholder_txn_id = entry.id
    log(db, user.email, "create", "shareholder_txns", entry.id,
        {"from_bank_txn": txn.id, "type": txn_type})
    db.commit()
    return serialize(entry)


@router.get("/{shareholder_id}/t5")
def t5(shareholder_id: int, year: int, db: Session = Depends(get_db),
       user: User = Depends(current_user)):
    holder = db.get(Shareholder, shareholder_id)
    if holder is None:
        raise HTTPException(404, "Shareholder not found")
    rules = rules_for_year(db, year)
    actual = sh.dividends_by_kind(db, shareholder_id, year)
    result = cra.dividend_t5(actual, rules)
    result["shareholder"] = serialize(holder)
    result["year"] = year
    result["provisional"] = rules.get("provisional", False)
    return result


@router.get("/journal.csv")
def journal_csv(start: str | None = None, end: str | None = None,
                db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Double-entry journal for the accountant (all shareholder activity)."""
    s, e = parse_period(db, start, end)
    entries = sh.journal_entries(db, s, e)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["date", "memo", "debit_account",
                                        "credit_account", "amount"])
    w.writeheader()
    w.writerows(entries)
    log(db, user.email, "export", "shareholder_journal", "",
        {"period": [s.isoformat(), e.isoformat()], "entries": len(entries)})
    db.commit()
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition":
        f'attachment; filename="OilForge_Journal_{s.isoformat()}_{e.isoformat()}.csv"'})


@router.get("/overview")
def overview(year: int | None = None, db: Session = Depends(get_db),
             user: User = Depends(current_user)):
    """Per-shareholder dashboard block: balance, YTD dividends, 15(2) flag."""
    year = year or date.today().year
    rules = rules_for_year(db, year)
    fye = fiscal_year_end(db, year)
    out = []
    for holder in db.query(Shareholder).all():
        bal = sh.balance(db, holder.id)
        dividends = sh.dividends_by_kind(db, holder.id, year)
        out.append({
            "shareholder": serialize(holder),
            "loan_balance": bal,
            "dividends_ytd": round(sum(dividends.values()), 2),
            "dividends_by_kind": dividends,
            "assessment": cra.shareholder_loan_assessment(
                bal, fye.isoformat(), rules),
        })
    return {"year": year, "shareholders": out}


@router.get("/{shareholder_id}/yearly")
def yearly_balances(shareholder_id: int, db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
    """Multi-year view: balance at each fiscal year-end, the ITA 15(2)
    repayment deadline for that balance, and dividends paid that year."""
    holder = db.get(Shareholder, shareholder_id)
    if holder is None:
        raise HTTPException(404, "Shareholder not found")
    first = (db.query(ShareholderTxn)
             .filter_by(shareholder_id=shareholder_id)
             .order_by(ShareholderTxn.date).first())
    first_div = (db.query(DividendDeclaration)
                 .filter_by(shareholder_id=shareholder_id)
                 .order_by(DividendDeclaration.date).first())
    dates = [d.date for d in (first, first_div) if d is not None]
    if not dates:
        return {"years": []}
    start_year = min(dates).year
    out = []
    for year in range(start_year, date.today().year + 1):
        fye = fiscal_year_end(db, year)
        bal = sh.balance(db, shareholder_id, fye)
        rules = rules_for_year(db, year)
        months = rules["shareholder_loan"]["ita_15_2_repayment_months_after_year_end"]
        deadline = date(fye.year + (fye.month + months - 1) // 12,
                        (fye.month + months - 1) % 12 + 1,
                        min(fye.day, 28))
        divs = sh.dividends_by_kind(db, shareholder_id, year)
        # If the balance was cleared by the deadline, 15(2) is satisfied.
        bal_at_deadline = sh.balance(db, shareholder_id, min(deadline, date.today()))
        out.append({
            "year": year,
            "fye": fye.isoformat(),
            "balance_at_fye": bal,
            "repayment_deadline": deadline.isoformat(),
            "balance_at_deadline": bal_at_deadline,
            "ita_15_2_ok": bal <= 0.005 or bal_at_deadline <= 0.005
                           or date.today() < deadline,
            "dividends": {k: round(v, 2) for k, v in divs.items()},
        })
    return {"shareholder": serialize(holder), "years": out}


@router.get("/{shareholder_id}/repayment-plan")
def repayment_plan(shareholder_id: int, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    """What it takes to clear the loan before the ITA 15(2) deadline."""
    holder = db.get(Shareholder, shareholder_id)
    if holder is None:
        raise HTTPException(404, "Shareholder not found")
    today = date.today()
    bal = sh.balance(db, shareholder_id)
    fye = fiscal_year_end(db, today.year)
    if today > fye:
        fye = fiscal_year_end(db, today.year + 1)
    rules = rules_for_year(db, today.year)
    months = rules["shareholder_loan"]["ita_15_2_repayment_months_after_year_end"]
    deadline = date(fye.year + (fye.month + months - 1) // 12,
                    (fye.month + months - 1) % 12 + 1, min(fye.day, 28))
    months_left = max((deadline.year - today.year) * 12
                      + deadline.month - today.month, 1)
    prescribed = rules["shareholder_loan"]["prescribed_rate"]
    return {
        "balance": bal,
        "fiscal_year_end": fye.isoformat(),
        "repayment_deadline": deadline.isoformat(),
        "months_remaining": months_left,
        "monthly_repayment_to_clear": round(max(bal, 0) / months_left, 2),
        "dividend_to_clear_now": round(max(bal, 0), 2),
        "estimated_80_4_interest_if_held_to_deadline":
            round(max(bal, 0) * prescribed * months_left / 12, 2),
        "options": [
            "Repay in cash before the deadline",
            "Declare a dividend settled against the loan (creates T5 income)",
            "Combination: partial repayment + smaller dividend",
        ],
    }
