"""OilForge CRA compliance engine (corporate / T2 focus).

Every tax-sensitive number flows through here, driven by per-year JSON rule
packs in cra/rules/<year>.json. UI edits persist as overrides in settings;
a missing year falls back to the newest earlier pack, flagged provisional.

Covers: GST/HST + ITCs, CCA/UCC schedules (with AIIP first-year factor),
dividend gross-up & dividend tax credit (T5 boxes), shareholder-loan
ITA 15(2)/80.4 parameters, and small-business corporate tax estimates.
"""
import json
from functools import lru_cache
from pathlib import Path

from ..config import RULES_DIR


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@lru_cache(maxsize=32)
def _load_pack(year: int) -> dict | None:
    path = Path(RULES_DIR) / f"{year}.json"
    return json.loads(path.read_text()) if path.exists() else None


def available_years() -> list[int]:
    return sorted(int(p.stem) for p in Path(RULES_DIR).glob("*.json") if p.stem.isdigit())


def get_rules(year: int, overrides: dict | None = None) -> dict:
    pack = _load_pack(year)
    if pack is None:
        years = available_years()
        if not years:
            raise RuntimeError("No CRA rule packs installed")
        fallback = max((y for y in years if y < year), default=years[-1])
        pack = dict(_load_pack(fallback))
        pack["year"] = year
        pack["provisional"] = True
        pack["source_notes"] = (f"No {year} pack published - using {fallback} "
                                "figures. Add a new pack or edit in Tax Rules.")
    if overrides:
        pack = _deep_merge(pack, overrides)
    return pack


# ---------------------------------------------------------------- GST / ITC

def gst_rate(rules: dict, province: str = "AB") -> float:
    return rules["gst_hst"]["rates"].get(province.upper(), 0.05)


def extract_gst(amount_incl_tax: float, rate: float) -> float:
    return round(amount_incl_tax * rate / (1 + rate), 2)


def calc_itc(amount: float, category: str, rules: dict,
             province: str = "AB", tax_included: bool = True) -> float:
    """Input tax credit on a corporate expense (tax-included by default)."""
    if amount <= 0:
        return 0.0
    cat_rate = rules["itc_category_rates"].get(category, 0.0)
    rate = gst_rate(rules, province)
    gst = amount * rate / (1 + rate) if tax_included else amount * rate
    return round(gst * cat_rate, 2)


def gst_return(revenue: float, gst_collected: float, itcs: float) -> dict:
    net = round(gst_collected - itcs, 2)
    return {"line_101_sales": round(revenue, 2),
            "line_105_gst_collected": round(gst_collected, 2),
            "line_108_itcs": round(itcs, 2),
            "line_109_net_tax": net, "owing": net > 0}


# --------------------------------------------------------------------- CCA

def cca_schedule(assets: list[dict], target_year: int,
                 rules_for_year, claim_pct: float = 100.0) -> dict:
    """Simulate UCC per CCA class from first acquisition to target_year.

    assets: [{cca_class, cost, acquired_year, disposed_year?, proceeds?}]
    rules_for_year: callable(year) -> rule pack (so each simulated year uses
    its own rates/first-year factor).

    Per-year, per-class:
      additions     = cost of assets acquired that year
      dispositions  = min(cost, proceeds) for assets disposed that year
      CCA base      = opening - dispositions + first_year_multiplier x additions
      CCA           = rate x base x claim%   (claiming CCA is optional)
      closing UCC   = opening + additions - dispositions - CCA
    """
    classes: dict[str, list[dict]] = {}
    for a in assets:
        classes.setdefault(str(a["cca_class"]), []).append(a)

    result = {"year": target_year, "classes": [], "total_cca": 0.0,
              "total_ucc_closing": 0.0}
    for cls, items in sorted(classes.items()):
        first_year = min(a["acquired_year"] for a in items)
        ucc = 0.0
        row = None
        for year in range(first_year, target_year + 1):
            rules = rules_for_year(year)
            cls_info = rules["cca"]["classes"].get(cls, {"rate": 0.0})
            rate = cls_info["rate"]
            mult = rules["cca"].get("first_year_multiplier", 0.5)
            additions = sum(a["cost"] for a in items if a["acquired_year"] == year)
            dispositions = sum(min(a["cost"], a.get("proceeds", 0.0))
                               for a in items
                               if a.get("disposed_year") == year)
            base = max(ucc - dispositions + mult * additions, 0.0)
            cca = round(base * rate * claim_pct / 100, 2)
            closing = round(ucc + additions - dispositions - cca, 2)
            if closing < 0:  # recapture situation — flag, don't go negative
                cca = round(cca + closing, 2)
                closing = 0.0
            row = {"class": cls, "rate": rate,
                   "description": cls_info.get("description", ""),
                   "ucc_opening": round(ucc, 2),
                   "additions": round(additions, 2),
                   "dispositions": round(dispositions, 2),
                   "cca": cca, "ucc_closing": closing}
            ucc = closing
        if row:
            result["classes"].append(row)
            result["total_cca"] += row["cca"]
            result["total_ucc_closing"] += row["ucc_closing"]
    result["total_cca"] = round(result["total_cca"], 2)
    result["total_ucc_closing"] = round(result["total_ucc_closing"], 2)
    return result


# ---------------------------------------------------------------- dividends

def dividend_t5(actual_by_kind: dict[str, float], rules: dict) -> dict:
    """T5 slip figures from actual dividends paid in a calendar year.
    taxable = actual x (1 + gross-up); DTC = taxable x federal DTC rate."""
    out = {"kinds": {}, "boxes": {}}
    for kind in ("non_eligible", "eligible"):
        actual = round(actual_by_kind.get(kind, 0.0), 2)
        cfg = rules["dividends"][kind]
        taxable = round(actual * (1 + cfg["gross_up"]), 2)
        dtc = round(taxable * cfg["federal_dtc_of_taxable"], 2)
        out["kinds"][kind] = {"actual": actual, "taxable": taxable, "dtc": dtc}
        boxes = rules["t5"]["boxes"][kind]
        out["boxes"][boxes["actual"]] = actual
        out["boxes"][boxes["taxable"]] = taxable
        out["boxes"][boxes["dtc"]] = dtc
    out["filing_deadline"] = rules["t5"]["filing_deadline"]
    return out


# ---------------------------------------------------------- shareholder loan

# Effect of each transaction type on the shareholder's debt to the corp.
LOAN_SIGNS = {
    "withdrawal": +1,
    "personal_expense": +1,
    "contribution": -1,
    "corp_expense_paid_personally": -1,
    "loan_repayment": -1,
    "dividend_applied": -1,
}


def loan_direction(txn_type: str) -> int:
    return LOAN_SIGNS.get(txn_type, 0)


def shareholder_loan_assessment(balance: float, fiscal_year_end: str,
                                rules: dict) -> dict:
    """ITA 15(2) exposure: a positive (owing-to-corp) balance must be repaid
    within `months` after the fiscal year-end or it becomes income."""
    cfg = rules["shareholder_loan"]
    months = cfg["ita_15_2_repayment_months_after_year_end"]
    prescribed = cfg["prescribed_rate"]
    return {
        "balance": round(balance, 2),
        "owing_to_corp": balance > 0.005,
        "repayment_deadline_note": (
            f"Repay or clear (e.g. declare a dividend) within {months} months "
            f"after the {fiscal_year_end} year-end or ITA 15(2) includes it "
            "in personal income." if balance > 0.005 else
            "No shareholder debit balance - no ITA 15(2) exposure."),
        "prescribed_rate": prescribed,
        "annual_imputed_interest_80_4": round(max(balance, 0.0) * prescribed, 2),
    }


# ------------------------------------------------------------ corporate tax

def corporate_tax_estimate(active_business_income: float, rules: dict,
                           province: str = "AB") -> dict:
    """Small-business T2 estimate (SBD on the first $500k, general above)."""
    ct = rules["corporate_tax"]
    prov = ct["provincial_rates"].get(province.upper(),
                                      {"small": 0.02, "general": 0.08})
    income = max(active_business_income, 0.0)
    sbd_part = min(income, ct["small_business_limit"])
    general_part = max(income - ct["small_business_limit"], 0.0)
    small_rate = ct["federal_small_business_rate"] + prov["small"]
    general_rate = ct["federal_general_rate"] + prov["general"]
    tax = round(sbd_part * small_rate + general_part * general_rate, 2)
    return {
        "active_business_income": round(income, 2),
        "small_business_rate": small_rate,
        "general_rate": general_rate,
        "estimated_tax": tax,
        "after_tax": round(income - tax, 2),
        "note": ct["notes"],
    }
