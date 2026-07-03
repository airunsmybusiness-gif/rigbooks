"""GST/HST filing detail: ITCs split operating vs capital property, per
category, quarterly breakdown, holdback GST memo — filing-ready summary."""
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session, joinedload

from ..cra import engine as cra
from ..helpers import get_province, get_setting, rules_for_year
from ..models import BankTransaction, Equipment, Expense, Invoice

CAPITAL_CATEGORIES = {"Capital Asset Purchase"}


def filing_summary(db: Session, start: date, end: date) -> dict:
    rules = rules_for_year(db, end.year)
    province = get_province(db)
    rate = cra.gst_rate(rules, province)

    invoices = (db.query(Invoice).options(joinedload(Invoice.lines))
                .filter(Invoice.date >= start, Invoice.date <= end,
                        Invoice.status != "void").all())
    revenue = sum(i.subtotal for i in invoices)
    gst_collected = sum(i.gst for i in invoices)
    holdback_gst_memo = round(sum(
        i.holdback * i.gst_rate for i in invoices if not i.holdback_released), 2)

    itc_by_category: dict[str, float] = defaultdict(float)
    quarterly = {q: {"gst_collected": 0.0, "itcs": 0.0} for q in (1, 2, 3, 4)}
    for i in invoices:
        quarterly[(i.date.month - 1) // 3 + 1]["gst_collected"] += i.gst

    operating_itc = capital_itc = 0.0
    for t in (db.query(BankTransaction)
              .filter(BankTransaction.date >= start, BankTransaction.date <= end,
                      BankTransaction.status == "business")):
        if t.itc > 0:
            itc_by_category[t.category] += t.itc
            quarterly[(t.date.month - 1) // 3 + 1]["itcs"] += t.itc
            if t.category in CAPITAL_CATEGORIES:
                capital_itc += t.itc
            else:
                operating_itc += t.itc
    for x in (db.query(Expense)
              .filter(Expense.date >= start, Expense.date <= end)):
        if x.itc > 0:
            itc_by_category[x.category] += x.itc
            quarterly[(x.date.month - 1) // 3 + 1]["itcs"] += x.itc
            if x.category in CAPITAL_CATEGORIES:
                capital_itc += x.itc
            else:
                operating_itc += x.itc

    # Capital property acquired in-period: ITC claimable on equipment used
    # >50% commercially (the normal case for oilfield units).
    equipment_itcs = []
    for e in (db.query(Equipment)
              .filter(Equipment.acquired.isnot(None),
                      Equipment.acquired >= start, Equipment.acquired <= end)):
        itc = round(e.cost * rate, 2)  # cost entered pre-GST
        equipment_itcs.append({"equipment": e.name, "cost": e.cost,
                               "potential_itc": itc})
    equipment_itc_total = round(sum(x["potential_itc"] for x in equipment_itcs), 2)
    capital_itc = round(capital_itc + equipment_itc_total, 2)

    total_itcs = round(operating_itc + capital_itc, 2)
    gst34 = cra.gst_return(revenue, gst_collected, total_itcs)

    return {
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "province": province, "gst_rate": rate,
        "gst34": gst34,
        "itcs": {
            "operating": round(operating_itc, 2),
            "capital_property": capital_itc,
            "capital_equipment_detail": equipment_itcs,
            "by_category": {k: round(v, 2) for k, v in
                            sorted(itc_by_category.items(), key=lambda x: -x[1])},
            "total": total_itcs,
        },
        "quarterly": [{"quarter": q,
                       "gst_collected": round(v["gst_collected"], 2),
                       "itcs": round(v["itcs"], 2),
                       "net": round(v["gst_collected"] - v["itcs"], 2)}
                      for q, v in quarterly.items()],
        "holdbacks": {
            "gst_on_unreleased_holdbacks": holdback_gst_memo,
            "note": ("GST on a holdback is generally collectible when the "
                     "holdback becomes payable (lien period expiry). This app "
                     "reports GST on the full invoice at issue - flag the "
                     "unreleased-holdback GST to the accountant if timing "
                     "relief is wanted."),
        },
        "rc4616": {
            "election": get_setting(db, "rc4616_election", None),
            "notes": rules["gst_hst"].get("rc4616_notes", ""),
        },
        "capital_note": ("Capital ITCs assume >50% commercial use (full ITC on "
                         "equipment). Passenger vehicles and mixed-use property "
                         "have special rules - confirm with the accountant."),
    }


def filing_csv(summary: dict) -> str:
    lines = ["line,description,amount"]
    g = summary["gst34"]
    lines.append(f'101,Sales and other revenue,{g["line_101_sales"]:.2f}')
    lines.append(f'105,GST/HST collected,{g["line_105_gst_collected"]:.2f}')
    lines.append(f'108,Total ITCs,{g["line_108_itcs"]:.2f}')
    lines.append(f',ITCs - operating,{summary["itcs"]["operating"]:.2f}')
    lines.append(f',ITCs - capital property,{summary["itcs"]["capital_property"]:.2f}')
    lines.append(f'109,Net tax,{g["line_109_net_tax"]:.2f}')
    lines.append(f',GST on unreleased holdbacks (memo),'
                 f'{summary["holdbacks"]["gst_on_unreleased_holdbacks"]:.2f}')
    for q in summary["quarterly"]:
        lines.append(f',Q{q["quarter"]} net,{q["net"]:.2f}')
    return "\n".join(lines) + "\n"
