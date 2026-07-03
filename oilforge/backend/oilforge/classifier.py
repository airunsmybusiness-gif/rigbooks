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
    (15, r"PAYMENT THANK YOU|CREDIT CARD PAYMENT|PAYMENT - THANK YOU|MASTERCARD PAYMENT|VISA PAYMENT", "Exclude"),
    (20, r"GOVERNMENT CANADA|CRA |REVENUE CANADA|GST-P|TXINS|EMPTX|CORP TAX", "Tax Payment"),
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


def _looks_like_card(value: str) -> bool:
    """Masked card number column in CIBC credit-card exports
    (e.g. 4500********1234)."""
    v = value.strip().replace(" ", "")
    return bool(re.fullmatch(r"[0-9*]{12,19}", v)) and "*" in v


def _detect_layout(rows: list[list[str]]) -> dict:
    """Sniff the column layout from data rows.

    Supported shapes (all exported by major Canadian banks):
      - CIBC chequing (no header):      Date, Description, Debit, Credit
      - CIBC credit card (no header):   Date, Description, Debit, Credit, Card#
      - Generic with header:            Date, Description, Debit, Credit[, Balance]
      - Single signed amount:           Date, Description, Amount
        (negative = money out for chequing exports; some cards flip the sign,
         so a sign_flip is detected from keywords like PAYMENT THANK YOU)
    """
    sample = [r for r in rows if len(r) >= 3][:50]
    if not sample:
        return {"kind": "debit_credit"}
    ncols = max(len(r) for r in sample)
    has_card_col = any(len(r) >= 5 and _looks_like_card(r[4]) for r in sample)
    # Count rows where both col2 and col3 parse as money and only one is set.
    two_col = single = 0
    for r in sample:
        try:
            d = _money(r[2]) if len(r) > 2 else 0.0
            c = _money(r[3]) if len(r) > 3 and not _looks_like_card(r[3]) else None
        except ValueError:
            continue
        if c is not None:
            two_col += 1
        elif d != 0:
            single += 1
    if ncols <= 3 or (single > two_col):
        return {"kind": "signed_amount"}
    return {"kind": "debit_credit", "card": has_card_col}


def parse_bank_csv(content: str, rules: list[ClassifierRule]) -> list[dict]:
    """Parse a bank CSV export (CIBC chequing/credit-card, or any bank using
    Date/Description/Debit/Credit or Date/Description/signed-Amount). Header
    rows are skipped automatically; a full year in one file is fine."""
    all_rows = [r for r in csv.reader(io.StringIO(content)) if any(x.strip() for x in r)]
    # Drop header rows (anything whose first cell doesn't parse as a date).
    data_rows = []
    for r in all_rows:
        try:
            _parse_date(r[0])
            data_rows.append(r)
        except (ValueError, IndexError):
            continue
    layout = _detect_layout(data_rows)

    out = []
    for parts in data_rows:
        if len(parts) < 3:
            continue
        try:
            tx_date = _parse_date(parts[0])
            desc = parts[1].strip()
            if layout["kind"] == "signed_amount":
                amount = _money(parts[2])
                # Chequing convention: negative = money out.
                debit, credit = (-amount, 0.0) if amount < 0 else (0.0, amount)
            else:
                debit = _money(parts[2]) if len(parts) > 2 else 0.0
                credit = (_money(parts[3])
                          if len(parts) > 3 and not _looks_like_card(parts[3])
                          else 0.0)
        except ValueError:
            continue
        if debit == 0 and credit == 0:
            continue
        category = classify(desc, rules)
        out.append({"date": tx_date, "description": desc,
                    "debit": round(debit, 2), "credit": round(credit, 2),
                    "category": category, "status": status_for(category)})
    return out
