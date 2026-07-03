"""Tax maximization endpoints: deduction scanner, Schedule 1 working paper,
personal tax bridge, GRIP tracking."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import shareholder as sh
from .. import tax_optimizer
from ..audit import log
from ..auth import current_user
from ..cra import engine as cra
from ..db import get_db
from ..helpers import (get_province, get_setting, parse_period, put_setting,
                       rules_for_year)
from ..models import User
from ..reports import statements
from .crud_factory import serialize

router = APIRouter(prefix="/api/tax", tags=["tax"])


@router.get("/optimizer")
def optimizer(start: str | None = None, end: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    s, e = parse_period(db, start, end)
    summary = statements.collect(db, s, e)
    cca = statements.cca_for_year(db, e.year)
    findings = tax_optimizer.scan(db, s, e, summary, cca)
    return {
        "period": summary["period"],
        "findings": findings,
        "counts": {sev: sum(1 for f in findings if f["severity"] == sev)
                   for sev in ("action", "review", "info")},
        "flagged_total": round(sum(f.get("amount", 0) for f in findings), 2),
    }


@router.get("/schedule1")
def schedule1(start: str | None = None, end: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    s, e = parse_period(db, start, end)
    summary = statements.collect(db, s, e)
    return {"period": summary["period"], **summary["schedule1"],
            "corporate_tax_estimate": summary["income"]["tax_estimate"]}


@router.get("/grip")
def get_grip(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return get_setting(db, "grip", {}) or {}


@router.put("/grip")
def put_grip(payload: dict, db: Session = Depends(get_db),
             user: User = Depends(current_user)):
    """{ "2026": 15000, ... } — year-end GRIP balances from the accountant's
    T2 Schedule 53; drives eligible-dividend warnings."""
    current = get_setting(db, "grip", {}) or {}
    current.update({str(k): float(v or 0) for k, v in payload.items()})
    put_setting(db, "grip", current)
    log(db, user.email, "update", "grip", "", payload)
    db.commit()
    return current
