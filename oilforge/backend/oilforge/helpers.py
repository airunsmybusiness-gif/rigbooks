"""Shared helpers: settings, fiscal periods, rules lookup."""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from .cra import engine as cra
from .models import Setting

DEFAULT_SETTINGS = {
    "business": {
        "name": "My Oilfield Services Ltd.",
        "province": "AB",
        "gst_number": "",
        "bn": "",
        "fiscal_year_end": "12-31",   # MM-DD
    },
    "invoice": {"prefix": "OF-", "next_number": 1, "terms": "Net 30",
                "footer": "Thank you for your business."},
    "job": {"prefix": "WO-", "next_number": 1},
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


def fiscal_year_end(db: Session, year: int) -> date:
    mmdd = get_setting(db, "business", {}).get("fiscal_year_end", "12-31")
    month, day = (int(x) for x in mmdd.split("-"))
    return date(year, month, day)


def fiscal_period(db: Session, year: int) -> tuple[date, date]:
    """Fiscal year *ending* in `year` (calendar year when FYE is 12-31)."""
    end = fiscal_year_end(db, year)
    start = date(end.year - 1, end.month, end.day) + timedelta(days=1)
    return start, end


def rules_for_year(db: Session, year: int) -> dict:
    overrides = get_setting(db, f"cra_rules_{year}", {})
    return cra.get_rules(year, overrides or None)


def parse_period(db: Session, start: str | None, end: str | None) -> tuple[date, date]:
    """Default reporting period = fiscal year containing today."""
    if start and end:
        return date.fromisoformat(start), date.fromisoformat(end)
    today = date.today()
    fs, fe = fiscal_period(db, today.year)
    if today > fe:
        fs, fe = fiscal_period(db, today.year + 1)
    if start:
        fs = date.fromisoformat(start)
    if end:
        fe = date.fromisoformat(end)
    return fs, fe
