"""T2 preparation endpoints + the Personal Tax Bridge."""
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import shareholder as sh
from ..audit import log
from ..auth import current_user
from ..cra import personal as pt
from ..db import get_db
from ..helpers import fiscal_period, get_province, parse_period, rules_for_year
from ..models import PersonalTaxInput, Shareholder, User
from ..reports import statements, t2

router = APIRouter(prefix="/api/t2", tags=["t2"])
personal_router = APIRouter(prefix="/api/personal-tax", tags=["personal-tax"])


# ------------------------------------------------------------------- T2

@router.get("/package")
def package(year: int, db: Session = Depends(get_db),
            user: User = Depends(current_user)):
    start, end = fiscal_period(db, year)
    return t2.year_end_package(db, start, end)


@router.post("/close")
def close_year(payload: dict, db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    year = int(payload.get("year", date.today().year))
    start, end = fiscal_period(db, year)
    result = t2.close_year(db, start, end)
    log(db, user.email, "update", "year_end_close", year,
        {"closing_re": result["retained_earnings"]["closing_retained_earnings"]})
    db.commit()
    return result


@router.get("/schedule8.csv")
def schedule8_csv(year: int, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    sched = t2.schedule8(db, year)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["class", "description", "rate", "ucc_opening", "additions",
                "dispositions", "cca", "ucc_closing"])
    for r in sched["classes"]:
        w.writerow([r["class"], r["description"], r["rate"], r["ucc_opening"],
                    r["additions"], r["dispositions"], r["cca"], r["ucc_closing"]])
    w.writerow(["TOTAL", "", "", "", "", "", sched["total_cca"],
                sched["total_ucc_closing"]])
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="T2_S8_CCA_{year}.csv"'})


@router.get("/gifi.csv")
def gifi_csv(year: int, db: Session = Depends(get_db),
             user: User = Depends(current_user)):
    start, end = fiscal_period(db, year)
    gifi = t2.schedule125_gifi(db, start, end)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["gifi_code", "description", "amount"])
    for l in gifi["lines"]:
        w.writerow([l["gifi"], l["description"], f"{l['amount']:.2f}"])
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="T2_S125_GIFI_{year}.csv"'})


# ------------------------------------------------------- Personal Tax Bridge

DEFAULT_INPUTS = {"employment_income": 0, "other_income": 0,
                  "interest_income": 0, "rrsp_deduction": 0,
                  "other_deductions": 0}


def _get_inputs(db: Session, shareholder_id: int, year: int) -> dict:
    row = (db.query(PersonalTaxInput)
           .filter_by(shareholder_id=shareholder_id, year=year).first())
    return {**DEFAULT_INPUTS, **(row.data if row else {})}


@personal_router.get("/{shareholder_id}/{year}")
def preview(shareholder_id: int, year: int, db: Session = Depends(get_db),
            user: User = Depends(current_user)):
    holder = db.get(Shareholder, shareholder_id)
    if holder is None:
        raise HTTPException(404, "Shareholder not found")
    rules = rules_for_year(db, year)
    inputs = _get_inputs(db, shareholder_id, year)
    dividends = sh.dividends_by_kind(db, shareholder_id, year)
    loan_balance = sh.balance(db, shareholder_id, date(year, 12, 31))
    t1 = pt.t1_preview(rules, get_province(db), dividends, inputs, loan_balance)

    start, end = fiscal_period(db, year)
    corp = statements.collect(db, start, end)
    return {
        "shareholder": {"id": holder.id, "name": holder.name},
        "year": year,
        "inputs": inputs,
        "dividends": dividends,
        "loan_balance_dec31": loan_balance,
        "t1_preview": t1,
        "integrated": pt.integrated_summary(corp, t1),
        "provisional": rules.get("provisional", False),
    }


@personal_router.put("/{shareholder_id}/{year}")
def save_inputs(shareholder_id: int, year: int, payload: dict,
                db: Session = Depends(get_db), user: User = Depends(current_user)):
    if db.get(Shareholder, shareholder_id) is None:
        raise HTTPException(404, "Shareholder not found")
    row = (db.query(PersonalTaxInput)
           .filter_by(shareholder_id=shareholder_id, year=year).first())
    clean = {k: float(payload.get(k, 0) or 0) for k in DEFAULT_INPUTS}
    if row is None:
        row = PersonalTaxInput(shareholder_id=shareholder_id, year=year, data=clean)
        db.add(row)
    else:
        row.data = clean
    log(db, user.email, "update", "personal_tax_inputs",
        f"{shareholder_id}/{year}", {"data": clean})
    db.commit()
    return preview(shareholder_id, year, db, user)
