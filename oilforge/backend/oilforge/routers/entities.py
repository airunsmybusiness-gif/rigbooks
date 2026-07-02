"""CRUD routers for flat entities, with CRA math in before_save hooks."""
from datetime import date

from sqlalchemy.orm import Session

from ..cra import engine as cra
from ..helpers import get_province, rules_for_year
from ..models import (Client, Equipment, Expense, MaintenanceLog, Shareholder,
                      WellSite)
from .crud_factory import make_crud_router


def _expense_hook(db: Session, data: dict) -> None:
    d = data.get("date")
    year = d.year if isinstance(d, date) else date.today().year
    rules = rules_for_year(db, year)
    data["itc"] = cra.calc_itc(float(data.get("amount", 0) or 0),
                               data.get("category", ""), rules,
                               province=get_province(db))


expense_router = make_crud_router(
    Expense, "expenses",
    search_fields=("vendor", "description", "category", "receipt_ref"),
    before_save=_expense_hook)
client_router = make_crud_router(
    Client, "clients", date_field="", search_fields=("name", "contact", "email"))
site_router = make_crud_router(
    WellSite, "sites", date_field="", search_fields=("name", "lsd", "region"))
equipment_router = make_crud_router(
    Equipment, "equipment", date_field="",
    search_fields=("name", "serial", "description"))
maintenance_router = make_crud_router(
    MaintenanceLog, "maintenance",
    search_fields=("description", "vendor", "receipt_ref"))
shareholder_router = make_crud_router(
    Shareholder, "shareholders", date_field="", search_fields=("name", "email"))

ALL = [expense_router, client_router, site_router, equipment_router,
       maintenance_router, shareholder_router]
