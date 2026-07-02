"""Personal Tax Bridge engine — T1 *preview* math.

Estimates the owner's personal tax from corporate dividends plus manually
entered personal income/deductions: bracket tax (federal + province),
basic personal amounts, dividend gross-up and tax credits, the ITA 80.4
imputed-interest benefit, and a simplified 2024+ AMT check.

Deliberately simplified (no CPP/EI, OAS clawback, or credit phase-outs) —
the point is a directional preview and a clean handoff package; the
accountant files the real T1.
"""


def bracket_tax(taxable: float, brackets: list) -> float:
    """Progressive tax over [[upper_limit, rate], …, [None, top_rate]]."""
    tax = 0.0
    lower = 0.0
    for upper, rate in brackets:
        if upper is None or taxable <= upper:
            tax += max(taxable - lower, 0.0) * rate
            break
        tax += (upper - lower) * rate
        lower = upper
    return round(max(tax, 0.0), 2)


def marginal_rate(taxable: float, brackets: list) -> float:
    for upper, rate in brackets:
        if upper is None or taxable <= upper:
            return rate
    return brackets[-1][1]


def t1_preview(rules: dict, province: str, dividends: dict[str, float],
               inputs: dict, shareholder_loan_balance: float = 0.0) -> dict:
    """Estimate the owner's T1 for a calendar year.

    dividends: {"eligible": actual, "non_eligible": actual}
    inputs: {employment_income, other_income, interest_income,
             rrsp_deduction, other_deductions}
    """
    pt = rules["personal_tax"]
    prov = pt["provincial"].get(province.upper()) or next(iter(pt["provincial"].values()))
    div_cfg = rules["dividends"]
    loan_cfg = rules["shareholder_loan"]

    employment = float(inputs.get("employment_income", 0) or 0)
    other = float(inputs.get("other_income", 0) or 0)
    interest = float(inputs.get("interest_income", 0) or 0)
    rrsp = float(inputs.get("rrsp_deduction", 0) or 0)
    other_ded = float(inputs.get("other_deductions", 0) or 0)

    actual_elig = round(dividends.get("eligible", 0.0), 2)
    actual_non = round(dividends.get("non_eligible", 0.0), 2)
    taxable_elig = round(actual_elig * (1 + div_cfg["eligible"]["gross_up"]), 2)
    taxable_non = round(actual_non * (1 + div_cfg["non_eligible"]["gross_up"]), 2)

    # ITA 80.4: outstanding shareholder loan creates an imputed-interest benefit.
    imputed = round(max(shareholder_loan_balance, 0.0) * loan_cfg["prescribed_rate"], 2)

    total_income = round(employment + other + interest + taxable_elig
                         + taxable_non + imputed, 2)
    deductions = round(rrsp + other_ded, 2)
    taxable_income = round(max(total_income - deductions, 0.0), 2)

    # Federal
    fed_gross = bracket_tax(taxable_income, pt["federal_brackets"])
    fed_low = pt["federal_brackets"][0][1]
    fed_bpa_credit = round(pt["federal_bpa"] * fed_low, 2)
    fed_dtc = round(taxable_elig * div_cfg["eligible"]["federal_dtc_of_taxable"]
                    + taxable_non * div_cfg["non_eligible"]["federal_dtc_of_taxable"], 2)
    fed_tax = round(max(fed_gross - fed_bpa_credit - fed_dtc, 0.0), 2)

    # Provincial
    prov_gross = bracket_tax(taxable_income, prov["brackets"])
    prov_low = prov["brackets"][0][1]
    prov_bpa_credit = round(prov["bpa"] * prov_low, 2)
    prov_dtc = round(taxable_elig * prov["dtc_of_taxable"]["eligible"]
                     + taxable_non * prov["dtc_of_taxable"]["non_eligible"], 2)
    prov_tax = round(max(prov_gross - prov_bpa_credit - prov_dtc, 0.0), 2)

    regular_tax = round(fed_tax + prov_tax, 2)

    # ---- Simplified AMT (2024+ rules) ----------------------------------
    amt_cfg = pt["amt"]
    # AMT base: dividends at ACTUAL amounts (gross-up excluded), no DTC.
    amt_income = round(employment + other + interest + actual_elig
                       + actual_non + imputed - deductions, 2)
    amt_base = max(amt_income - amt_cfg["exemption"], 0.0)
    amt_gross = amt_base * amt_cfg["rate"]
    amt_credits = fed_bpa_credit * amt_cfg["credit_allowance"]
    amt_tax = round(max(amt_gross - amt_credits, 0.0), 2)
    amt_applies = amt_tax > fed_tax

    total_tax = round((amt_tax if amt_applies else fed_tax) + prov_tax, 2)
    cash_received = round(actual_elig + actual_non + employment + other + interest, 2)

    return {
        "income": {
            "employment": employment, "other": other, "interest": interest,
            "dividends_actual": {"eligible": actual_elig, "non_eligible": actual_non},
            "dividends_taxable": {"eligible": taxable_elig, "non_eligible": taxable_non},
            "gross_up_added": round(taxable_elig - actual_elig
                                    + taxable_non - actual_non, 2),
            "imputed_interest_80_4": imputed,
            "total_income": total_income,
            "deductions": deductions,
            "taxable_income": taxable_income,
        },
        "federal": {"gross": fed_gross, "bpa_credit": fed_bpa_credit,
                    "dividend_tax_credit": fed_dtc, "net": fed_tax},
        "provincial": {"code": province.upper(), "gross": prov_gross,
                       "bpa_credit": prov_bpa_credit,
                       "dividend_tax_credit": prov_dtc, "net": prov_tax},
        "amt": {"adjusted_income": amt_income, "exemption": amt_cfg["exemption"],
                "amt_tax": amt_tax, "applies": amt_applies,
                "notes": amt_cfg["notes"]},
        "totals": {
            "regular_tax": regular_tax,
            "total_tax": total_tax,
            "average_rate": round(total_tax / taxable_income, 4) if taxable_income else 0.0,
            "marginal_rate": round(
                marginal_rate(taxable_income, pt["federal_brackets"])
                + marginal_rate(taxable_income, prov["brackets"]), 4),
            "cash_received": cash_received,
            "after_tax_cash": round(cash_received - total_tax, 2),
        },
        "notes": pt["notes"],
    }


def integrated_summary(corp: dict, personal: dict) -> dict:
    """Corp + personal view of a dollar earned: corporate tax on income,
    personal tax on the dividends that flowed out."""
    corp_tax = corp["income"]["tax_estimate"]
    personal_tax = personal["totals"]["total_tax"]
    pre_tax = corp["income"]["before_tax"]
    combined = round(corp_tax + personal_tax, 2)
    return {
        "corporate_income_before_tax": pre_tax,
        "corporate_tax_estimate": corp_tax,
        "dividends_to_owner": personal["totals"]["cash_received"],
        "personal_tax_estimate": personal_tax,
        "combined_tax": combined,
        "combined_effective_rate": round(combined / pre_tax, 4) if pre_tax > 0 else 0.0,
        "owner_after_tax_cash": personal["totals"]["after_tax_cash"],
    }
