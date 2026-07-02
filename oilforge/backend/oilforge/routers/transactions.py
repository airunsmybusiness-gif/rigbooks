"""Bank import + transaction management + classifier rules."""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..audit import log
from ..auth import current_user
from ..classifier import (CATEGORIES, parse_bank_csv, seed_default_rules,
                          status_for)
from ..cra import engine as cra
from ..db import get_db
from ..helpers import get_province, parse_period, rules_for_year
from ..models import BankTransaction, ClassifierRule, User
from .crud_factory import serialize

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _recalc_itc(db: Session, tx: BankTransaction) -> None:
    if tx.status != "business" or tx.credit > 0:
        tx.itc = 0.0
        return
    rules = rules_for_year(db, tx.date.year)
    tx.itc = cra.calc_itc(tx.debit, tx.category, rules, province=get_province(db))


@router.get("/categories")
def categories():
    return CATEGORIES


@router.post("/import")
async def import_csv(file: UploadFile, db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    content = (await file.read()).decode("utf-8", errors="replace")
    seed_default_rules(db)
    rules = db.query(ClassifierRule).order_by(ClassifierRule.priority).all()
    parsed = parse_bank_csv(content, rules)
    if not parsed:
        raise HTTPException(422, "No transactions found. Expected columns: "
                                 "Date, Description, Debit, Credit")
    created = skipped = 0
    for row in parsed:
        if db.query(BankTransaction).filter_by(
                date=row["date"], description=row["description"],
                debit=row["debit"], credit=row["credit"]).first():
            skipped += 1
            continue
        tx = BankTransaction(**row, source_file=file.filename or "")
        db.add(tx)
        _recalc_itc(db, tx)
        created += 1
    log(db, user.email, "import", "bank_transactions", "",
        {"file": file.filename, "created": created, "skipped_duplicates": skipped})
    db.commit()
    return {"created": created, "skipped_duplicates": skipped}


@router.get("")
def list_transactions(start: str | None = None, end: str | None = None,
                      q: str | None = None, category: str | None = None,
                      status: str | None = None, unposted: bool = False,
                      limit: int = Query(1000, le=10000), offset: int = 0,
                      db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    s, e = parse_period(db, start, end)
    query = (db.query(BankTransaction)
             .filter(BankTransaction.date >= s, BankTransaction.date <= e))
    if q:
        query = query.filter(or_(BankTransaction.description.ilike(f"%{q}%"),
                                 BankTransaction.notes.ilike(f"%{q}%")))
    if category:
        query = query.filter(BankTransaction.category == category)
    if status:
        query = query.filter(BankTransaction.status == status)
    if unposted:
        query = query.filter(BankTransaction.status == "shareholder",
                             BankTransaction.posted_shareholder_txn_id.is_(None))
    total = query.count()
    items = (query.order_by(BankTransaction.date.desc(), BankTransaction.id.desc())
             .offset(offset).limit(limit).all())
    return {"total": total, "items": [serialize(t) for t in items]}


@router.put("/{tx_id}")
def update_transaction(tx_id: int, payload: dict, db: Session = Depends(get_db),
                       user: User = Depends(current_user)):
    tx = db.get(BankTransaction, tx_id)
    if tx is None:
        raise HTTPException(404, "Transaction not found")
    if "category" in payload:
        tx.category = payload["category"]
        tx.status = payload.get("status") or status_for(tx.category)
    if "status" in payload:
        tx.status = payload["status"]
    if "notes" in payload:
        tx.notes = payload["notes"]
    _recalc_itc(db, tx)
    log(db, user.email, "update", "bank_transactions", tx_id, {"changes": payload})
    db.commit()
    return serialize(tx)


@router.delete("/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(get_db),
                       user: User = Depends(current_user)):
    tx = db.get(BankTransaction, tx_id)
    if tx is None:
        raise HTTPException(404, "Transaction not found")
    log(db, user.email, "delete", "bank_transactions", tx_id, {"was": serialize(tx)})
    db.delete(tx)
    db.commit()
    return {"deleted": tx_id}


@router.get("/classifier-rules")
def list_rules(db: Session = Depends(get_db), user: User = Depends(current_user)):
    seed_default_rules(db)
    return [serialize(r) for r in
            db.query(ClassifierRule).order_by(ClassifierRule.priority).all()]


@router.post("/classifier-rules", status_code=201)
def create_rule(payload: dict, db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    rule = ClassifierRule(pattern=payload.get("pattern", ""),
                          category=payload.get("category", "Other Operating"),
                          priority=int(payload.get("priority", 100)),
                          enabled=bool(payload.get("enabled", True)))
    db.add(rule)
    db.flush()
    log(db, user.email, "create", "classifier_rules", rule.id, payload)
    db.commit()
    return serialize(rule)


@router.delete("/classifier-rules/{rule_id}")
def delete_rule(rule_id: int, db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    rule = db.get(ClassifierRule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    db.delete(rule)
    log(db, user.email, "delete", "classifier_rules", rule_id)
    db.commit()
    return {"deleted": rule_id}
