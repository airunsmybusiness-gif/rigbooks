"""CRA-ready reports: dashboard, GST34, T2125 CSV, IFTA, T4A, audit trail,
full data backup/restore."""
import csv
import io
import json
from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from ..audit import log
from ..auth import current_user
from ..cra import engine as cra
from ..db import get_db
from ..helpers import get_province, get_setting, parse_period, rules_for_year
from ..models import (AuditLog, BankTransaction, Customer, Expense,
                      FuelPurchase, HomeOffice, MealEntry, PhoneBill,
                      RevenueEntry, Trip, User, Vehicle)
from ..reports.pdf import summary_pdf
from ..reports.summary import collect, monthly_series
from .crud_factory import serialize

router = APIRouter(prefix="/api/reports", tags=["reports"])

QUARTERS = {1: ((1, 1), (3, 31)), 2: ((4, 1), (6, 30)),
            3: ((7, 1), (9, 30)), 4: ((10, 1), (12, 31))}

T4A_CATEGORIES = ("Professional Fees",)


@router.get("/dashboard")
def dashboard(start: str | None = None, end: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    s, e = parse_period(start, end)
    summary = collect(db, s, e)
    summary["monthly"] = monthly_series(db, s.year)
    return summary


@router.get("/summary")
def accountant_summary(start: str | None = None, end: str | None = None,
                       db: Session = Depends(get_db),
                       user: User = Depends(current_user)):
    s, e = parse_period(start, end)
    return collect(db, s, e)


@router.get("/summary.pdf")
def summary_as_pdf(start: str | None = None, end: str | None = None,
                   db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    s, e = parse_period(start, end)
    pdf = summary_pdf(collect(db, s, e), get_setting(db, "business"))
    log(db, user.email, "export", "reports", "summary.pdf",
        {"period": [s.isoformat(), e.isoformat()]})
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="RigBooks_Summary_{s.year}.pdf"'})


@router.get("/gst34")
def gst34(start: str | None = None, end: str | None = None,
          db: Session = Depends(get_db), user: User = Depends(current_user)):
    s, e = parse_period(start, end)
    summary = collect(db, s, e)
    return {"period": summary["period"], "gst34": summary["gst34"],
            "itcs_by_source": summary["itcs"]["by_source"],
            "revenue": summary["revenue"],
            "rules_provisional": summary["rules_provisional"]}


@router.get("/t2125.csv")
def t2125_csv(start: str | None = None, end: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Line-level export mapped for the accountant preparing T2125/T2."""
    s, e = parse_period(start, end)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Date", "Type", "Category", "Client_Vendor", "Amount",
                "Business_Pct", "GST_ITC", "Receipt_Ref", "Notes"])

    for r in db.query(RevenueEntry).filter(RevenueEntry.date >= s, RevenueEntry.date <= e):
        w.writerow([r.date, "Revenue", "Sales", r.client, f"{r.amount:.2f}",
                    100, f"{r.gst_amount:.2f}", "", r.job])
    for t in db.query(BankTransaction).filter(
            BankTransaction.date >= s, BankTransaction.date <= e,
            BankTransaction.status == "business"):
        w.writerow([t.date, "Expense", t.category, t.description[:60],
                    f"{t.debit:.2f}", 100, f"{t.itc:.2f}", "", "Bank statement"])
    for x in db.query(Expense).filter(Expense.date >= s, Expense.date <= e):
        w.writerow([x.date, "Expense", x.category, x.vendor or x.description,
                    f"{x.amount:.2f}", x.business_pct, f"{x.itc:.2f}",
                    x.receipt_ref, f"{x.source} - {x.paid_by}".strip(" -")])
    for f in db.query(FuelPurchase).filter(FuelPurchase.date >= s, FuelPurchase.date <= e):
        w.writerow([f.date, "Expense", "Fuel & Petroleum", f.vendor,
                    f"{f.amount:.2f}", 100, f"{f.itc:.2f}", f.receipt_ref,
                    f"{f.litres}L {f.fuel_type} in {f.jurisdiction}"])
    for p in db.query(PhoneBill).filter(PhoneBill.period_start >= s,
                                        PhoneBill.period_start <= e):
        w.writerow([p.period_start, "Expense", "Phone & Communications", p.owner,
                    f"{p.amount:.2f}", p.business_pct, "", "", p.notes])
    for m in db.query(MealEntry).filter(MealEntry.date >= s, MealEntry.date <= e):
        rules = rules_for_year(db, m.date.year)
        d = cra.meal_deduction(rules, meals_count=m.meals_count,
                               actual_amount=m.amount, method=m.method,
                               long_haul=m.long_haul)
        w.writerow([m.date, "Expense",
                    "Meals - Long Haul (80%)" if m.long_haul else "Meals (50%)",
                    m.location, f"{d['gross']:.2f}",
                    round(d["deductible_pct"] * 100), "", m.receipt_ref,
                    f"{m.method}; deductible {d['deductible']:.2f}"])
    ho = db.query(HomeOffice).filter_by(year=s.year).first()
    if ho:
        gross = (ho.rent + ho.property_tax + ho.insurance + ho.electricity +
                 ho.gas + ho.water + ho.internet)
        w.writerow([f"{s.year}-12-31", "Expense", "Home Office", "Workspace in home",
                    f"{gross:.2f}", ho.pct, "", "",
                    f"rent {ho.rent}, utils {ho.electricity + ho.gas + ho.water}, net {ho.internet}"])
    trips = db.query(Trip).filter(Trip.date >= s, Trip.date <= e).all()
    if trips:
        bkm = sum(t.business_km for t in trips)
        tkm = sum(t.total_km for t in trips)
        w.writerow([f"{s.year}-12-31", "Mileage", "Vehicle log",
                    f"Business {bkm:.0f} km / Total {tkm:.0f} km", 0,
                    cra.business_use_pct(bkm, tkm), "", "",
                    "Detailed daily log available in RigBooks"])

    log(db, user.email, "export", "reports", "t2125.csv",
        {"period": [s.isoformat(), e.isoformat()]})
    db.commit()
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": f'attachment; filename="T2125_RigBooks_{s.year}.csv"'})


@router.get("/ifta")
def ifta(year: int, quarter: int = Query(ge=1, le=4),
         db: Session = Depends(get_db), user: User = Depends(current_user)):
    (sm, sd), (em, ed) = QUARTERS[quarter]
    s, e = date(year, sm, sd), date(year, em, ed)
    rules = rules_for_year(db, year)

    km_by_juris: dict[str, float] = defaultdict(float)
    for t in db.query(Trip).filter(Trip.date >= s, Trip.date <= e):
        jk = t.jurisdiction_km or {}
        if jk:
            for j, km in jk.items():
                km_by_juris[j.upper()] += float(km or 0)
        else:
            km_by_juris[get_province(db)] += t.total_km

    fuel_by_juris: dict[str, float] = defaultdict(float)
    for f in db.query(FuelPurchase).filter(FuelPurchase.date >= s, FuelPurchase.date <= e):
        fuel_by_juris[f.jurisdiction.upper()] += f.litres

    report = cra.ifta_quarter_report(dict(km_by_juris), dict(fuel_by_juris), rules)
    report["year"] = year
    report["quarter"] = quarter
    report["period"] = {"start": s.isoformat(), "end": e.isoformat()}
    report["rates_note"] = rules.get("ifta", {}).get("notes", "")
    return report


@router.get("/t4a")
def t4a(year: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Vendors paid > $500 in fees for services (T4A box 048 candidates)."""
    s, e = date(year, 1, 1), date(year, 12, 31)
    rules = rules_for_year(db, year)
    payments: dict[str, float] = defaultdict(float)
    for x in db.query(Expense).filter(Expense.date >= s, Expense.date <= e,
                                      Expense.category.in_(T4A_CATEGORIES)):
        payments[x.vendor or x.description] += x.amount
    candidates = cra.t4a_candidates(dict(payments), rules)
    return {"year": year, "threshold": rules["t4a"]["fee_reporting_threshold"],
            "box": rules["t4a"]["box"], "candidates": candidates,
            "notes": rules["t4a"]["notes"]}


@router.get("/audit-log")
def audit_log(limit: int = Query(200, le=2000), offset: int = 0,
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = db.query(AuditLog).order_by(AuditLog.ts.desc(), AuditLog.id.desc())
    total = q.count()
    items = q.offset(offset).limit(limit).all()
    return {"total": total, "items": [
        {"id": a.id, "ts": a.ts.isoformat(), "user": a.user, "action": a.action,
         "entity": a.entity, "entity_id": a.entity_id, "details": a.details}
        for a in items]}


# ------------------------------------------------------------- backup

_BACKUP_MODELS = [BankTransaction, RevenueEntry, Expense, FuelPurchase, Trip,
                  MealEntry, PhoneBill, HomeOffice, Customer, Vehicle]


@router.get("/backup")
def export_backup(db: Session = Depends(get_db), user: User = Depends(current_user)):
    data = {m.__tablename__: [serialize(row) for row in db.query(m).all()]
            for m in _BACKUP_MODELS}
    data["_meta"] = {"app": "RigBooks", "version": 5,
                     "exported": date.today().isoformat()}
    log(db, user.email, "export", "backup", "", {})
    db.commit()
    return StreamingResponse(
        io.BytesIO(json.dumps(data, indent=1).encode()),
        media_type="application/json",
        headers={"Content-Disposition":
                 f'attachment; filename="rigbooks_backup_{date.today()}.json"'})


@router.post("/backup/restore")
async def restore_backup(file: UploadFile, db: Session = Depends(get_db),
                         user: User = Depends(current_user)):
    data = json.loads((await file.read()).decode())
    counts = {}
    for m in _BACKUP_MODELS:
        rows = data.get(m.__tablename__, [])
        n = 0
        for row in rows:
            row = {k: v for k, v in row.items()
                   if k not in ("id", "created_at", "updated_at")}
            for col in m.__table__.columns:
                if col.type.__class__.__name__ == "Date" and isinstance(row.get(col.key), str):
                    row[col.key] = date.fromisoformat(row[col.key])
            db.add(m(**row))
            n += 1
        counts[m.__tablename__] = n
    log(db, user.email, "import", "backup", "", counts)
    db.commit()
    return {"restored": counts}
