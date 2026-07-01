"""PDF generation (reportlab): customer invoices and CRA-ready summaries."""
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
                     textColor=colors.HexColor("#0f172a"))
_H2 = ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=12,
                     textColor=colors.HexColor("#334155"))
_BODY = _styles["BodyText"]
_SMALL = ParagraphStyle("Small", parent=_styles["BodyText"], fontSize=8,
                        textColor=colors.HexColor("#64748b"))

_TABLE_STYLE = TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ("FONTSIZE", (0, 0), (-1, -1), 9),
    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("TOPPADDING", (0, 0), (-1, -1), 5),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
])


def _money(v: float) -> str:
    return f"${v:,.2f}"


def invoice_pdf(inv: dict, business: dict, customer_address: str,
                terms: str = "") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.7 * inch,
                            bottomMargin=0.7 * inch)
    story = [
        Paragraph(business.get("name", "RigBooks"), _H1),
        Paragraph(f"GST # {business.get('gst_number', '—') or '—'} · "
                  f"Province: {business.get('province', 'AB')}", _SMALL),
        Spacer(1, 14),
        Paragraph(f"INVOICE {inv['number']}", _H2),
        Paragraph(f"Date: {inv['date']} &nbsp;&nbsp; Due: {inv.get('due_date') or 'On receipt'}"
                  f" &nbsp;&nbsp; Status: {inv['status'].upper()}", _BODY),
        Spacer(1, 6),
        Paragraph(f"<b>Bill to:</b> {inv.get('customer_name', '')}", _BODY),
    ]
    if customer_address:
        story.append(Paragraph(customer_address.replace("\n", "<br/>"), _BODY))
    story.append(Spacer(1, 12))

    rows = [["Description", "Qty", "Unit Price", "Amount"]]
    for l in inv["lines"]:
        rows.append([Paragraph(l["description"], _BODY), f"{l['quantity']:g}",
                     _money(l["unit_price"]), _money(l["amount"])])
    rows += [
        ["", "", "Subtotal", _money(inv["subtotal"])],
        ["", "", f"GST/HST ({inv['gst_rate'] * 100:g}%)", _money(inv["gst"])],
        ["", "", "TOTAL DUE", _money(inv["total"])],
    ]
    t = Table(rows, colWidths=[3.6 * inch, 0.7 * inch, 1.3 * inch, 1.3 * inch])
    t.setStyle(_TABLE_STYLE)
    t.setStyle(TableStyle([
        ("FONTNAME", (2, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (2, -3), (-1, -3), 1, colors.HexColor("#0f172a")),
    ]))
    story.append(t)
    if inv.get("notes"):
        story += [Spacer(1, 10), Paragraph(inv["notes"], _BODY)]
    if terms:
        story += [Spacer(1, 10), Paragraph(f"Terms: {terms}", _SMALL)]
    doc.build(story)
    return buf.getvalue()


def summary_pdf(summary: dict, business: dict) -> bytes:
    """CRA-ready accountant summary: revenue, expenses by category,
    ITCs by source, GST34 working copy, mileage log stats."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.7 * inch,
                            bottomMargin=0.7 * inch)
    p = summary["period"]
    story = [
        Paragraph(f"{business.get('name', 'RigBooks')} — Tax Summary", _H1),
        Paragraph(f"Period {p['start']} to {p['end']} · Province {summary['province']}"
                  f" · GST/HST rate {summary['gst_rate'] * 100:g}%"
                  f" · Generated {date.today().isoformat()}", _SMALL),
    ]
    if summary.get("rules_provisional"):
        story.append(Paragraph(
            "⚠ Tax rules for this year are PROVISIONAL — verify current CRA "
            "rates before filing.", _SMALL))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Income & GST/HST (Form GST34 working copy)", _H2))
    g = summary["gst34"]
    rows = [["Line", "Description", "Amount"],
            ["101", "Sales and other revenue", _money(g["line_101_sales"])],
            ["105", "GST/HST collected", _money(g["line_105_gst_collected"])],
            ["108", "Input tax credits (ITCs)", _money(g["line_108_itcs"])],
            ["109", "NET TAX " + ("(owing)" if g["owing"] else "(refund)"),
             _money(abs(g["line_109_net_tax"]))]]
    t = Table(rows, colWidths=[0.7 * inch, 4.2 * inch, 1.6 * inch])
    t.setStyle(_TABLE_STYLE)
    story += [t, Spacer(1, 12)]

    story.append(Paragraph("Business Expenses by Category (T2125 mapping)", _H2))
    rows = [["Category", "Deductible Amount"]]
    for cat, amt in summary["expenses"]["by_category"].items():
        rows.append([cat, _money(amt)])
    rows.append(["TOTAL EXPENSES", _money(summary["expenses"]["total"])])
    t = Table(rows, colWidths=[4.9 * inch, 1.6 * inch])
    t.setStyle(_TABLE_STYLE)
    t.setStyle(TableStyle([("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    story += [t, Spacer(1, 12)]

    story.append(Paragraph("Input Tax Credits by Source", _H2))
    rows = [["Source", "ITC"]]
    for src, amt in summary["itcs"]["by_source"].items():
        rows.append([src, _money(amt)])
    rows.append(["TOTAL ITCs", _money(summary["itcs"]["total"])])
    t = Table(rows, colWidths=[4.9 * inch, 1.6 * inch])
    t.setStyle(_TABLE_STYLE)
    t.setStyle(TableStyle([("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold")]))
    story += [t, Spacer(1, 12)]

    m = summary["mileage"]
    story.append(Paragraph("Vehicle & Mileage Log Summary", _H2))
    story.append(Paragraph(
        f"Business km: {m['business_km']:,} · Total km: {m['total_km']:,} · "
        f"Business use: {m['business_pct']}% · "
        f"CRA per-km allowance: {_money(m['cra_allowance'])} · "
        f"Fuel purchased: {m['fuel_litres']:,} L", _BODY))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Keep all receipts and this report for at least 6 years "
        "(CRA record-keeping requirement).", _SMALL))
    doc.build(story)
    return buf.getvalue()
