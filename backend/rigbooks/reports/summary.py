"""Financial aggregation for dashboards and CRA reports.

One collection pass produces everything: P&L, GST34 numbers, ITC breakdown
by source, mileage/business-use stats and profit-per-km. All tax figures go
through the CRA engine with the rules for the period's tax year.
"""
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from ..cra import engine as cra
from ..helpers import get_province, rules_for_year
from ..models import (BankTransaction, Expense, FuelPurchase, HomeOffice,
                      MealEntry, PhoneBill, RevenueEntry, Trip)

REVENUE_CATEGORY = "Revenue - Oilfield Services"


def collect(db: Session, start: date, end: date) -> dict:
    year = start.year
    rules = rules_for_year(db, year)
    province = get_province(db)
    rate = cra.gst_rate(rules, province)

    # ---- Revenue -------------------------------------------------------
    revenue_rows = (db.query(RevenueEntry)
                    .filter(RevenueEntry.date >= start, RevenueEntry.date <= end).all())
    manual_revenue = sum(r.amount for r in revenue_rows)
    manual_gst = sum(r.gst_amount for r in revenue_rows)

    bank_rows = (db.query(BankTransaction)
                 .filter(BankTransaction.date >= start, BankTransaction.date <= end).all())
    bank_revenue = sum(t.credit for t in bank_rows if t.category == REVENUE_CATEGORY)
    bank_gst = cra.extract_gst(bank_revenue, rate)

    total_revenue = manual_revenue + bank_revenue
    gst_collected = manual_gst + bank_gst

    # ---- Expenses & ITCs ------------------------------------------------
    itc_by_source: dict[str, float] = defaultdict(float)
    expense_by_category: dict[str, float] = defaultdict(float)

    bank_expenses = sum(t.debit for t in bank_rows if t.status == "business")
    for t in bank_rows:
        if t.status == "business" and t.debit > 0:
            expense_by_category[t.category] += t.debit
    itc_by_source["Bank statement"] = sum(t.itc for t in bank_rows)

    expense_rows = (db.query(Expense)
                    .filter(Expense.date >= start, Expense.date <= end).all())
    source_labels = {"cash": "Cash expenses", "personal": "Personal account",
                     "other": "Other expenses", "vehicle": "Vehicle"}
    expense_totals = defaultdict(float)
    for e in expense_rows:
        deductible = e.amount * e.business_pct / 100
        expense_totals[e.source] += deductible
        expense_by_category[e.category] += deductible
        itc_by_source[source_labels.get(e.source, e.source)] += e.itc

    fuel_rows = (db.query(FuelPurchase)
                 .filter(FuelPurchase.date >= start, FuelPurchase.date <= end).all())
    fuel_total = sum(f.amount for f in fuel_rows)
    fuel_litres = sum(f.litres for f in fuel_rows)
    if fuel_total:
        expense_by_category["Fuel & Petroleum"] += fuel_total
        itc_by_source["Fuel purchases"] = sum(f.itc for f in fuel_rows)

    phone_rows = (db.query(PhoneBill)
                  .filter(PhoneBill.period_start >= start,
                          PhoneBill.period_start <= end).all())
    phone_deductible = sum(p.amount * p.business_pct / 100 for p in phone_rows)
    if phone_deductible:
        expense_by_category["Phone & Communications"] += phone_deductible
        itc_by_source["Phone bills"] = sum(
            cra.calc_itc(p.amount, "Phone & Communications", rules,
                         business_pct=p.business_pct, province=province)
            for p in phone_rows)

    ho = db.query(HomeOffice).filter_by(year=year).first()
    ho_deductible = ho_itc = 0.0
    if ho:
        gross = (ho.rent + ho.property_tax + ho.insurance + ho.electricity +
                 ho.gas + ho.water + ho.internet)
        ho_deductible = round(gross * ho.pct / 100, 2)
        gst_bearing = (ho.rent + ho.electricity + ho.gas + ho.water + ho.internet)
        ho_itc = cra.extract_gst(gst_bearing * ho.pct / 100, rate)
        if ho_deductible:
            expense_by_category["Home Office"] += ho_deductible
            itc_by_source["Home office"] = ho_itc

    # ---- Meals (per diem) ----------------------------------------------
    meal_rows = (db.query(MealEntry)
                 .filter(MealEntry.date >= start, MealEntry.date <= end).all())
    meal_deductible = 0.0
    meal_itc = 0.0
    for m in meal_rows:
        d = cra.meal_deduction(rules, meals_count=m.meals_count,
                               actual_amount=m.amount, method=m.method,
                               long_haul=m.long_haul)
        meal_deductible += d["deductible"]
        # ITCs require receipts, so only the detailed method claims GST back.
        if m.method == "detailed":
            meal_itc += cra.extract_gst(m.amount, rate) * d["deductible_pct"]
    meal_deductible = round(meal_deductible, 2)
    if meal_deductible:
        expense_by_category["Meals & Per Diem"] += meal_deductible
        itc_by_source["Meals (detailed)"] = round(meal_itc, 2)

    # ---- Mileage / trips -------------------------------------------------
    trips = db.query(Trip).filter(Trip.date >= start, Trip.date <= end).all()
    business_km = sum(t.business_km for t in trips)
    total_km = sum(t.total_km for t in trips)
    trip_revenue = sum(t.revenue_amount for t in trips)

    # ---- Totals ----------------------------------------------------------
    total_expenses = round(
        bank_expenses + sum(expense_totals.values()) + fuel_total +
        phone_deductible + ho_deductible + meal_deductible, 2)
    total_itcs = round(sum(itc_by_source.values()), 2)
    net_income = round(total_revenue - total_expenses, 2)

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat(), "year": year},
        "rules_year": rules["year"],
        "rules_provisional": rules.get("provisional", False),
        "province": province,
        "gst_rate": rate,
        "revenue": {
            "manual": round(manual_revenue, 2),
            "bank": round(bank_revenue, 2),
            "invoiced_trips": round(trip_revenue, 2),
            "total": round(total_revenue, 2),
            "gst_collected": round(gst_collected, 2),
        },
        "expenses": {
            "bank": round(bank_expenses, 2),
            "cash": round(expense_totals["cash"], 2),
            "personal": round(expense_totals["personal"], 2),
            "other": round(expense_totals["other"], 2),
            "vehicle": round(expense_totals["vehicle"], 2),
            "fuel": round(fuel_total, 2),
            "phone": round(phone_deductible, 2),
            "home_office": ho_deductible,
            "meals": meal_deductible,
            "total": total_expenses,
            "by_category": {k: round(v, 2) for k, v in
                            sorted(expense_by_category.items(), key=lambda x: -x[1])},
        },
        "itcs": {
            "by_source": {k: round(v, 2) for k, v in
                          sorted(itc_by_source.items(), key=lambda x: -x[1]) if v > 0},
            "total": total_itcs,
        },
        "gst34": cra.gst_return(total_revenue, gst_collected, total_itcs),
        "mileage": {
            "business_km": round(business_km, 1),
            "total_km": round(total_km, 1),
            "business_pct": cra.business_use_pct(business_km, total_km),
            "cra_allowance": cra.mileage_allowance(business_km, rules),
            "fuel_litres": round(fuel_litres, 1),
        },
        "kpis": {
            "net_income": net_income,
            "profit_per_km": round(net_income / business_km, 2) if business_km else 0.0,
            "revenue_per_km": round(total_revenue / business_km, 2) if business_km else 0.0,
            "cost_per_km": round(total_expenses / business_km, 2) if business_km else 0.0,
        },
    }


def monthly_series(db: Session, year: int) -> list[dict]:
    """Month-by-month revenue/expenses/net for dashboard charts.

    Only date-stamped records are bucketed by month; annual items
    (home office) are excluded so months aren't inflated.
    """
    months = [{"month": date(year, m, 1).strftime("%b"), "revenue": 0.0,
               "expenses": 0.0, "business_km": 0.0} for m in range(1, 13)]

    def bucket(d: date):
        return months[d.month - 1] if d.year == year else None

    for r in db.query(RevenueEntry).filter(
            RevenueEntry.date >= date(year, 1, 1), RevenueEntry.date <= date(year, 12, 31)):
        b = bucket(r.date)
        if b:
            b["revenue"] += r.amount
    for t in db.query(BankTransaction).filter(
            BankTransaction.date >= date(year, 1, 1), BankTransaction.date <= date(year, 12, 31)):
        b = bucket(t.date)
        if not b:
            continue
        if t.category == REVENUE_CATEGORY:
            b["revenue"] += t.credit
        elif t.status == "business":
            b["expenses"] += t.debit
    for e in db.query(Expense).filter(
            Expense.date >= date(year, 1, 1), Expense.date <= date(year, 12, 31)):
        b = bucket(e.date)
        if b:
            b["expenses"] += e.amount * e.business_pct / 100
    for f in db.query(FuelPurchase).filter(
            FuelPurchase.date >= date(year, 1, 1), FuelPurchase.date <= date(year, 12, 31)):
        b = bucket(f.date)
        if b:
            b["expenses"] += f.amount
    for t in db.query(Trip).filter(
            Trip.date >= date(year, 1, 1), Trip.date <= date(year, 12, 31)):
        b = bucket(t.date)
        if b:
            b["business_km"] += t.business_km

    for m in months:
        m["revenue"] = round(m["revenue"], 2)
        m["expenses"] = round(m["expenses"], 2)
        m["net"] = round(m["revenue"] - m["expenses"], 2)
        m["business_km"] = round(m["business_km"], 1)
        m["profit_per_km"] = round(m["net"] / m["business_km"], 2) if m["business_km"] else 0.0
    return months
