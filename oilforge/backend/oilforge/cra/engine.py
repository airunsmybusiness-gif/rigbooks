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

    Per-year, per-class (T2 Schedule 8 logic):
      additions      = cost of assets acquired that year
      dispositions   = min(cost, proceeds) per asset disposed that year
      UCC after adj. = opening + additions - dispositions
        < 0                        -> RECAPTURE (income), UCC resets to 0
        > 0 and class now empty    -> TERMINAL LOSS (deduction), UCC to 0
        otherwise:
          CCA base   = UCC-after + (first_year_multiplier - 1) x net additions
                       (1.5 = AIIP bonus; 0.5 = plain half-year rule)
          CCA        = rate x base x claim%  (claiming CCA is optional)
          closing    = UCC-after - CCA
    """
    classes: dict[str, list[dict]] = {}
    for a in assets:
        classes.setdefault(str(a["cca_class"]), []).append(a)

    result = {"year": target_year, "classes": [], "total_cca": 0.0,
              "total_ucc_closing": 0.0, "total_recapture": 0.0,
              "total_terminal_loss": 0.0}
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
            ucc_after = ucc + additions - dispositions
            class_empty = all(
                a.get("disposed_year") is not None and a["disposed_year"] <= year
                for a in items if a["acquired_year"] <= year
            ) and any(a["acquired_year"] <= year for a in items)
            recapture = terminal_loss = cca = 0.0
            if ucc_after < -0.005:
                recapture = round(-ucc_after, 2)
                closing = 0.0
            elif class_empty and ucc_after > 0.005:
                terminal_loss = round(ucc_after, 2)
                closing = 0.0
            else:
                net_additions = max(additions - dispositions, 0.0)
                base = max(ucc_after + (mult - 1) * net_additions, 0.0)
                cca = round(base * rate * claim_pct / 100, 2)
                closing = round(ucc_after - cca, 2)
            row = {"class": cls, "rate": rate,
                   "description": cls_info.get("description", ""),
                   "ucc_opening": round(ucc, 2),
                   "additions": round(additions, 2),
                   "dispositions": round(dispositions, 2),
                   "cca": cca, "recapture": recapture,
                   "terminal_loss": terminal_loss, "ucc_closing": closing}
            ucc = closing
        if row:
            result["classes"].append(row)
            result["total_cca"] += row["cca"]
            result["total_recapture"] += row["recapture"]
            result["total_terminal_loss"] += row["terminal_loss"]
            result["total_ucc_closing"] += row["ucc_closing"]
    for k in ("total_cca", "total_ucc_closing", "total_recapture",
              "total_terminal_loss"):
        result[k] = round(result[k], 2)
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


# ------------------------------------------------------ personal tax bridge

def _progressive_tax(income: float, brackets: list) -> float:
    """Tax on `income` under [[threshold, rate], ...] brackets."""
    tax = 0.0
    for i, (lo, rate) in enumerate(brackets):
        hi = brackets[i + 1][0] if i + 1 < len(brackets) else float("inf")
        if income <= lo:
            break
        tax += (min(income, hi) - lo) * rate
    return tax


def personal_dividend_tax(actual_by_kind: dict[str, float], rules: dict,
                          province: str = "AB",
                          other_income: float = 0.0) -> dict:
    """Estimated personal tax if this year's dividends are the shareholder's
    income (plus optional other income). Uses gross-up, progressive federal +
    provincial brackets, basic personal amounts and both levels of DTC.
    A planning estimate — not a T1."""
    pt = rules["personal_tax"]
    prov = province.upper() if province.upper() in pt["provincial_brackets"] else "AB"

    taxable = other_income
    dtc_fed = dtc_prov = 0.0
    for kind in ("non_eligible", "eligible"):
        actual = actual_by_kind.get(kind, 0.0)
        grossed = actual * (1 + rules["dividends"][kind]["gross_up"])
        taxable += grossed
        dtc_fed += grossed * pt["dtc_of_taxable"]["federal"][kind]
        dtc_prov += grossed * pt["dtc_of_taxable"].get(prov, {}).get(kind, 0.0)

    fed_brackets = pt["federal_brackets"]
    prov_brackets = pt["provincial_brackets"][prov]
    fed_gross = _progressive_tax(taxable, fed_brackets)
    prov_gross = _progressive_tax(taxable, prov_brackets)
    # Basic personal amount credits at the lowest rate of each schedule.
    fed_bpa_credit = pt["federal_basic_personal_amount"] * fed_brackets[0][1]
    prov_bpa_credit = (pt["provincial_basic_personal_amount"].get(prov, 0.0)
                       * prov_brackets[0][1])
    fed_tax = max(fed_gross - fed_bpa_credit - dtc_fed, 0.0)
    prov_tax = max(prov_gross - prov_bpa_credit - dtc_prov, 0.0)
    total_actual = sum(actual_by_kind.values()) + other_income

    warnings = []
    if actual_by_kind.get("eligible", 0.0) > 0 and taxable > pt["amt_exemption"]:
        warnings.append(
            "Large eligible dividends above the AMT exemption "
            f"(${pt['amt_exemption']:,.0f} taxable) can trigger Alternative "
            "Minimum Tax — have the accountant run the AMT calculation.")
    if total_actual > 0 and taxable > fed_brackets[-1][0]:
        warnings.append("Income reaches the top federal bracket — consider "
                        "splitting declarations across calendar years.")

    return {
        "province": prov,
        "taxable_income": round(taxable, 2),
        "federal_tax": round(fed_tax, 2),
        "provincial_tax": round(prov_tax, 2),
        "total_tax": round(fed_tax + prov_tax, 2),
        "cash_received": round(sum(actual_by_kind.values()), 2),
        "average_rate_on_cash": round(
            (fed_tax + prov_tax) / sum(actual_by_kind.values()) * 100, 1)
        if sum(actual_by_kind.values()) else 0.0,
        "warnings": warnings,
        "notes": pt["notes"],
    }


# --------------------------------------------------------------- Schedule 1

def schedule1(book_income: float, expense_by_category: dict[str, float],
              cca_claimed: float, recapture: float, terminal_loss: float,
              rules: dict) -> dict:
    """T2 Schedule 1 working paper: book income -> income for tax purposes."""
    cfg = rules.get("schedule1", {"addback_categories": {}, "non_deductible_categories": []})
    lines = [{"line": "Net income (loss) per financial statements",
              "amount": round(book_income, 2)}]
    total = book_income
    for cat, pct in cfg["addback_categories"].items():
        spent = expense_by_category.get(cat, 0.0)
        if spent > 0:
            addback = round(spent * pct, 2)
            lines.append({"line": f"Add: non-deductible {int(pct * 100)}% of {cat}",
                          "amount": addback})
            total += addback
    for cat in cfg["non_deductible_categories"]:
        spent = expense_by_category.get(cat, 0.0)
        if spent > 0:
            lines.append({"line": f"Add: non-deductible {cat}", "amount": round(spent, 2)})
            total += spent
    if recapture > 0:
        lines.append({"line": "Add: recapture of CCA (Schedule 8)",
                      "amount": round(recapture, 2)})
        total += recapture
    if cca_claimed > 0:
        lines.append({"line": "Deduct: CCA claimed (Schedule 8)",
                      "amount": round(-cca_claimed, 2)})
        total -= cca_claimed
    if terminal_loss > 0:
        lines.append({"line": "Deduct: terminal loss (Schedule 8)",
                      "amount": round(-terminal_loss, 2)})
        total -= terminal_loss
    lines.append({"line": "Net income for tax purposes", "amount": round(total, 2)})
    return {"lines": lines, "net_income_for_tax": round(total, 2),
            "notes": cfg.get("notes", "")}
