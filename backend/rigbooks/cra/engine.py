"""CRA compliance engine.

All tax math flows through this module so the rules stay in one place and
adapt per year. Rules come from JSON packs in cra/rules/<year>.json and can
be overridden per-year from the UI (overrides persist in the settings table
under key "cra_rules_<year>").

Adding a new tax year = drop in a new JSON file (or edit in the Tax Rules
page). If no pack exists for a year, the latest available pack is used and
flagged provisional so reports show the caveat.
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
    if path.exists():
        return json.loads(path.read_text())
    return None


def available_years() -> list[int]:
    return sorted(int(p.stem) for p in Path(RULES_DIR).glob("*.json") if p.stem.isdigit())


def get_rules(year: int, overrides: dict | None = None) -> dict:
    """Return the rule pack for a tax year, falling back to the nearest
    earlier year (marked provisional) when the exact year isn't published."""
    pack = _load_pack(year)
    if pack is None:
        years = available_years()
        if not years:
            raise RuntimeError("No CRA rule packs installed")
        fallback = max((y for y in years if y < year), default=years[-1])
        pack = dict(_load_pack(fallback))
        pack["year"] = year
        pack["provisional"] = True
        pack["source_notes"] = (
            f"No {year} pack published - using {fallback} rates. "
            "Add cra/rules/{year}.json or edit in Tax Rules."
        )
    if overrides:
        pack = _deep_merge(pack, overrides)
    return pack


# ---------------------------------------------------------------- GST / ITC

def gst_rate(rules: dict, province: str = "AB") -> float:
    return rules["gst_hst"]["rates"].get(province.upper(), 0.05)


def extract_gst(amount_incl_tax: float, rate: float) -> float:
    """GST/HST embedded in a tax-included amount."""
    return round(amount_incl_tax * rate / (1 + rate), 2)


def calc_itc(amount: float, category: str, rules: dict,
             business_pct: float = 100.0, province: str = "AB",
             tax_included: bool = True) -> float:
    """Input Tax Credit for an expense.

    ITC = business portion x embedded GST x category recoverability
    (e.g. meals recover only 50% of the GST; insurance is GST-exempt so 0%).
    """
    if amount <= 0:
        return 0.0
    cat_rate = rules["itc_category_rates"].get(category, 0.0)
    rate = gst_rate(rules, province)
    biz = amount * business_pct / 100.0
    gst = biz * rate / (1 + rate) if tax_included else biz * rate
    return round(gst * cat_rate, 2)


# ------------------------------------------------------------------ Mileage

def mileage_allowance(business_km: float, rules: dict, territories: bool = False) -> float:
    """CRA per-km automobile allowance (tiered: first 5,000 km higher rate).

    This is the tax-free allowance a corporation can pay a shareholder/
    employee for business use of a personal vehicle.
    """
    m = rules["mileage"]
    t1_limit = m["tier1_limit_km"]
    t1 = min(business_km, t1_limit) * m["tier1_rate"]
    t2 = max(business_km - t1_limit, 0) * m["tier2_rate"]
    supplement = business_km * m.get("territory_supplement_per_km", 0) if territories else 0
    return round(t1 + t2 + supplement, 2)


def business_use_pct(business_km: float, total_km: float) -> float:
    """Business-use percentage from the mileage log (actual-expense method)."""
    if total_km <= 0:
        return 0.0
    return round(min(business_km / total_km, 1.0) * 100, 1)


# -------------------------------------------------------------------- Meals

def meal_deduction(rules: dict, meals_count: int = 0, actual_amount: float = 0.0,
                   method: str = "simplified", long_haul: bool = True) -> dict:
    """Meal deduction under CRA simplified (flat rate/meal) or detailed
    (receipts) method. Long-haul truck drivers deduct 80%, others 50%."""
    m = rules["meals"]
    pct = m["long_haul_deductible_pct"] if long_haul else m["standard_deductible_pct"]
    if method == "simplified":
        gross = meals_count * m["simplified_rate_per_meal"]
    else:
        gross = actual_amount
    return {
        "gross": round(gross, 2),
        "deductible_pct": pct,
        "deductible": round(gross * pct, 2),
    }


# --------------------------------------------------------------------- IFTA

def ifta_quarter_report(trips_km_by_juris: dict[str, float],
                        fuel_by_juris: dict[str, float],
                        rules: dict) -> dict:
    """IFTA quarterly fuel-tax apportionment.

    fleet consumption = total km / total litres purchased
    taxable litres per jurisdiction = km in jurisdiction / fleet km-per-litre
    net tax = (taxable litres - tax-paid litres purchased there) x rate
    """
    rates = rules.get("ifta", {}).get("fuel_tax_rates_per_litre", {})
    total_km = sum(trips_km_by_juris.values())
    total_litres = sum(fuel_by_juris.values())
    kpl = (total_km / total_litres) if total_litres > 0 else 0.0

    lines = []
    net_total = 0.0
    for juris in sorted(set(trips_km_by_juris) | set(fuel_by_juris)):
        km = trips_km_by_juris.get(juris, 0.0)
        purchased = fuel_by_juris.get(juris, 0.0)
        taxable = (km / kpl) if kpl > 0 else 0.0
        rate = rates.get(juris, 0.0)
        net_tax = round((taxable - purchased) * rate, 2)
        net_total += net_tax
        lines.append({
            "jurisdiction": juris,
            "distance_km": round(km, 1),
            "fuel_purchased_l": round(purchased, 1),
            "taxable_litres": round(taxable, 1),
            "net_taxable_litres": round(taxable - purchased, 1),
            "tax_rate": rate,
            "net_tax": net_tax,
        })
    return {
        "total_km": round(total_km, 1),
        "total_litres": round(total_litres, 1),
        "fleet_kpl": round(kpl, 3),
        "lines": lines,
        "net_tax_due": round(net_total, 2),
    }


# ---------------------------------------------------------------------- T4A

def t4a_candidates(payments_by_vendor: dict[str, float], rules: dict) -> list[dict]:
    """Vendors paid fees for services above the T4A reporting threshold
    (box 048). Applies to unincorporated contractors and CCPCs alike."""
    threshold = rules["t4a"]["fee_reporting_threshold"]
    return [
        {"vendor": v, "total_fees": round(t, 2), "box": rules["t4a"]["box"]}
        for v, t in sorted(payments_by_vendor.items(), key=lambda x: -x[1])
        if t > threshold and v.strip()
    ]


# ------------------------------------------------------------------ GST34

def gst_return(revenue_incl_gst: float, gst_collected: float,
               total_itcs: float) -> dict:
    """Form GST34 working copy numbers."""
    net = round(gst_collected - total_itcs, 2)
    return {
        "line_101_sales": round(revenue_incl_gst, 2),
        "line_105_gst_collected": round(gst_collected, 2),
        "line_108_itcs": round(total_itcs, 2),
        "line_109_net_tax": net,
        "owing": net > 0,
    }
