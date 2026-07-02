"""Invoicing with progress billing from job entries and holdback tracking."""
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from ..audit import log
from ..auth import current_user
from ..cra import engine as cra
from ..db import get_db
from ..helpers import get_province, get_setting, put_setting, rules_for_year
from ..models import Invoice, InvoiceLine, Job, JobEntry, User
from ..reports.pdf import invoice_pdf

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


def _serialize(inv: Invoice) -> dict:
    return {
        "id": inv.id, "number": inv.number, "client_id": inv.client_id,
        "client_name": inv.client.name if inv.client else "",
        "job_id": inv.job_id,
        "job_number": inv.job.number if inv.job else "",
        "date": inv.date.isoformat(),
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "status": inv.status, "gst_rate": inv.gst_rate,
        "holdback_pct": inv.holdback_pct, "holdback": inv.holdback,
        "holdback_released": inv.holdback_released,
        "notes": inv.notes, "subtotal": inv.subtotal, "gst": inv.gst,
        "total": inv.total, "amount_due_now": inv.amount_due_now,
        "lines": [{"id": l.id, "description": l.description,
                   "quantity": l.quantity, "unit_price": l.unit_price,
                   "amount": round(l.quantity * l.unit_price, 2)}
                  for l in inv.lines],
    }


def _apply(inv: Invoice, p: dict) -> None:
    for f in ("client_id", "job_id", "status", "notes", "holdback_pct"):
        if f in p:
            setattr(inv, f, p[f] if p[f] != "" else None if f == "job_id" else p[f])
    for f in ("date", "due_date", "paid_date", "holdback_released_date"):
        if f in p:
            setattr(inv, f, date.fromisoformat(p[f]) if p[f] else None)
    if "holdback_released" in p:
        inv.holdback_released = bool(p["holdback_released"])
        if inv.holdback_released and not inv.holdback_released_date:
            inv.holdback_released_date = date.today()
    if "lines" in p:
        inv.lines.clear()
        for l in p["lines"]:
            inv.lines.append(InvoiceLine(
                description=l.get("description", ""),
                quantity=float(l.get("quantity", 1) or 1),
                unit_price=float(l.get("unit_price", 0) or 0)))


@router.get("")
def list_invoices(db: Session = Depends(get_db), user: User = Depends(current_user)):
    q = (db.query(Invoice)
         .options(joinedload(Invoice.lines), joinedload(Invoice.client),
                  joinedload(Invoice.job))
         .order_by(Invoice.date.desc(), Invoice.id.desc()))
    return [_serialize(i) for i in q.all()]


def _next_number(db: Session) -> str:
    cfg = dict(get_setting(db, "invoice"))
    number = f"{cfg['prefix']}{cfg['next_number']:04d}"
    cfg["next_number"] = int(cfg.get("next_number", 1)) + 1
    put_setting(db, "invoice", cfg)
    return number


@router.post("", status_code=201)
def create_invoice(payload: dict, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    if not payload.get("client_id"):
        raise HTTPException(422, "client_id is required")
    rules = rules_for_year(db, date.today().year)
    inv = Invoice(number=payload.get("number") or _next_number(db),
                  client_id=payload["client_id"], date=date.today(),
                  gst_rate=cra.gst_rate(rules, get_province(db)))
    _apply(inv, payload)
    db.add(inv)
    db.flush()
    log(db, user.email, "create", "invoices", inv.id, {"number": inv.number})
    db.commit()
    return _serialize(inv)


@router.post("/from-job/{job_id}", status_code=201)
def invoice_from_job(job_id: int, db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    """Progress billing: pull all unbilled field entries into a new invoice,
    inheriting the job's holdback percentage."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    entries = (db.query(JobEntry)
               .filter(JobEntry.job_id == job_id, JobEntry.invoice_id.is_(None))
               .order_by(JobEntry.date).all())
    if not entries:
        raise HTTPException(422, "No unbilled entries on this job")
    rules = rules_for_year(db, date.today().year)
    inv = Invoice(number=_next_number(db), client_id=job.client_id,
                  job_id=job.id, date=date.today(),
                  gst_rate=cra.gst_rate(rules, get_province(db)),
                  holdback_pct=job.holdback_pct,
                  notes=f"Progress billing - {job.number} {job.title}".strip())
    for e in entries:
        label = {"day": "Day rate", "hours": "Hourly",
                 "mobilization": "Mobilization", "charge": "Charge"}[e.kind]
        desc = f"{e.date.isoformat()} {label}: {e.description or job.title}"
        if e.ticket_ref:
            desc += f" (ticket {e.ticket_ref})"
        inv.lines.append(InvoiceLine(description=desc, quantity=e.quantity,
                                     unit_price=e.rate))
    db.add(inv)
    db.flush()
    for e in entries:
        e.invoice_id = inv.id
    log(db, user.email, "create", "invoices", inv.id,
        {"number": inv.number, "from_job": job.number, "entries": len(entries)})
    db.commit()
    return _serialize(inv)


@router.put("/{invoice_id}")
def update_invoice(invoice_id: int, payload: dict, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found")
    if payload.get("status") == "paid" and inv.status != "paid":
        inv.paid_date = date.today()
    _apply(inv, payload)
    log(db, user.email, "update", "invoices", invoice_id, {"changes": payload})
    db.commit()
    return _serialize(inv)


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found")
    # Release any job entries billed on it so they can be re-invoiced.
    for e in db.query(JobEntry).filter_by(invoice_id=invoice_id):
        e.invoice_id = None
    log(db, user.email, "delete", "invoices", invoice_id, {"number": inv.number})
    db.delete(inv)
    db.commit()
    return {"deleted": invoice_id}


@router.get("/{invoice_id}/pdf")
def download_pdf(invoice_id: int, db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found")
    pdf = invoice_pdf(_serialize(inv), get_setting(db, "business"),
                      inv.client.address if inv.client else "",
                      terms=get_setting(db, "invoice").get("terms", ""))
    log(db, user.email, "export", "invoices", invoice_id, {"format": "pdf"})
    db.commit()
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="{inv.number}.pdf"'})
