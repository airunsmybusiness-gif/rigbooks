"""Workspace-in-home costs, one record per tax year."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..audit import log
from ..auth import current_user
from ..cra import engine as cra
from ..db import get_db
from ..helpers import get_province, rules_for_year
from ..models import HomeOffice, User
from .crud_factory import serialize

router = APIRouter(prefix="/api/home-office", tags=["home-office"])

COST_FIELDS = ("rent", "property_tax", "insurance", "electricity", "gas",
               "water", "internet")
# Insurance and property tax carry no GST, so no ITC on those portions.
GST_BEARING = ("rent", "electricity", "gas", "water", "internet")


def _summary(db: Session, ho: HomeOffice) -> dict:
    rules = rules_for_year(db, ho.year)
    rate = cra.gst_rate(rules, get_province(db))
    total = sum(getattr(ho, f) for f in COST_FIELDS)
    deductible = round(total * ho.pct / 100, 2)
    gst_bearing_ded = sum(getattr(ho, f) for f in GST_BEARING) * ho.pct / 100
    itc = cra.extract_gst(gst_bearing_ded, rate)
    return {**serialize(ho), "total": round(total, 2),
            "deductible": deductible, "itc": itc}


@router.get("/{year}")
def get_year(year: int, db: Session = Depends(get_db),
             user: User = Depends(current_user)):
    ho = db.query(HomeOffice).filter_by(year=year).first()
    if ho is None:
        ho = HomeOffice(year=year)
    return _summary(db, ho)


@router.put("/{year}")
def put_year(year: int, payload: dict, db: Session = Depends(get_db),
             user: User = Depends(current_user)):
    ho = db.query(HomeOffice).filter_by(year=year).first()
    if ho is None:
        ho = HomeOffice(year=year)
        db.add(ho)
    for f in COST_FIELDS + ("pct",):
        if f in payload:
            setattr(ho, f, float(payload[f] or 0))
    log(db, user.email, "update", "home_office", year, {"changes": payload})
    db.commit()
    return _summary(db, ho)
