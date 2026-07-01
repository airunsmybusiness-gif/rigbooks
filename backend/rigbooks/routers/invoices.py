"""Customer invoicing with professional PDF output."""
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from ..audit import log
from ..auth import current_user
from ..db import get_db
from ..helpers import get_setting, put_setting, rules_for_year, get_province
from ..cra import engine as cra
from ..models import Customer, Invoice, InvoiceLine, RevenueEntry, User
from ..reports.pdf import invoice_pdf

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


def _serialize(inv: Invoice) -> dict:
    return {
        "id": inv.id, "number": inv.number, "customer_id": inv.customer_id,
        "customer_name": inv.customer.name if inv.customer else "",
        "date": inv.date.isoformat(),
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "status": inv.status, "gst_rate": inv.gst_rate, "notes": inv.notes,
        "subtotal": inv.subtotal, "gst": inv.gst, "total": inv.total,
        "lines": [{"id": l.id, "description": l.description,
                   "quantity": l.quantity, "unit_price": l.unit_price,
                   "amount": round(l.quantity * l.unit_price, 2)}
                  for l in inv.lines],
    }


def _apply(inv: Invoice, payload: dict, db: Session) -> None:
    if "customer_id" in payload:
        inv.customer_id = payload["customer_id"]
    if "date" in payload:
        inv.date = date.fromisoformat(payload["date"])
    if payload.get("due_date"):
        inv.due_date = date.fromisoformat(payload["due_date"])
    if "status" in payload:
        inv.status = payload["status"]
    if "notes" in payload:
        inv.notes = payload["notes"]
    if "lines" in payload:
        inv.lines.clear()
        for l in payload["lines"]:
            inv.lines.append(InvoiceLine(
                description=l.get("description", ""),
                quantity=float(l.get("quantity", 1) or 1),
                unit_price=float(l.get("unit_price", 0) or 0)))


@router.get("")
def list_invoices(db: Session = Depends(get_db), user: User = Depends(current_user)):
    invoices = (db.query(Invoice).options(joinedload(Invoice.lines),
                                          joinedload(Invoice.customer))
                .order_by(Invoice.date.desc(), Invoice.id.desc()).all())
    return [_serialize(i) for i in invoices]


@router.post("", status_code=201)
def create_invoice(payload: dict, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    if not payload.get("customer_id"):
        raise HTTPException(422, "customer_id is required")
    cfg = dict(get_setting(db, "invoice"))
    number = payload.get("number") or f"{cfg['prefix']}{cfg['next_number']:04d}"
    cfg["next_number"] = int(cfg.get("next_number", 1)) + 1
    put_setting(db, "invoice", cfg)

    rules = rules_for_year(db, date.today().year)
    inv = Invoice(number=number, customer_id=payload["customer_id"],
                  date=date.today(),
                  gst_rate=cra.gst_rate(rules, get_province(db)))
    _apply(inv, payload, db)
    db.add(inv)
    db.flush()
    log(db, user.email, "create", "invoices", inv.id, {"number": number})
    db.commit()
    return _serialize(inv)


@router.put("/{invoice_id}")
def update_invoice(invoice_id: int, payload: dict, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found")
    was_paid = inv.status == "paid"
    _apply(inv, payload, db)
    # Marking an invoice paid books the revenue automatically.
    if inv.status == "paid" and not was_paid:
        db.add(RevenueEntry(
            date=date.today(), client=inv.customer.name if inv.customer else "",
            customer_id=inv.customer_id, job=f"Invoice {inv.number}",
            amount=inv.total, gst_included=True, gst_amount=inv.gst,
            invoice_id=inv.id, notes="Auto-created on invoice payment"))
    log(db, user.email, "update", "invoices", invoice_id, {"changes": payload})
    db.commit()
    return _serialize(inv)


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        raise HTTPException(404, "Invoice not found")
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
    business = get_setting(db, "business")
    pdf_bytes = invoice_pdf(_serialize(inv), business,
                            inv.customer.address if inv.customer else "",
                            terms=get_setting(db, "invoice").get("terms", ""))
    log(db, user.email, "export", "invoices", invoice_id, {"format": "pdf"})
    db.commit()
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                             headers={"Content-Disposition":
                                      f'attachment; filename="{inv.number}.pdf"'})
