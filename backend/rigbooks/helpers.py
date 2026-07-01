"""Shared router helpers: period filtering, settings access, rules lookup."""
from datetime import date

from sqlalchemy.orm import Session

from .cra import engine as cra
from .models import Setting

DEFAULT_SETTINGS = {
    "business": {
        "name": "My Trucking Co.",
        "province": "AB",
        "gst_number": "",
        "fiscal_year_end": "12-31",
    },
    "shareholders": [
        {"name": "Shareholder 1", "pct": 50},
        {"name": "Shareholder 2", "pct": 50},
    ],
    "invoice": {"prefix": "INV-", "next_number": 1, "terms": "Net 30",
                "footer": "Thank you for your business."},
}


def get_setting(db: Session, key: str, default=None):
    row = db.get(Setting, key)
    if row is not None:
        return row.value
    return DEFAULT_SETTINGS.get(key, default)


def put_setting(db: Session, key: str, value) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value


def get_province(db: Session) -> str:
    return get_setting(db, "business", {}).get("province", "AB")


def rules_for_year(db: Session, year: int) -> dict:
    """CRA rule pack for a year, merged with any UI-saved overrides."""
    overrides = get_setting(db, f"cra_rules_{year}", {})
    return cra.get_rules(year, overrides or None)


def parse_period(start: str | None, end: str | None) -> tuple[date, date]:
    """Default period = current tax year (Jan-Dec)."""
    today = date.today()
    s = date.fromisoformat(start) if start else date(today.year, 1, 1)
    e = date.fromisoformat(end) if end else date(today.year, 12, 31)
    return s, e
