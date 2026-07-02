"""PDF generation (reportlab): invoices, financial summary, dividend register."""
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

_styles = getSampleStyleSheet()
_H1 = ParagraphStyle("H1", parent=_styles["Heading1"], fontSize=20,
                     textColor=colors.HexColor("#1c1917"))
_H2 = ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=12,
                     textColor=colors.HexColor("#44403c"))
_BODY = _styles["BodyText"]
_SMALL = ParagraphStyle("Small", parent=_styles["BodyText"], fontSize=8,
                        textColor=colors.HexColor("#78716c"))

_TABLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1c1917")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d6d3d1")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f4")]),
    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
])


def _money(v: float) -> str:
    return f"${v:,.2f}"


def _doc(buf):
    return SimpleDocTemplate(buf, pagesize=letter, topMargin=0.7 * inch,
                             bottomMargin=0.7 * inch)


def invoice_pdf(inv: dict, business: dict, client_address: str,
                terms: str = "") -> bytes:
    buf = io.BytesIO()
    story = [
        Paragraph(business.get("name", "OilForge"), _H1),
        Paragraph(f"GST # {business.get('gst_number') or '—'} · "
                  f"BN {business.get('bn') or '—'} · "
                  f"Province {business.get('province', 'AB')}", _SMALL),
        Spacer(1, 14),
        Paragraph(f"INVOICE {inv['number']}"
                  + (f" · Job {inv['job_number']}" if inv.get("job_number") else ""), _H2),
        Paragraph(f"Date: {inv['date']} &nbsp;&nbsp; Due: {inv.get('due_date') or 'On receipt'}"
                  f" &nbsp;&nbsp; Status: {inv['status'].upper()}", _BODY),
        Spacer(1, 6),
        Paragraph(f"<b>Bill to:</b> {inv.get('client_name', '')}", _BODY),
    ]
    if client_address:
        story.append(Paragraph(client_address.replace("\n", "<br/>"), _BODY))
    story.append(Spacer(1, 12))

    rows = [["Description", "Qty", "Unit Price", "Amount"]]
    for l in inv["lines"]:
        rows.append([Paragraph(l["description"], _BODY), f"{l['quantity']:g}",
                     _money(l["unit_price"]), _money(l["amount"])])
    rows.append(["", "", "Subtotal", _money(inv["subtotal"])])
    rows.append(["", "", f"GST ({inv['gst_rate'] * 100:g}%)", _money(inv["gst"])])
    if inv.get("holdback", 0) > 0 and not inv.get("holdback_released"):
        rows.append(["", "", f"Holdback ({inv['holdback_pct']:g}%)",
                     f"({_money(inv['holdback'])})"])
    rows.append(["", "", "AMOUNT DUE", _money(inv["amount_due_now"])])
    t = Table(rows, colWidths=[3.6 * inch, 0.7 * inch, 1.4 * inch, 1.2 * inch])
    t.setStyle(_TABLE)
    t.setStyle(TableStyle([("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold")]))
    story.append(t)
    if inv.get("holdback", 0) > 0:
        story += [Spacer(1, 6), Paragraph(
            "Holdback retained per contract; released on completion/lien "
            "period expiry. GST is charged on the full contract value.", _SMALL)]
    if inv.get("notes"):
        story += [Spacer(1, 8), Paragraph(inv["notes"], _BODY)]
    if terms:
        story += [Spacer(1, 8), Paragraph(f"Terms: {terms}", _SMALL)]
    _doc(buf).build(story)
    return buf.getvalue()


def financial_summary_pdf(summary: dict, tb: dict, business: dict) -> bytes:
    buf = io.BytesIO()
    p = summary["period"]
    story = [
        Paragraph(f"{business.get('name', 'OilForge')} — Financial Summary", _H1),
        Paragraph(f"Fiscal period {p['start']} to {p['end']} · Province "
                  f"{summary['province']} · Generated {date.today().isoformat()}", _SMALL),
    ]
    if summary.get("rules_provisional"):
        story.append(Paragraph("⚠ Tax figures use PROVISIONAL rates — verify "
                               "before filing.", _SMALL))
    story.append(Spacer(1, 10))

    inc = summary["income"]
    rows = [["Income Statement", "Amount"],
            ["Revenue (invoiced)", _money(summary["revenue"]["invoiced"])],
            ["Operating expenses", f"({_money(summary['expenses']['total'])})"],
            ["EBITDA", _money(inc["ebitda"])],
            ["CCA (depreciation)", f"({_money(inc['cca'])})"],
            ["Income before tax", _money(inc["before_tax"])],
            [f"Corporate tax estimate ({inc['small_business_rate'] * 100:g}%)",
             f"({_money(inc['tax_estimate'])})"],
            ["Estimated after-tax income", _money(inc["after_tax_estimate"])]]
    t = Table(rows, colWidths=[4.6 * inch, 1.9 * inch])
    t.setStyle(_TABLE)
    story += [t, Spacer(1, 10)]

    g = summary["gst34"]
    rows = [["GST/HST (Form GST34 working copy)", "Amount"],
            ["Line 101 - Sales", _money(g["line_101_sales"])],
            ["Line 105 - GST/HST collected", _money(g["line_105_gst_collected"])],
            ["Line 108 - ITCs", _money(g["line_108_itcs"])],
            ["Line 109 - Net tax " + ("(owing)" if g["owing"] else "(refund)"),
             _money(abs(g["line_109_net_tax"]))]]
    t = Table(rows, colWidths=[4.6 * inch, 1.9 * inch])
    t.setStyle(_TABLE)
    story += [t, Spacer(1, 10)]

    shd = summary["shareholder"]
    story.append(Paragraph("Shareholder", _H2))
    story.append(Paragraph(
        f"Loan balance (due {'from' if shd['loan_balance_total'] >= 0 else 'to'} "
        f"shareholder): {_money(abs(shd['loan_balance_total']))} · "
        f"Dividends declared this period: {_money(shd['dividends_declared'])}", _BODY))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Trial Balance (derived)", _H2))
    rows = [["Account", "Debit", "Credit"]]
    for r in tb["rows"]:
        rows.append([r["account"],
                     _money(r["debit"]) if r["debit"] else "",
                     _money(r["credit"]) if r["credit"] else ""])
    rows.append(["TOTALS", _money(tb["total_debits"]), _money(tb["total_credits"])])
    t = Table(rows, colWidths=[3.9 * inch, 1.3 * inch, 1.3 * inch])
    t.setStyle(_TABLE)
    t.setStyle(TableStyle([("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    story += [t, Spacer(1, 8),
              Paragraph(tb["note"], _SMALL),
              Paragraph("Keep all records at least 6 years (CRA).", _SMALL)]
    _doc(buf).build(story)
    return buf.getvalue()


def dividend_register_pdf(shareholder: dict, rows: list[dict], t5: dict,
                          business: dict, year: int) -> bytes:
    buf = io.BytesIO()
    story = [
        Paragraph(f"{business.get('name', 'OilForge')} — Dividend Register {year}", _H1),
        Paragraph(f"Shareholder: {shareholder['name']} "
                  f"({shareholder['ownership_pct']:g}% ownership) · "
                  f"Generated {date.today().isoformat()}", _SMALL),
        Spacer(1, 12),
    ]
    table = [["Date", "Kind", "Settlement", "Resolution", "Amount"]]
    for d in rows:
        table.append([d["date"], d["kind"].replace("_", "-"), d["settlement"],
                      d.get("resolution_ref") or "—", _money(d["amount"])])
    t = Table(table, colWidths=[1.0 * inch, 1.2 * inch, 1.0 * inch,
                                1.9 * inch, 1.4 * inch])
    t.setStyle(_TABLE)
    story += [t, Spacer(1, 12), Paragraph("T5 slip figures", _H2)]

    trows = [["", "Actual", "Taxable (grossed up)", "Dividend tax credit"]]
    for kind, label in (("non_eligible", "Non-eligible (boxes 10/11/12)"),
                        ("eligible", "Eligible (boxes 24/25/26)")):
        k = t5["kinds"][kind]
        trows.append([label, _money(k["actual"]), _money(k["taxable"]),
                      _money(k["dtc"])])
    t = Table(trows, colWidths=[2.5 * inch, 1.3 * inch, 1.7 * inch, 1.5 * inch])
    t.setStyle(_TABLE)
    story += [t, Spacer(1, 8),
              Paragraph(f"T5 filing deadline: {t5['filing_deadline']}. Attach "
                        "directors' resolutions for each declaration.", _SMALL)]
    _doc(buf).build(story)
    return buf.getvalue()
