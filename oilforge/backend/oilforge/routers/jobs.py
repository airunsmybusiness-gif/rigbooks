"""Jobs (contracts/work orders), field-ticket entries, and job profitability."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..audit import log
from ..auth import current_user
from ..db import get_db
from ..helpers import get_setting, put_setting
from ..models import Expense, Invoice, Job, JobEntry, User
from .crud_factory import make_crud_router, serialize

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_out(db: Session, job: Job) -> dict:
    out = serialize(job)
    out["client_name"] = job.client.name if job.client else ""
    out["site_name"] = job.site.name if job.site else ""
    out["site_lsd"] = job.site.lsd if job.site else ""
    return out


@router.get("")
def list_jobs(status: str | None = None, q: str | None = None,
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = (db.query(Job).options(joinedload(Job.client), joinedload(Job.site))
             .order_by(Job.id.desc()))
    if status:
        query = query.filter(Job.status == status)
    if q:
        query = query.filter(Job.title.ilike(f"%{q}%") | Job.number.ilike(f"%{q}%"))
    return {"items": [_job_out(db, j) for j in query.all()]}


@router.post("", status_code=201)
def create_job(payload: dict, db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    if not payload.get("client_id"):
        raise HTTPException(422, "client_id is required")
    cfg = dict(get_setting(db, "job"))
    number = payload.get("number") or f"{cfg['prefix']}{cfg['next_number']:04d}"
    cfg["next_number"] = int(cfg.get("next_number", 1)) + 1
    put_setting(db, "job", cfg)
    job = Job(number=number)
    _apply(job, payload)
    db.add(job)
    db.flush()
    log(db, user.email, "create", "jobs", job.id, {"number": number})
    db.commit()
    db.refresh(job)
    return _job_out(db, job)


def _apply(job: Job, p: dict) -> None:
    for f in ("title", "client_id", "site_id", "rate_type", "day_rate",
              "hourly_rate", "fixed_price", "mobilization_fee", "holdback_pct",
              "status", "notes"):
        if f in p:
            setattr(job, f, p[f] if p[f] != "" else None if f == "site_id" else p[f])
    for f in ("start_date", "end_date"):
        if f in p:
            setattr(job, f, date.fromisoformat(p[f]) if p[f] else None)


@router.put("/{job_id}")
def update_job(job_id: int, payload: dict, db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    _apply(job, payload)
    log(db, user.email, "update", "jobs", job_id, {"changes": payload})
    db.commit()
    return _job_out(db, job)


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if db.query(JobEntry).filter_by(job_id=job_id).count():
        raise HTTPException(409, "Job has field entries - delete them first or close the job instead")
    log(db, user.email, "delete", "jobs", job_id, {"was": serialize(job)})
    db.delete(job)
    db.commit()
    return {"deleted": job_id}


@router.get("/{job_id}/profitability")
def profitability(job_id: int, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    """Per-contract costing: billed entries + invoices vs job-tagged costs."""
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    entries = db.query(JobEntry).filter_by(job_id=job_id).all()
    earned = sum(e.quantity * e.rate for e in entries)
    unbilled = sum(e.quantity * e.rate for e in entries if e.invoice_id is None)
    costs = sum(x.amount for x in db.query(Expense).filter_by(job_id=job_id))
    invoices = (db.query(Invoice).options(joinedload(Invoice.lines))
                .filter_by(job_id=job_id).all())
    invoiced = sum(i.subtotal for i in invoices)
    holdback_out = sum(i.holdback for i in invoices if not i.holdback_released)
    margin = earned - costs
    return {
        "job": _job_out(db, job),
        "earned": round(earned, 2),
        "unbilled": round(unbilled, 2),
        "invoiced_subtotal": round(invoiced, 2),
        "holdback_outstanding": round(holdback_out, 2),
        "costs": round(costs, 2),
        "margin": round(margin, 2),
        "margin_pct": round(margin / earned * 100, 1) if earned else 0.0,
        "entry_count": len(entries),
    }


# Field-ticket entries (nested CRUD via the generic factory).
entries_router = make_crud_router(
    JobEntry, "job-entries",
    search_fields=("description", "ticket_ref"))
