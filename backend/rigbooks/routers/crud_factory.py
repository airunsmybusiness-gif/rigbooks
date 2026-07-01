"""Generic CRUD router factory.

Most RigBooks entities are flat records with identical needs: list with a
date-range filter + text search, create, update, delete — all audited.
The factory builds those endpoints once; per-model tax math (ITC, GST)
plugs in via a before_save hook.
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date as SADate
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..audit import log
from ..auth import current_user
from ..db import get_db
from ..helpers import parse_period
from ..models import User


def _column_names(model) -> set[str]:
    return {c.key for c in model.__table__.columns}


def serialize(obj) -> dict:
    out = {}
    for c in obj.__table__.columns:
        v = getattr(obj, c.key)
        if isinstance(v, (date, datetime)):
            v = v.isoformat()
        out[c.key] = v
    return out


def _coerce(model, data: dict) -> dict:
    """Whitelist payload keys to real columns and parse ISO dates."""
    cols = model.__table__.columns
    clean = {}
    for k, v in data.items():
        if k in ("id", "created_at", "updated_at") or k not in cols:
            continue
        if isinstance(cols[k].type, SADate) and isinstance(v, str):
            v = date.fromisoformat(v)
        clean[k] = v
    return clean


def make_crud_router(model, prefix: str, *, date_field: str = "date",
                     search_fields: tuple[str, ...] = (),
                     before_save=None, order_desc: bool = True) -> APIRouter:
    router = APIRouter(prefix=f"/api/{prefix}", tags=[prefix])
    entity = model.__tablename__

    @router.get("")
    def list_items(start: str | None = None, end: str | None = None,
                   q: str | None = None, limit: int = Query(500, le=5000),
                   offset: int = 0,
                   db: Session = Depends(get_db), user: User = Depends(current_user)):
        query = db.query(model)
        if date_field and date_field in _column_names(model):
            s, e = parse_period(start, end)
            col = getattr(model, date_field)
            query = query.filter(col >= s, col <= e)
            query = query.order_by(col.desc() if order_desc else col.asc(), model.id.desc())
        else:
            query = query.order_by(model.id.desc())
        if q and search_fields:
            like = f"%{q}%"
            query = query.filter(or_(*[getattr(model, f).ilike(like) for f in search_fields]))
        total = query.count()
        items = query.offset(offset).limit(limit).all()
        return {"total": total, "items": [serialize(i) for i in items]}

    @router.post("", status_code=201)
    def create_item(payload: dict, db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
        data = _coerce(model, payload)
        if before_save:
            before_save(db, data)
        obj = model(**data)
        db.add(obj)
        db.flush()
        log(db, user.email, "create", entity, obj.id, {"data": payload})
        db.commit()
        return serialize(obj)

    @router.put("/{item_id}")
    def update_item(item_id: int, payload: dict, db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
        obj = db.get(model, item_id)
        if obj is None:
            raise HTTPException(404, f"{entity} {item_id} not found")
        data = _coerce(model, {**serialize(obj), **payload})
        if before_save:
            before_save(db, data)
        for k, v in data.items():
            setattr(obj, k, v)
        log(db, user.email, "update", entity, item_id, {"changes": payload})
        db.commit()
        return serialize(obj)

    @router.delete("/{item_id}")
    def delete_item(item_id: int, db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
        obj = db.get(model, item_id)
        if obj is None:
            raise HTTPException(404, f"{entity} {item_id} not found")
        log(db, user.email, "delete", entity, item_id, {"was": serialize(obj)})
        db.delete(obj)
        db.commit()
        return {"deleted": item_id}

    return router
