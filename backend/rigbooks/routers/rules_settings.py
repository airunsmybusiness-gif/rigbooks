"""Tax-rule packs (view/override per year) and app settings."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..audit import log
from ..auth import current_user
from ..cra import engine as cra
from ..db import get_db
from ..helpers import DEFAULT_SETTINGS, get_setting, put_setting, rules_for_year
from ..models import User

router = APIRouter(prefix="/api", tags=["rules", "settings"])


@router.get("/rules/years")
def years():
    return cra.available_years()


@router.get("/rules/{year}")
def get_rules(year: int, db: Session = Depends(get_db),
              user: User = Depends(current_user)):
    return rules_for_year(db, year)


@router.put("/rules/{year}")
def override_rules(year: int, payload: dict, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    """Persist UI edits as an override layer on top of the packaged pack —
    the shipped JSON files stay pristine for reference."""
    existing = get_setting(db, f"cra_rules_{year}", {}) or {}
    merged = cra._deep_merge(existing, payload)
    put_setting(db, f"cra_rules_{year}", merged)
    log(db, user.email, "update", "cra_rules", year, {"changes": payload})
    db.commit()
    return rules_for_year(db, year)


@router.delete("/rules/{year}/overrides")
def reset_rules(year: int, db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    put_setting(db, f"cra_rules_{year}", {})
    log(db, user.email, "update", "cra_rules", year, {"reset": True})
    db.commit()
    return rules_for_year(db, year)


@router.get("/settings")
def all_settings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return {k: get_setting(db, k) for k in DEFAULT_SETTINGS}


@router.put("/settings/{key}")
def update_setting(key: str, payload: dict, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    value = payload.get("value", payload)
    put_setting(db, key, value)
    log(db, user.email, "update", "settings", key)
    db.commit()
    return {key: value}
