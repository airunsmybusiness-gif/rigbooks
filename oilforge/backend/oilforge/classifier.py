"""Bank-statement smart classifier (oilfield corporate flavor).

Regex rules → category; user-editable in the UI. Owner draws / transfers to
personal accounts classify as "Owner Withdrawal" with status `shareholder`,
ready for one-click posting to the shareholder loan ledger.
"""
import csv
import io
import re
from datetime import date, datetime

from sqlalchemy.orm import Session

from .models import ClassifierRule

CATEGORIES = [
    "Revenue - Contract Services", "Subcontractors", "Fuel & Petroleum",
    "Equipment Rental", "Equipment Repairs & Parts", "Shop Supplies",
    "Small Tools (<$500)", "Safety Gear & PPE", "Camp & Accommodation",
    "Meals (50%)", "Travel", "Insurance - Commercial", "Insurance - Equipment",
    "WCB Premiums", "Professional Fees", "Office & Admin",
    "Phone & Communications", "Software & Subscriptions", "Bank Fees",
    "Interest & Loan Charges", "Utilities - Shop", "Rent - Shop/Yard",
    "Licenses & Permits", "Training & Certifications", "Marketing",
    "Capital Asset Purchase", "Owner Withdrawal", "Shareholder Contribution",
    "Dividend Payment", "Tax Payment", "Other Operating", "Exclude",
]

DEFAULT_RULES = [
    (10, r"WIRE TSF|EFT CREDIT|MOBILE DEPOSIT|DIRECT DEPOSIT.*(ENERGY|OIL|RESOURCES|EXPLORATION)", "Revenue - Contract Services"),
    (20, r"GOVERNMENT CANADA|CRA |REVENUE CANADA|GST-P|TXINS", "Tax Payment"),
    (30, r"E-TRANSFER.*SEND|INTERNET TRANSFER.*TO:|ATM WITHDR|ABM WITHDR|BRANCH.*WITHDR|TFR-TO.*PERSONAL", "Owner Withdrawal"),
    (35, r"TFR-FR|E-TRANSFER.*RECEIV.*OWNER|SHAREHOLDER DEPOSIT", "Shareholder Contribution"),
    (40, r"WCB|WORKERS COMP", "WCB Premiums"),
    (50, r"UFA|CO-OP CARDLOCK|FLYING J|PILOT|PETRO|SHELL|ESSO|HUSKY|FAS GAS|CENTEX|MOBIL", "Fuel & Petroleum"),
    (60, r"NAPA|ACKLANDS|GREGG|PRINCESS AUTO|WAJAX|FINNING|BRANDT|PARTS", "Equipment Repairs & Parts"),
    (70, r"UNITED RENTALS|SUNBELT|CAT RENTAL|HERC ", "Equipment Rental"),
    (80, r"MARKS WORK|MARK'S|HI-VIS|SAFETY|HAZMASTERS|ACOT", "Safety Gear & PPE"),
    (90, r"H2S|ENFORM|ENERGY SAFETY|FIRST AID|OSSA|CSTS", "Training & Certifications"),
    (100, r"ATCO|EPCOR|ENMAX|DIRECT ENERGY|FORTIS", "Utilities - Shop"),
    (110, r"TELUS|BELL|ROGERS|SASKTEL|KOODO|STARLINK", "Phone & Communications"),
    (120, r"ACCOUNT FEE|SERVICE CHARGE|MONTHLY.*FEE|OVERDRAFT", "Bank Fees"),
    (130, r"LOAN INTEREST|INTEREST CHARGE|LEASE.*FINANCE", "Interest & Loan Charges"),
    (140, r"AVIVA|INTACT|WAWANESA|PEACE HILLS|LLOYD", "Insurance - Commercial"),
    (150, r"LAWYER|NOTARY|ACCOUNTING|ACCOUNTANT|BOOKKEEP|MNP|KPMG", "Professional Fees"),
    (160, r"STAPLES|DOLLARAMA|AMAZON.*OFFICE", "Office & Admin"),
    (170, r"TIM HORTON|A&W |MCDONALD|SUBWAY|DENNY|BOSTON PIZZA|RESTAURANT", "Meals (50%)"),
    (180, r"CAMP|LODGE|ATCO STRUCTURES|BLACK DIAMOND|HOTEL|MOTEL|INN ", "Camp & Accommodation"),
    (190, r"REGISTRIES|REGISTRY|LICENCE|LICENSE|PERMIT", "Licenses & Permits"),
]

STATUS_BY_CATEGORY = {
    "Revenue - Contract Services": "exclude",   # revenue, not an expense
    "Owner Withdrawal": "shareholder",
    "Shareholder Contribution": "shareholder",
    "Dividend Payment": "shareholder",
    "Tax Payment": "exclude",
    "Exclude": "exclude",
}


def status_for(category: str) -> str:
    return STATUS_BY_CATEGORY.get(category, "business")


def seed_default_rules(db: Session) -> None:
    if db.query(ClassifierRule).count() == 0:
        for prio, pattern, cat in DEFAULT_RULES:
            db.add(ClassifierRule(priority=prio, pattern=pattern, category=cat))
        db.commit()


def classify(description: str, rules: list[ClassifierRule]) -> str:
    d = description.upper()
    for rule in rules:
        try:
            if rule.enabled and re.search(rule.pattern, d):
                return rule.category
        except re.error:
            continue
    return "Other Operating"


def _parse_date(raw: str) -> date:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y", "%b %d, %Y",
                "%d-%b-%Y", "%Y/%m/%d", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unrecognized date: {raw!r}")


def _money(raw: str) -> float:
    raw = (raw or "").replace("$", "").replace(",", "").strip()
    return 0.0 if raw in ("", "-") else float(raw)


def parse_bank_csv(content: str, rules: list[ClassifierRule]) -> list[dict]:
    """Bank CSV: Date, Description, Debit, Credit[, Balance]."""
    out = []
    for parts in csv.reader(io.StringIO(content)):
        if len(parts) < 3:
            continue
        raw_date, desc = parts[0].strip(), parts[1].strip()
        if "date" in raw_date.lower():
            continue
        try:
            tx_date = _parse_date(raw_date)
            debit = _money(parts[2]) if len(parts) > 2 else 0.0
            credit = _money(parts[3]) if len(parts) > 3 else 0.0
        except ValueError:
            continue
        if debit == 0 and credit == 0:
            continue
        category = classify(desc, rules)
        out.append({"date": tx_date, "description": desc, "debit": debit,
                    "credit": credit, "category": category,
                    "status": status_for(category)})
    return out
