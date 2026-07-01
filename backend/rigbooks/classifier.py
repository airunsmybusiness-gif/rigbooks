"""Bank-statement auto-classifier.

Ports the RigBooks v4 regex rules and makes them user-editable: rules are
seeded into the classifier_rules table on first run, checked in priority
order, and manageable from the Transactions page.
"""
import csv
import io
import re
from datetime import date, datetime

from sqlalchemy.orm import Session

from .models import ClassifierRule

CATEGORIES = [
    'Revenue - Oilfield Services', 'Fuel & Petroleum', 'Rent - Work Accommodation',
    'Utilities', 'Vehicle Repairs', 'Equipment & Tools', 'Safety Gear & PPE',
    'Meals (50%)', 'Meals - Long Haul (80%)', 'Entertainment (50%)', 'Professional Fees',
    'Office Supplies', 'Phone & Communications', 'Internet', 'Bank Fees',
    'Loan - Business Vehicle', 'Training & Certifications', 'Software & Subscriptions',
    'Travel & Accommodations', 'Insurance', 'Donations', 'Other Business',
    'Shareholder Distribution', 'Personal Expense', 'Tax Payment', 'Exclude',
]

# (priority, pattern, category) — lower priority number wins.
DEFAULT_RULES = [
    (10, r'WIRE TSF.*PRICE|LONG RUN|MOBILE DEPOSIT', 'Revenue - Oilfield Services'),
    (20, r'GOVERNMENT CANADA', 'Tax Payment'),
    (30, r'INTERNET TRANSFER.*TO:|E-TRANSFER.*SEND|ATM WITHDR|ABM WITHDR|BANKING CENTRE|BRANCH.*WITHDR', 'Shareholder Distribution'),
    (40, r'TD ON-LINE LOANS|LOAN PAYMENT.*TD|SCOTIA BANK.*LOAN|LOAN.*SCOTIA', 'Loan - Business Vehicle'),
    (50, r'RENT@|REALTY|FOCUS@', 'Rent - Work Accommodation'),
    (60, r'EPCOR|ATCO|DIRECT ENERGY|ENMAX', 'Utilities'),
    (70, r'ACCOUNT FEE|SERVICE CHARGE|MONTHLY.*FEE', 'Bank Fees'),
    (80, r'MANULIFE', 'Insurance'),
    (90, r'KOODO|TELUS|BELL|ROGERS|FIDO', 'Phone & Communications'),
    (100, r'SHAW', 'Internet'),
    (110, r'PETRO|SHELL|ESSO|CHEVRON|CENTEX|MOBIL|FAS GA|FGP|CIRCLE K|CO-OP|BOYLE|DOMO|HUSKY|FLYING J|PILOT', 'Fuel & Petroleum'),
    (120, r'OK TIRE|NAPA|PART SOURCE|JIFFY|KEEPS MECH|GOODBRAND|SOUTH.?FORT|CANADIAN TIRE|KAL TIRE', 'Vehicle Repairs'),
    (130, r'PRINCESS AUTO|HOME HARDWARE|HOME DEPOT|ACKLANDS', 'Equipment & Tools'),
    (140, r'NOTARY|LAWYER|ACCOUNTANT|WORKERS COMP|COSTCO BUSINESS', 'Professional Fees'),
    (150, r'DOLLARAMA|IKEA|STAPLES', 'Office Supplies'),
    (160, r'COMMUNITY|DONATION', 'Donations'),
    (170, r'TIM HORTON|A&W |MCDONALD|SUBWAY|IGA|WALMART|SUPERSTORE|SAFEWAY|DENNY|HUSKY HOUSE', 'Meals (50%)'),
    (180, r'GOLF', 'Entertainment (50%)'),
    (190, r'LIQUOR|CANNA|BARBER|DAYCARE', 'Personal Expense'),
]

STATUS_BY_CATEGORY = {
    'Revenue - Oilfield Services': 'exclude',
    'Shareholder Distribution': 'exclude',
    'Tax Payment': 'exclude',
    'Exclude': 'exclude',
    'Personal Expense': 'personal',
}


def status_for(category: str) -> str:
    return STATUS_BY_CATEGORY.get(category, 'business')


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
    return 'Other Business'


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
    if raw in ("", "-"):
        return 0.0
    return float(raw)


def parse_bank_csv(content: str, rules: list[ClassifierRule]) -> list[dict]:
    """Parse a bank CSV export: Date, Description, Debit, Credit[, Balance].
    Rows without amounts and header rows are skipped."""
    out = []
    reader = csv.reader(io.StringIO(content))
    for parts in reader:
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
        out.append({
            "date": tx_date,
            "description": desc,
            "debit": debit,
            "credit": credit,
            "category": category,
            "status": status_for(category),
        })
    return out
