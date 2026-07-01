"""CRUD routers for all flat entities, with CRA tax math applied in
before_save hooks so stored ITC/GST amounts always match the year's rules."""
from datetime import date

from sqlalchemy.orm import Session

from ..cra import engine as cra
from ..helpers import get_province, rules_for_year
from ..models import (Customer, Expense, FuelPurchase, MealEntry, PhoneBill,
                      RevenueEntry, Trip, Vehicle)
from .crud_factory import make_crud_router


def _year_of(data: dict) -> int:
    d = data.get("date")
    if isinstance(d, date):
        return d.year
    return date.today().year


def _expense_hook(db: Session, data: dict) -> None:
    rules = rules_for_year(db, _year_of(data))
    data["itc"] = cra.calc_itc(
        float(data.get("amount", 0) or 0), data.get("category", ""),
        rules, business_pct=float(data.get("business_pct", 100) or 100),
        province=get_province(db))


def _revenue_hook(db: Session, data: dict) -> None:
    rules = rules_for_year(db, _year_of(data))
    rate = cra.gst_rate(rules, get_province(db))
    amount = float(data.get("amount", 0) or 0)
    data["gst_amount"] = cra.extract_gst(amount, rate) if data.get("gst_included", True) else 0.0


def _fuel_hook(db: Session, data: dict) -> None:
    rules = rules_for_year(db, _year_of(data))
    # Rig fuel is 100% business use; ITC on the jurisdiction's GST/HST.
    juris = (data.get("jurisdiction") or "AB").upper()
    province = juris if juris in rules["gst_hst"]["rates"] else get_province(db)
    data["itc"] = cra.calc_itc(float(data.get("amount", 0) or 0),
                               "Fuel & Petroleum", rules, province=province)


def _trip_hook(db: Session, data: dict) -> None:
    start, end = data.get("odometer_start"), data.get("odometer_end")
    if not data.get("total_km") and start is not None and end is not None and end >= start:
        data["total_km"] = round(float(end) - float(start), 1)
    if not data.get("total_km"):
        data["total_km"] = float(data.get("business_km", 0) or 0)
    # Default all distance to a single jurisdiction when not broken out.
    if not data.get("jurisdiction_km"):
        data["jurisdiction_km"] = {get_province(db): float(data.get("total_km", 0) or 0)}


revenue_router = make_crud_router(
    RevenueEntry, "revenue", search_fields=("client", "job", "notes"),
    before_save=_revenue_hook)
expense_router = make_crud_router(
    Expense, "expenses", search_fields=("description", "vendor", "category", "paid_by"),
    before_save=_expense_hook)
fuel_router = make_crud_router(
    FuelPurchase, "fuel", search_fields=("vendor", "jurisdiction", "receipt_ref"),
    before_save=_fuel_hook)
trip_router = make_crud_router(
    Trip, "trips", search_fields=("origin", "destination", "purpose"),
    before_save=_trip_hook)
meal_router = make_crud_router(
    MealEntry, "meals", search_fields=("location", "notes"))
phone_router = make_crud_router(
    PhoneBill, "phone-bills", date_field="period_start",
    search_fields=("owner", "notes"))
customer_router = make_crud_router(
    Customer, "customers", date_field="", search_fields=("name", "email", "gst_number"))
vehicle_router = make_crud_router(
    Vehicle, "vehicles", date_field="", search_fields=("name", "make_model", "plate"))

ALL = [revenue_router, expense_router, fuel_router, trip_router, meal_router,
       phone_router, customer_router, vehicle_router]
