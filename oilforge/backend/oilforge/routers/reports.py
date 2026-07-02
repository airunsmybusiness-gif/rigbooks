"""Reports: dashboard, financial statements, trial balance, GST34, CCA
schedule, dividend register PDFs, audit trail, backup/restore (optionally
encrypted), and the data-migration placeholder."""
import base64
import hashlib
import io
import json
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import shareholder as sh
from ..audit import log
from ..auth import current_user
from ..cra import engine as cra
from ..db import get_db
from ..helpers import get_setting, parse_period, rules_for_year
from ..models import (AuditLog, BankTransaction, Client, DividendDeclaration,
                      Equipment, Expense, Invoice, InvoiceLine, Job, JobEntry,
                      MaintenanceLog, Shareholder, ShareholderTxn, User,
                      WellSite)
from ..reports import statements
from ..reports.pdf import dividend_register_pdf, financial_summary_pdf
from .crud_factory import serialize

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/dashboard")
def dashboard(start: str | None = None, end: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    s, e = parse_period(db, start, end)
    out = statements.collect(db, s, e)
    out["cash_flow"] = statements.monthly_cash_flow(db, e.year)
    out["job_margins"] = statements.job_margins(db)
    out["equipment_utilization"] = statements.equipment_utilization(db, e.year)
    return out


@router.get("/statements")
def financial_statements(start: str | None = None, end: str | None = None,
                         db: Session = Depends(get_db),
                         user: User = Depends(current_user)):
    s, e = parse_period(db, start, end)
    return {"summary": statements.collect(db, s, e),
            "trial_balance": statements.trial_balance(db, s, e)}


@router.get("/statements.pdf")
def statements_pdf(start: str | None = None, end: str | None = None,
                   db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    s, e = parse_period(db, start, end)
    pdf = financial_summary_pdf(statements.collect(db, s, e),
                                statements.trial_balance(db, s, e),
                                get_setting(db, "business"))
    log(db, user.email, "export", "reports", "statements.pdf",
        {"period": [s.isoformat(), e.isoformat()]})
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition":
        f'attachment; filename="OilForge_Financials_{e.year}.pdf"'})


@router.get("/cca")
def cca_schedule(year: int, db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    return statements.cca_for_year(db, year)


@router.get("/dividend-register/{shareholder_id}.pdf")
def dividend_register(shareholder_id: int, year: int,
                      db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    holder = db.get(Shareholder, shareholder_id)
    if holder is None:
        raise HTTPException(404, "Shareholder not found")
    rows = [serialize(d) for d in
            db.query(DividendDeclaration)
            .filter(DividendDeclaration.shareholder_id == shareholder_id,
                    DividendDeclaration.date >= date(year, 1, 1),
                    DividendDeclaration.date <= date(year, 12, 31))
            .order_by(DividendDeclaration.date)]
    rules = rules_for_year(db, year)
    t5 = cra.dividend_t5(sh.dividends_by_kind(db, shareholder_id, year), rules)
    pdf = dividend_register_pdf(serialize(holder), rows, t5,
                                get_setting(db, "business"), year)
    log(db, user.email, "export", "dividend_register", shareholder_id,
        {"year": year})
    db.commit()
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition":
        f'attachment; filename="Dividends_{holder.name.replace(" ", "_")}_{year}.pdf"'})


@router.get("/audit-log")
def audit_log(limit: int = Query(200, le=2000), offset: int = 0,
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = db.query(AuditLog).order_by(AuditLog.ts.desc(), AuditLog.id.desc())
    total = q.count()
    return {"total": total, "items": [
        {"id": a.id, "ts": a.ts.isoformat(), "user": a.user, "action": a.action,
         "entity": a.entity, "entity_id": a.entity_id, "details": a.details}
        for a in q.offset(offset).limit(limit)]}


# ----------------------------------------------------------- backup/restore

_BACKUP_MODELS = [BankTransaction, Client, WellSite, Job, JobEntry, Invoice,
                  InvoiceLine, Expense, Equipment, MaintenanceLog, Shareholder,
                  ShareholderTxn, DividendDeclaration]


def _fernet(password: str):
    from cryptography.fernet import Fernet
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), b"oilforge-backup",
                              200_000)
    return Fernet(base64.urlsafe_b64encode(key))


@router.get("/backup")
def export_backup(password: str | None = None, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    """Full JSON backup; pass ?password=… for an encrypted .ofb file."""
    data = {m.__tablename__: [serialize(r) for r in db.query(m).all()]
            for m in _BACKUP_MODELS}
    data["_meta"] = {"app": "OilForge", "version": 1,
                     "exported": date.today().isoformat(),
                     "encrypted": bool(password)}
    raw = json.dumps(data, indent=1).encode()
    log(db, user.email, "export", "backup", "", {"encrypted": bool(password)})
    db.commit()
    if password:
        blob = _fernet(password).encrypt(raw)
        return Response(blob, media_type="application/octet-stream", headers={
            "Content-Disposition":
            f'attachment; filename="oilforge_backup_{date.today()}.ofb"'})
    return Response(raw, media_type="application/json", headers={
        "Content-Disposition":
        f'attachment; filename="oilforge_backup_{date.today()}.json"'})


@router.post("/backup/restore")
async def restore_backup(file: UploadFile, password: str | None = None,
                         db: Session = Depends(get_db),
                         user: User = Depends(current_user)):
    raw = await file.read()
    if password:
        try:
            raw = _fernet(password).decrypt(raw)
        except Exception:
            raise HTTPException(422, "Wrong password or corrupted backup file")
    try:
        data = json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, "Not a valid backup (is it encrypted? "
                                 "supply the password)")
    counts = {}
    for m in _BACKUP_MODELS:
        n = 0
        for row in data.get(m.__tablename__, []):
            row = {k: v for k, v in row.items()
                   if k not in ("id", "created_at", "updated_at")}
            for col in m.__table__.columns:
                if col.type.__class__.__name__ == "Date" and isinstance(row.get(col.key), str):
                    row[col.key] = date.fromisoformat(row[col.key])
            # Foreign keys keep their original ids only on a fresh database;
            # restore is intended for empty/new installs.
            db.add(m(**row))
            n += 1
        counts[m.__tablename__] = n
    log(db, user.email, "import", "backup", "", counts)
    db.commit()
    return {"restored": counts}


# ------------------------------------------------------- migration (stub)

@router.post("/migration/import")
async def migration_import(file: UploadFile, source: str = "generic",
                           db: Session = Depends(get_db),
                           user: User = Depends(current_user)):
    """Placeholder for future imports (QuickBooks, Wave, spreadsheets).
    Currently accepts the file, records the request in the audit log, and
    returns the detected shape so a mapping can be built later."""
    content = (await file.read()).decode("utf-8", errors="replace")
    first_lines = content.splitlines()[:5]
    log(db, user.email, "import", "migration", "",
        {"source": source, "file": file.filename, "status": "received-not-processed"})
    db.commit()
    return {"status": "received", "source": source,
            "detected_header": first_lines[0] if first_lines else "",
            "preview": first_lines,
            "note": "Migration mapping not implemented yet - use Bank Import "
                    "for statements or the backup/restore JSON format."}
