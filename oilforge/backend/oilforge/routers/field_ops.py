"""Field operations & data tooling: photo attachments, parts inventory,
safety registry, CSV import tools, audit-log export, and the accountant
handoff ZIP package."""
import csv
import io
import json
import secrets
import zipfile
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from ..audit import log
from ..auth import current_user
from ..config import DATA_DIR
from ..db import get_db
from ..helpers import fiscal_period, get_setting, parse_period
from ..classifier import classify, seed_default_rules, status_for
from ..models import (Attachment, AuditLog, BankTransaction, ClassifierRule,
                      Client, DividendDeclaration, Equipment, Expense, Job,
                      Part, SafetyItem, Shareholder, ShareholderTxn, User)
from ..reports import gst_detail, statements, t2
from ..reports.pdf import financial_summary_pdf
from ..shareholder import dividends_by_kind, journal_entries
from ..cra import engine as cra
from ..helpers import rules_for_year
from .crud_factory import make_crud_router, serialize

router = APIRouter(prefix="/api", tags=["field-ops"])

parts_router = make_crud_router(Part, "parts", date_field="",
                                search_fields=("name", "part_number", "location"))
safety_router = make_crud_router(SafetyItem, "safety", date_field="",
                                 search_fields=("name", "reference", "kind"))

ATTACH_DIR = DATA_DIR / "attachments"
ATTACH_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "image/heic",
                 "application/pdf"}
_MAX_ATTACHMENT = 15 * 1024 * 1024  # 15 MB


# ------------------------------------------------------------- attachments

@router.post("/attachments/{entity}/{entity_id}", status_code=201)
async def upload_attachment(entity: str, entity_id: int, file: UploadFile,
                            note: str = "",
                            db: Session = Depends(get_db),
                            user: User = Depends(current_user)):
    blob = await file.read()
    if len(blob) > _MAX_ATTACHMENT:
        raise HTTPException(413, "File too large (15 MB max)")
    mime = file.content_type or "application/octet-stream"
    if mime not in _ALLOWED_MIME:
        raise HTTPException(415, f"Unsupported type {mime} - photos or PDF only")
    stored = f"{secrets.token_hex(12)}_{entity}_{entity_id}"
    (ATTACH_DIR / stored).write_bytes(blob)
    att = Attachment(entity=entity, entity_id=entity_id,
                     filename=file.filename or "photo.jpg",
                     stored_name=stored, mime=mime, size=len(blob), note=note)
    db.add(att)
    db.flush()
    log(db, user.email, "create", "attachments", att.id,
        {"entity": entity, "entity_id": entity_id, "file": att.filename})
    db.commit()
    return serialize(att)


# NOTE: registered before /attachments/{entity}/{entity_id} so "file"
# isn't swallowed by the entity route.
@router.get("/attachments/file/{attachment_id}")
def get_attachment(attachment_id: int, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    att = db.get(Attachment, attachment_id)
    if att is None or not (ATTACH_DIR / att.stored_name).exists():
        raise HTTPException(404, "Attachment not found")
    return FileResponse(ATTACH_DIR / att.stored_name, media_type=att.mime,
                        filename=att.filename)


@router.get("/attachments/{entity}/{entity_id}")
def list_attachments(entity: str, entity_id: int,
                     db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    rows = (db.query(Attachment)
            .filter_by(entity=entity, entity_id=entity_id)
            .order_by(Attachment.id.desc()).all())
    return [serialize(a) for a in rows]


@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    att = db.get(Attachment, attachment_id)
    if att is None:
        raise HTTPException(404, "Attachment not found")
    (ATTACH_DIR / att.stored_name).unlink(missing_ok=True)
    log(db, user.email, "delete", "attachments", attachment_id,
        {"file": att.filename})
    db.delete(att)
    db.commit()
    return {"deleted": attachment_id}


# ------------------------------------------------------------ parts actions

@router.post("/parts/{part_id}/adjust")
def adjust_part(part_id: int, payload: dict, db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    """Receive (+qty) or use (−qty) stock; usage can book a maintenance cost."""
    part = db.get(Part, part_id)
    if part is None:
        raise HTTPException(404, "Part not found")
    delta = float(payload.get("delta", 0) or 0)
    part.qty_on_hand = round(part.qty_on_hand + delta, 2)
    if part.qty_on_hand < 0:
        raise HTTPException(422, "Cannot go below zero on hand")
    log(db, user.email, "update", "parts", part_id,
        {"delta": delta, "reason": payload.get("reason", "")})
    db.commit()
    return {**serialize(part),
            "low_stock": part.qty_on_hand <= part.min_qty}


# ------------------------------------------------------------- CSV imports

IMPORT_TEMPLATES = {
    "expenses": ["date", "vendor", "description", "amount", "category",
                 "receipt_ref"],
    "clients": ["name", "contact", "email", "phone", "address", "gst_number"],
    "equipment": ["name", "serial", "cca_class", "cost", "acquired"],
    # Migration-wizard kinds (historical data from the old Streamlit app,
    # spreadsheets, or any prior system):
    "bank_transactions": ["date", "description", "debit", "credit",
                          "category", "receipt_ref"],
    "jobs": ["number", "title", "client_name", "rate_type", "day_rate",
             "hourly_rate", "holdback_pct", "status", "start_date"],
    "shareholder_history": ["date", "shareholder_name", "type", "amount",
                            "memo"],
    "dividends": ["date", "shareholder_name", "amount", "kind",
                  "settlement", "resolution_ref"],
}

TEMPLATE_EXAMPLES = {
    "bank_transactions": "2024-03-05,UFA CARDLOCK NISKU,412.88,,Fuel & Petroleum,R-101",
    "jobs": "WO-H001,Completions support,Prairie Energy Resources,day_rate,2400,0,10,closed,2024-02-01",
    "shareholder_history": "2024-01-15,J. Smith,withdrawal,5000,Opening-year draw (use type 'contribution' with a negative-history note for opening credit balances)",
    "dividends": "2024-12-31,J. Smith,45000,non_eligible,loan,RES-2024-01",
}


@router.get("/import/template/{kind}")
def import_template(kind: str, user: User = Depends(current_user)):
    if kind not in IMPORT_TEMPLATES:
        raise HTTPException(404, f"No template for {kind!r}. "
                                 f"Available: {list(IMPORT_TEMPLATES)}")
    body = ",".join(IMPORT_TEMPLATES[kind]) + "\n"
    if kind in TEMPLATE_EXAMPLES:
        body += TEMPLATE_EXAMPLES[kind] + "\n"
    return Response(body,
                    media_type="text/csv", headers={
                        "Content-Disposition":
                        f'attachment; filename="oilforge_{kind}_template.csv"'})


def _holder_by_name(db: Session, name: str):
    """Find or create a shareholder for migration rows."""
    name = name.strip()
    holder = (db.query(Shareholder).filter(Shareholder.name == name)
              .order_by(Shareholder.id).first())
    if holder is None:
        holder = Shareholder(name=name)
        db.add(holder)
        db.flush()
    return holder


@router.post("/import/{kind}")
async def import_csv(kind: str, file: UploadFile,
                     db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    """Bulk import from the matching CSV template (expenses recompute ITCs)."""
    if kind not in IMPORT_TEMPLATES:
        raise HTTPException(404, f"Unknown import kind {kind!r}")
    content = (await file.read()).decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    created, errors = 0, []
    for i, row in enumerate(reader, start=2):
        try:
            if kind == "expenses":
                d = date.fromisoformat(row["date"].strip())
                rules = rules_for_year(db, d.year)
                amount = float(row["amount"])
                category = row.get("category", "Other Operating").strip() or "Other Operating"
                db.add(Expense(
                    date=d, vendor=row.get("vendor", ""), amount=amount,
                    description=row.get("description", ""), category=category,
                    receipt_ref=row.get("receipt_ref", ""),
                    itc=cra.calc_itc(amount, category, rules)))
            elif kind == "clients":
                db.add(Client(**{k: row.get(k, "") for k in IMPORT_TEMPLATES["clients"]}))
            elif kind == "equipment":
                db.add(Equipment(
                    name=row["name"], serial=row.get("serial", ""),
                    cca_class=row.get("cca_class", "8") or "8",
                    cost=float(row.get("cost", 0) or 0),
                    acquired=date.fromisoformat(row["acquired"])
                    if row.get("acquired") else None))
            elif kind == "bank_transactions":
                d = date.fromisoformat(row["date"].strip())
                debit = float(row.get("debit") or 0)
                credit = float(row.get("credit") or 0)
                desc = row.get("description", "").strip()
                if db.query(BankTransaction).filter_by(
                        date=d, description=desc, debit=debit,
                        credit=credit).first():
                    continue  # idempotent, like the main bank import
                seed_default_rules(db)
                category = (row.get("category", "").strip()
                            or classify(desc, db.query(ClassifierRule)
                                        .order_by(ClassifierRule.priority).all()))
                status = status_for(category)
                rules = rules_for_year(db, d.year)
                itc = (cra.calc_itc(debit, category, rules)
                       if status == "business" and debit > 0 else 0.0)
                db.add(BankTransaction(
                    date=d, description=desc, debit=debit, credit=credit,
                    category=category, status=status, itc=itc,
                    receipt_ref=row.get("receipt_ref", ""),
                    source_file=f"migration:{file.filename}"))
            elif kind == "jobs":
                client = (db.query(Client)
                          .filter(Client.name == row["client_name"].strip())
                          .first())
                if client is None:
                    client = Client(name=row["client_name"].strip())
                    db.add(client)
                    db.flush()
                db.add(Job(
                    number=row["number"].strip(),
                    title=row.get("title", ""), client_id=client.id,
                    rate_type=row.get("rate_type", "day_rate") or "day_rate",
                    day_rate=float(row.get("day_rate") or 0),
                    hourly_rate=float(row.get("hourly_rate") or 0),
                    holdback_pct=float(row.get("holdback_pct") or 0),
                    status=row.get("status", "closed") or "closed",
                    start_date=date.fromisoformat(row["start_date"])
                    if row.get("start_date") else None))
            elif kind == "shareholder_history":
                holder = _holder_by_name(db, row["shareholder_name"])
                txn_type = row.get("type", "withdrawal").strip()
                if cra.loan_direction(txn_type) == 0:
                    raise ValueError(f"unknown type {txn_type!r}")
                db.add(ShareholderTxn(
                    shareholder_id=holder.id,
                    date=date.fromisoformat(row["date"].strip()),
                    type=txn_type, amount=float(row["amount"]),
                    memo=row.get("memo", "")))
            elif kind == "dividends":
                holder = _holder_by_name(db, row["shareholder_name"])
                db.add(DividendDeclaration(
                    shareholder_id=holder.id,
                    date=date.fromisoformat(row["date"].strip()),
                    amount=float(row["amount"]),
                    kind=row.get("kind", "non_eligible") or "non_eligible",
                    settlement=row.get("settlement", "loan") or "loan",
                    resolution_ref=row.get("resolution_ref", "")))
            created += 1
        except (KeyError, ValueError) as e:
            errors.append({"row": i, "error": str(e)})
    log(db, user.email, "import", f"csv_{kind}", "",
        {"file": file.filename, "created": created, "errors": len(errors)})
    db.commit()
    return {"created": created, "errors": errors[:20]}


# ----------------------------------------------------------- audit export

@router.get("/reports/audit-log.csv")
def audit_csv(db: Session = Depends(get_db), user: User = Depends(current_user)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp_utc", "user", "action", "entity", "entity_id", "details"])
    for a in db.query(AuditLog).order_by(AuditLog.ts):
        w.writerow([a.ts.isoformat(), a.user, a.action, a.entity, a.entity_id,
                    json.dumps(a.details)])
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition":
        f'attachment; filename="oilforge_audit_log_{date.today()}.csv"'})


# ------------------------------------------------- accountant handoff ZIP

@router.get("/reports/accountant-package.zip")
def accountant_package(year: int, db: Session = Depends(get_db),
                       user: User = Depends(current_user)):
    """Everything the accountant needs for the year in one download."""
    start, end = fiscal_period(db, year)
    business = get_setting(db, "business")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        summary = statements.collect(db, start, end)
        tb = statements.trial_balance(db, start, end)
        z.writestr("01_financial_summary.pdf",
                   financial_summary_pdf(summary, tb, business))
        z.writestr("02_t2_package.json",
                   json.dumps(t2.year_end_package(db, start, end), indent=1))
        gst = gst_detail.filing_summary(db, start, end)
        z.writestr("03_gst_filing_summary.csv", gst_detail.filing_csv(gst))
        z.writestr("03_gst_filing_detail.json", json.dumps(gst, indent=1))

        jbuf = io.StringIO()
        w = csv.DictWriter(jbuf, fieldnames=["date", "memo", "debit_account",
                                             "credit_account", "amount"])
        w.writeheader()
        w.writerows(journal_entries(db, start, end))
        z.writestr("04_shareholder_journal.csv", jbuf.getvalue())

        t5buf = io.StringIO()
        w2 = csv.writer(t5buf)
        w2.writerow(["shareholder", "kind", "actual", "taxable", "dtc"])
        rules = rules_for_year(db, year)
        for holder in db.query(Shareholder).all():
            t5 = cra.dividend_t5(dividends_by_kind(db, holder.id, year), rules)
            for kind, k in t5["kinds"].items():
                w2.writerow([holder.name, kind, k["actual"], k["taxable"], k["dtc"]])
        z.writestr("05_t5_dividends.csv", t5buf.getvalue())

        z.writestr("06_audit_log.csv",
                   audit_csv(db, user).body.decode())
        z.writestr("README.txt",
                   f"OilForge accountant package - fiscal {year}\n"
                   f"Business: {business.get('name')}\n"
                   f"Generated: {date.today().isoformat()}\n\n"
                   "01 Financial summary PDF (income statement, GST34, trial balance)\n"
                   "02 T2 working papers JSON (S1, S8, S50, S125 GIFI, RE reconciliation, provision entry)\n"
                   "03 GST filing summary CSV + detail JSON (operating vs capital ITCs, quarterly, holdback memo)\n"
                   "04 Shareholder journal entries CSV (double-entry)\n"
                   "05 T5 dividend figures per shareholder\n"
                   "06 Full audit log\n\n"
                   "All figures are working-paper estimates from single-entry "
                   "records. Verify before filing.")
    log(db, user.email, "export", "accountant_package", year, {})
    db.commit()
    return Response(buf.getvalue(), media_type="application/zip", headers={
        "Content-Disposition":
        f'attachment; filename="OilForge_Accountant_Package_{year}.zip"'})
