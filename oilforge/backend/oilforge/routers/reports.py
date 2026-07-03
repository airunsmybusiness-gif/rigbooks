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
    # Simple forward look: average net of the last 3 active months.
    active = [m for m in out["cash_flow"] if m["cash_in"] or m["cash_out"]]
    if active:
        recent = active[-3:]
        avg_net = round(sum(m["net"] for m in recent) / len(recent), 2)
        out["forecast"] = {
            "avg_monthly_net": avg_net,
            "next_quarter_net": round(avg_net * 3, 2),
            "projected_cash_in_3mo": round(out["kpis"]["cash_position"] + avg_net * 3, 2),
            "basis": f"average of last {len(recent)} active months",
        }
    else:
        out["forecast"] = None
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


def _fernet(password: str, salt: bytes):
    from cryptography.fernet import Fernet
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return Fernet(base64.urlsafe_b64encode(key))


_OFB_MAGIC = b"OFB2"  # magic + 16-byte random salt + Fernet token


def encrypt_backup(raw: bytes, password: str) -> bytes:
    import os as _os
    salt = _os.urandom(16)
    return _OFB_MAGIC + salt + _fernet(password, salt).encrypt(raw)


def decrypt_backup(blob: bytes, password: str) -> bytes:
    if blob.startswith(_OFB_MAGIC):
        salt, token = blob[4:20], blob[20:]
        return _fernet(password, salt).decrypt(token)
    # Legacy format (fixed salt, 200k iterations).
    from cryptography.fernet import Fernet
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), b"oilforge-backup",
                              200_000)
    return Fernet(base64.urlsafe_b64encode(key)).decrypt(blob)


@router.get("/backup")
def export_backup(password: str | None = None, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    """Full JSON backup; pass ?password=… for an encrypted .ofb file
    (PBKDF2-SHA256 600k iterations, per-file random salt, Fernet/AES)."""
    data = {m.__tablename__: [serialize(r) for r in db.query(m).all()]
            for m in _BACKUP_MODELS}
    data["_meta"] = {"app": "OilForge", "version": 2,
                     "exported": date.today().isoformat(),
                     "encrypted": bool(password)}
    raw = json.dumps(data, indent=1).encode()
    log(db, user.email, "export", "backup", "", {"encrypted": bool(password)})
    db.commit()
    if password:
        return Response(encrypt_backup(raw, password),
                        media_type="application/octet-stream", headers={
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
            raw = decrypt_backup(raw, password)
        except Exception:
            raise HTTPException(422, "Wrong password or corrupted backup file")
    try:
        data = json.loads(raw.decode())
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(422, "Not a valid backup (is it encrypted? "
                                 "supply the password)")
    from sqlalchemy.exc import IntegrityError

    counts: dict[str, int] = {}
    skipped = 0
    for m in _BACKUP_MODELS:
        n = 0
        for row in data.get(m.__tablename__, []):
            row = {k: v for k, v in row.items()
                   if k not in ("id", "created_at", "updated_at")
                   and k in m.__table__.columns}
            for col in m.__table__.columns:
                if col.type.__class__.__name__ == "Date" and isinstance(row.get(col.key), str):
                    row[col.key] = date.fromisoformat(row[col.key])
            # Foreign keys keep their original ids only on a fresh database;
            # rows that collide with existing unique keys are skipped so a
            # restore-on-top never blows up mid-way.
            try:
                with db.begin_nested():
                    db.add(m(**row))
                    db.flush()
                n += 1
            except IntegrityError:
                skipped += 1
        counts[m.__tablename__] = n
    log(db, user.email, "import", "backup", "",
        {**counts, "skipped_conflicts": skipped})
    db.commit()
    return {"restored": counts, "skipped_conflicts": skipped}


# ------------------------------------------------------------- year-end

def _yearend_checklist(db: Session, start: date, end: date) -> list[dict]:
    from .. import tax_optimizer
    from ..reports import statements as st
    summary = st.collect(db, start, end)
    cca = st.cca_for_year(db, end.year)
    findings = tax_optimizer.scan(db, start, end, summary, cca)
    checklist = [
        {"item": "Bank transactions categorized",
         "ok": not any("uncategorized" in f["title"] for f in findings)},
        {"item": "Owner draws posted to shareholder ledger",
         "ok": not any("not on the loan ledger" in f["title"] for f in findings)},
        {"item": "Shareholder loan cleared / ITA 15(2) safe",
         "ok": not any(f["title"].startswith("ITA 15(2)") for f in findings)},
        {"item": "Eligible dividends within GRIP",
         "ok": not any("GRIP" in f["title"] for f in findings)},
        {"item": "Capital purchases on the CCA schedule",
         "ok": not any("not on the CCA schedule" in f["title"] for f in findings)},
        {"item": "All field work billed",
         "ok": not any("Unbilled" in f["title"] for f in findings)},
        {"item": "Tax rates confirmed (not provisional)",
         "ok": not summary.get("rules_provisional", False)},
    ]
    return checklist


@router.get("/yearend/checklist")
def yearend_checklist(start: str | None = None, end: str | None = None,
                      db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    s, e = parse_period(db, start, end)
    items = _yearend_checklist(db, s, e)
    return {"period": {"start": s.isoformat(), "end": e.isoformat()},
            "items": items, "ready": all(i["ok"] for i in items)}


@router.get("/yearend.zip")
def yearend_zip(start: str | None = None, end: str | None = None,
                db: Session = Depends(get_db), user: User = Depends(current_user)):
    """One-click accountant handoff: everything needed for the T2 + T1 in
    a single ZIP."""
    import csv as csvmod
    import zipfile

    from .. import tax_optimizer
    from ..reports import statements as st

    s, e = parse_period(db, start, end)
    year = e.year
    summary = st.collect(db, s, e)
    tb = st.trial_balance(db, s, e)
    cca = st.cca_for_year(db, year)
    findings = tax_optimizer.scan(db, s, e, summary, cca)
    business = get_setting(db, "business")

    def csv_bytes(header: list[str], rows: list[list]) -> str:
        buf = io.StringIO()
        w = csvmod.writer(buf)
        w.writerow(header)
        w.writerows(rows)
        return buf.getvalue()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("01_financial_summary.pdf",
                   financial_summary_pdf(summary, tb, business))
        z.writestr("02_trial_balance.csv", csv_bytes(
            ["Account", "Debit", "Credit"],
            [[r["account"], r["debit"], r["credit"]] for r in tb["rows"]]))
        z.writestr("03_expenses_by_category.csv", csv_bytes(
            ["Category", "Amount"],
            list(summary["expenses"]["by_category"].items())))
        z.writestr("04_bank_transactions.csv", csv_bytes(
            ["Date", "Description", "Debit", "Credit", "Category", "Status",
             "ITC", "Receipt", "Notes"],
            [[t.date, t.description, t.debit, t.credit, t.category, t.status,
              t.itc, t.receipt_ref, t.notes]
             for t in db.query(BankTransaction)
             .filter(BankTransaction.date >= s, BankTransaction.date <= e)
             .order_by(BankTransaction.date)]))
        z.writestr("05_cca_schedule8.csv", csv_bytes(
            ["Class", "Rate", "UCC Opening", "Additions", "Dispositions",
             "CCA", "Recapture", "Terminal Loss", "UCC Closing"],
            [[r["class"], r["rate"], r["ucc_opening"], r["additions"],
              r["dispositions"], r["cca"], r["recapture"], r["terminal_loss"],
              r["ucc_closing"]] for r in cca["classes"]]))
        z.writestr("06_schedule1_working_paper.csv", csv_bytes(
            ["Line", "Amount"],
            [[l["line"], l["amount"]] for l in summary["schedule1"]["lines"]]))
        z.writestr("07_gst34.csv", csv_bytes(
            ["Line", "Amount"],
            [[k, v] for k, v in summary["gst34"].items()]))
        z.writestr("08_journal_entries.csv", csv_bytes(
            ["Date", "Memo", "Debit Account", "Credit Account", "Amount"],
            [[j["date"], j["memo"], j["debit_account"], j["credit_account"],
              j["amount"]] for j in sh.journal_entries(db, s, e)]))
        for holder in db.query(Shareholder).all():
            rules = rules_for_year(db, year)
            t5 = cra.dividend_t5(sh.dividends_by_kind(db, holder.id, year), rules)
            z.writestr(f"09_t5_{holder.name.replace(' ', '_')}.csv", csv_bytes(
                ["Box", "Amount"], list(t5["boxes"].items())))
        # Tax optimization summary — the "did we miss anything" memo.
        lines = [f"# Tax Optimization Summary — {business.get('name')} {year}",
                 f"Period {s} to {e}. Generated by OilForge.", ""]
        for f in findings:
            amt = f" — ${f['amount']:,.2f}" if f.get("amount") else ""
            lines.append(f"[{f['severity'].upper()}] {f['title']}{amt}")
            lines.append(f"    {f['detail']}")
            if f.get("action"):
                lines.append(f"    Fix: {f['action']}")
            lines.append("")
        checklist = _yearend_checklist(db, s, e)
        lines.append("## Year-end checklist")
        for c in checklist:
            lines.append(f"[{'x' if c['ok'] else ' '}] {c['item']}")
        z.writestr("10_tax_optimization_summary.md", "\n".join(lines))

    log(db, user.email, "export", "yearend", year, {"files": 10})
    db.commit()
    return Response(buf.getvalue(), media_type="application/zip", headers={
        "Content-Disposition":
        f'attachment; filename="OilForge_YearEnd_{year}.zip"'})


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


# ------------------------------------------------------ GST filing detail

from ..reports import gst_detail as _gst_detail  # noqa: E402


@router.get("/gst-filing")
def gst_filing(start: str | None = None, end: str | None = None,
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    s, e = parse_period(db, start, end)
    return _gst_detail.filing_summary(db, s, e)


@router.get("/gst-filing.csv")
def gst_filing_csv(start: str | None = None, end: str | None = None,
                   db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    s, e = parse_period(db, start, end)
    summary = _gst_detail.filing_summary(db, s, e)
    log(db, user.email, "export", "gst_filing", "",
        {"period": [s.isoformat(), e.isoformat()]})
    db.commit()
    return Response(_gst_detail.filing_csv(summary), media_type="text/csv",
                    headers={"Content-Disposition":
                             f'attachment; filename="GST_Filing_{e.year}.csv"'})
