"""T2 preparation package: Schedule 1 (book-to-tax reconciliation),
Schedule 8 (CCA), Schedule 50 (shareholders), GIFI Schedule 125 income
statement, retained-earnings reconciliation, tax provision entry, and the
year-end closing snapshot.

These are working papers for the accountant, not filed forms.
"""
from datetime import date

from sqlalchemy.orm import Session

from .. import shareholder as sh
from ..cra import engine as cra
from ..helpers import get_province, get_setting, put_setting, rules_for_year
from ..models import DividendDeclaration, Shareholder
from . import statements


def schedule1(db: Session, start: date, end: date) -> dict:
    """Net income per books → net income for tax purposes."""
    summary = statements.collect(db, start, end)
    rules = rules_for_year(db, end.year)
    addback_cfg = rules.get("t2", {}).get("schedule1_addbacks", {})

    # Books here are pre-CCA (EBITDA); CCA is the tax-side deduction.
    net_per_books = summary["income"]["ebitda"]
    addbacks = []
    for category, nondeductible_pct in addback_cfg.items():
        spent = summary["expenses"]["by_category"].get(category, 0.0)
        if spent > 0:
            addbacks.append({
                "line": f"Non-deductible portion of {category}",
                "amount": round(spent * nondeductible_pct, 2),
            })
    total_addbacks = round(sum(a["amount"] for a in addbacks), 2)

    cca = summary["income"]["cca"]
    net_for_tax = round(net_per_books + total_addbacks - cca, 2)
    tax_est = cra.corporate_tax_estimate(net_for_tax, rules, get_province(db))
    return {
        "net_income_per_books": net_per_books,
        "addbacks": addbacks,
        "total_addbacks": total_addbacks,
        "deductions": [{"line": "CCA claimed (Schedule 8)", "amount": cca}],
        "net_income_for_tax": net_for_tax,
        "tax_estimate": tax_est,
    }


def schedule8(db: Session, year: int) -> dict:
    """CCA schedule in T2 S8 layout (already computed by the CCA engine)."""
    return statements.cca_for_year(db, year)


def schedule50(db: Session, year: int) -> list[dict]:
    """Shareholder information: holdings and dividends received."""
    out = []
    for holder in db.query(Shareholder).all():
        dividends = sh.dividends_by_kind(db, holder.id, year)
        out.append({
            "name": holder.name,
            "ownership_pct": holder.ownership_pct,
            "dividends_eligible": round(dividends.get("eligible", 0.0), 2),
            "dividends_non_eligible": round(dividends.get("non_eligible", 0.0), 2),
            "loan_balance_at_year_end": sh.balance(db, holder.id, date(year, 12, 31)),
        })
    return out


def schedule125_gifi(db: Session, start: date, end: date) -> dict:
    """GIFI-coded income statement for Schedule 125."""
    summary = statements.collect(db, start, end)
    rules = rules_for_year(db, end.year)
    gifi = rules.get("gifi", {"revenue": {}, "expenses": {}})
    lines = [{"gifi": gifi["revenue"].get("Revenue - Contract Services", "8000"),
              "description": "Revenue - Contract Services",
              "amount": summary["revenue"]["invoiced"]}]
    for cat, amt in summary["expenses"]["by_category"].items():
        lines.append({"gifi": gifi["expenses"].get(cat, "9270"),
                      "description": cat, "amount": amt})
    lines.append({"gifi": gifi["expenses"].get("CCA", "8670"),
                  "description": "Amortization (CCA claimed)",
                  "amount": summary["income"]["cca"]})
    net = round(summary["revenue"]["invoiced"]
                - summary["expenses"]["total"] - summary["income"]["cca"], 2)
    lines.append({"gifi": "9999", "description": "Net income (loss)", "amount": net})
    return {"lines": lines, "note": gifi.get("notes", "")}


def retained_earnings(db: Session, start: date, end: date) -> dict:
    """Opening RE + net income − dividends declared = closing RE.
    Opening RE comes from the prior year-end close (or a manual setting)."""
    s1 = schedule1(db, start, end)
    net_after_tax = round(s1["net_income_for_tax"]
                          - s1["tax_estimate"]["estimated_tax"], 2)
    opening = float(get_setting(db, f"opening_re_{end.year}", 0.0) or 0.0)
    dividends = round(sum(
        d.amount for d in db.query(DividendDeclaration)
        .filter(DividendDeclaration.date >= start,
                DividendDeclaration.date <= end)), 2)
    closing = round(opening + net_after_tax - dividends, 2)
    return {
        "opening_retained_earnings": opening,
        "net_income_after_tax_estimate": net_after_tax,
        "dividends_declared": dividends,
        "closing_retained_earnings": closing,
        "note": ("Opening RE is set by the prior year's close (or manually in "
                 "Settings as opening_re_<year>). Estimates use the tax "
                 "provision below - final figures come from the filed T2."),
    }


def provision_entry(s1: dict, end: date) -> dict:
    """Suggested year-end tax provision journal entry."""
    tax = s1["tax_estimate"]["estimated_tax"]
    return {
        "date": end.isoformat(),
        "memo": f"Income tax provision (estimate) for fiscal {end.year}",
        "debit_account": "Income Tax Expense",
        "credit_account": "Income Taxes Payable",
        "amount": tax,
    }


def year_end_package(db: Session, start: date, end: date) -> dict:
    s1 = schedule1(db, start, end)
    return {
        "fiscal_period": {"start": start.isoformat(), "end": end.isoformat()},
        "schedule1": s1,
        "schedule8": schedule8(db, end.year),
        "schedule50": schedule50(db, end.year),
        "schedule125_gifi": schedule125_gifi(db, start, end),
        "retained_earnings": retained_earnings(db, start, end),
        "provision_entry": provision_entry(s1, end),
        "closed": bool(get_setting(db, f"year_end_close_{end.year}", None)),
    }


def close_year(db: Session, start: date, end: date) -> dict:
    """Snapshot the year-end package and roll closing RE into next year's
    opening RE. Records stay editable — the snapshot is the audit anchor."""
    package = year_end_package(db, start, end)
    put_setting(db, f"year_end_close_{end.year}", {
        "closed_on": date.today().isoformat(),
        "snapshot": {
            "net_income_for_tax": package["schedule1"]["net_income_for_tax"],
            "tax_estimate": package["schedule1"]["tax_estimate"]["estimated_tax"],
            "closing_re": package["retained_earnings"]["closing_retained_earnings"],
            "total_cca": package["schedule8"]["total_cca"],
        },
    })
    put_setting(db, f"opening_re_{end.year + 1}",
                package["retained_earnings"]["closing_retained_earnings"])
    package["closed"] = True
    return package
