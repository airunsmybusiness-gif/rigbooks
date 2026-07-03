"""Tax optimization scanner.

Sweeps the year's records for missed claims, compliance exposures and
book-to-tax items an accountant would want flagged. Every finding cites
the rule it comes from; amounts are computed where the data supports it.

Severities: action (money/compliance at stake) · review (judgment call)
· info (reminder of a claimable category that shows no activity).
"""
from datetime import date

from sqlalchemy.orm import Session

from . import shareholder as sh
from .cra import engine as cra
from .helpers import fiscal_year_end, get_setting, rules_for_year
from .models import (BankTransaction, DividendDeclaration, Equipment,
                     Expense, JobEntry, Shareholder)

CAPITAL_HINT_CATEGORIES = ("Equipment Repairs & Parts", "Shop Supplies",
                           "Other Operating")
CAPITAL_HINT_THRESHOLD = 2500.0


def _f(severity: str, title: str, detail: str, amount: float | None = None,
       action: str | None = None) -> dict:
    out = {"severity": severity, "title": title, "detail": detail}
    if amount is not None:
        out["amount"] = round(amount, 2)
    if action:
        out["action"] = action
    return out


def scan(db: Session, start: date, end: date, summary: dict,
         cca: dict) -> list[dict]:
    year = end.year
    rules = rules_for_year(db, year)
    findings: list[dict] = []

    # ---- shareholder / dividend compliance -----------------------------
    unposted = (db.query(BankTransaction)
                .filter(BankTransaction.date >= start, BankTransaction.date <= end,
                        BankTransaction.status == "shareholder",
                        BankTransaction.posted_shareholder_txn_id.is_(None)).all())
    if unposted:
        findings.append(_f(
            "action", f"{len(unposted)} owner transfers not on the loan ledger",
            "Bank lines flagged as shareholder activity aren't posted to the "
            "shareholder loan ledger yet, so the 15(2) balance is understated.",
            sum(t.debit or t.credit for t in unposted),
            "Bank Import → click ⇄ on each flagged row"))

    fye = fiscal_year_end(db, year)
    for holder in db.query(Shareholder).all():
        bal = sh.balance(db, holder.id, end)
        if bal > 0.005:
            a = cra.shareholder_loan_assessment(bal, fye.isoformat(), rules)
            findings.append(_f(
                "action", f"ITA 15(2): {holder.name} owes the corp",
                a["repayment_deadline_note"] + " Typical cleanup: declare a "
                "non-eligible dividend settled against the loan.",
                bal, "Dividends & Loans → Declare dividend"))

    grip = get_setting(db, "grip", {}) or {}
    grip_bal = float(grip.get(str(year), 0) or 0)
    eligible_declared = sum(
        d.amount for d in db.query(DividendDeclaration)
        .filter(DividendDeclaration.date >= date(year, 1, 1),
                DividendDeclaration.date <= date(year, 12, 31),
                DividendDeclaration.kind == "eligible"))
    if eligible_declared > grip_bal + 0.005:
        findings.append(_f(
            "action", "Eligible dividends exceed the GRIP balance",
            f"${eligible_declared:,.2f} of eligible dividends declared in "
            f"{year} vs GRIP of ${grip_bal:,.2f}. Excess eligible designations "
            "attract Part III.1 tax. Reclassify as non-eligible or update "
            "GRIP (Tax Optimizer page) from the accountant's figures.",
            eligible_declared - grip_bal))

    # ---- book-to-tax items ----------------------------------------------
    meals = summary["expenses"]["by_category"].get("Meals (50%)", 0.0)
    if meals > 0:
        findings.append(_f(
            "review", "Schedule 1 meals add-back",
            "50% of meals & entertainment is not deductible for tax. The "
            "Schedule 1 working paper adds this back automatically.",
            meals * rules["schedule1"]["meals_addback_pct"]))

    if cca.get("total_recapture", 0) > 0:
        findings.append(_f(
            "action", "CCA recapture is taxable income",
            "Disposal proceeds exceeded a class's UCC — the excess is "
            "recaptured into income on Schedule 8/1.",
            cca["total_recapture"]))
    if cca.get("total_terminal_loss", 0) > 0:
        findings.append(_f(
            "review", "Terminal loss available",
            "A class was emptied with UCC remaining — fully deductible as a "
            "terminal loss this year.", cca["total_terminal_loss"]))

    # ---- capital vs expense ---------------------------------------------
    big_expensed = (db.query(Expense)
                    .filter(Expense.date >= start, Expense.date <= end,
                            Expense.category.in_(CAPITAL_HINT_CATEGORIES),
                            Expense.amount >= CAPITAL_HINT_THRESHOLD).all())
    for x in big_expensed:
        findings.append(_f(
            "review", f"Possible capital item expensed: {x.vendor or x.description}",
            f"${x.amount:,.2f} in '{x.category}' on {x.date}. Items with a "
            "lasting benefit belong on the CCA schedule (though expensing "
            "repairs is often better — accountant's call).", x.amount))

    cap_txns = (db.query(BankTransaction)
                .filter(BankTransaction.date >= start, BankTransaction.date <= end,
                        BankTransaction.category == "Capital Asset Purchase").all())
    asset_dates = {e.acquired for e in db.query(Equipment)
                   .filter(Equipment.acquired.isnot(None))}
    orphans = [t for t in cap_txns if t.date not in asset_dates]
    if orphans:
        findings.append(_f(
            "action", f"{len(orphans)} capital purchases not on the CCA schedule",
            "Bank lines categorized as capital purchases with no matching "
            "equipment asset — they earn no CCA until added.",
            sum(t.debit for t in orphans),
            "Bank Import → 'To asset' on those rows"))

    # ---- categorization hygiene ------------------------------------------
    other = (db.query(BankTransaction)
             .filter(BankTransaction.date >= start, BankTransaction.date <= end,
                     BankTransaction.category == "Other Operating",
                     BankTransaction.status == "business").all())
    if other:
        findings.append(_f(
            "review", f"{len(other)} uncategorized business transactions",
            "Lines sitting in 'Other Operating' — recategorizing improves "
            "deduction support and may add ITCs (e.g. meals vs fuel vs PPE).",
            sum(t.debit for t in other),
            "Bank Import → filter category 'Other Operating'"))

    # ---- unbilled work ----------------------------------------------------
    unbilled = sum(e.quantity * e.rate for e in
                   db.query(JobEntry).filter(JobEntry.invoice_id.is_(None),
                                             JobEntry.date <= end))
    if unbilled > 0:
        findings.append(_f(
            "review", "Unbilled field work at period end",
            "Unbilled entries are WIP — bill them or tell the accountant so "
            "revenue is recognized in the right year.", unbilled,
            "Jobs → Invoice unbilled entries"))

    # ---- claimable-category reminders (zero-activity) ---------------------
    by_cat = summary["expenses"]["by_category"]
    reminders = [
        ("Safety Gear & PPE", "FR clothing, boots, H2S monitors, gloves — 100% "
         "deductible and easy to miss when bought personally."),
        ("Training & Certifications", "H2S Alive, First Aid, CSTS, well service "
         "tickets — deductible, and often bought on personal cards."),
        ("Camp & Accommodation", "Camp, lodging and reasonable allowances at "
         "remote sites are deductible (ITA 6(6) special work sites)."),
        ("Small Tools (<$500)", "Tools under $500 are class 12 — 100% "
         "write-off in the year of purchase."),
    ]
    for cat, why in reminders:
        if by_cat.get(cat, 0.0) == 0.0:
            findings.append(_f("info", f"No {cat} claimed this period", why))

    if summary.get("rules_provisional"):
        findings.append(_f(
            "review", f"{year} tax rates are provisional",
            "Verify current CRA figures in Tax Rules before relying on the "
            "estimates."))

    order = {"action": 0, "review": 1, "info": 2}
    findings.sort(key=lambda f: (order[f["severity"]], -(f.get("amount") or 0)))
    return findings
