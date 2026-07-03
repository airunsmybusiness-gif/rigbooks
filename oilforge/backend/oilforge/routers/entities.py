"""CRUD routers for flat entities, with CRA math in before_save hooks."""
from datetime import date

from fastapi import Depends, UploadFile
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import User

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


@expense_router.get("/import-template")
def expense_template():
    """CSV template for historical-data import."""
    from fastapi.responses import Response
    body = ("Date,Vendor,Description,Amount,Category,Receipt\n"
            "2025-01-15,UFA Cardlock,Diesel for skid steer,184.50,Fuel & Petroleum,R-001\n"
            "2025-02-02,Hazmasters,FR coveralls,289.99,Safety Gear & PPE,R-002\n")
    return Response(body, media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="oilforge_expenses_template.csv"'})


@expense_router.post("/import")
async def import_expenses(file: UploadFile, db: Session = Depends(get_db),
                          user: User = Depends(current_user)):
    """Historical-data import: CSV with Date,Vendor,Description,Amount,
    Category[,Receipt]. ITCs are computed per the year's rules."""
    import csv as csvmod
    import io as iomod

    from ..audit import log

    content = (await file.read()).decode("utf-8", errors="replace")
    reader = csvmod.reader(iomod.StringIO(content))
    created = skipped = 0
    for row in reader:
        if len(row) < 5 or "date" in row[0].lower():
            continue
        try:
            data = {"date": date.fromisoformat(row[0].strip()),
                    "vendor": row[1].strip(), "description": row[2].strip(),
                    "amount": float(row[3].replace("$", "").replace(",", "")),
                    "category": row[4].strip(),
                    "receipt_ref": row[5].strip() if len(row) > 5 else ""}
        except (ValueError, IndexError):
            skipped += 1
            continue
        _expense_hook(db, data)
        db.add(Expense(**data))
        created += 1
    log(db, user.email, "import", "expenses", "",
        {"file": file.filename, "created": created, "skipped": skipped})
    db.commit()
    return {"created": created, "skipped": skipped}
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
