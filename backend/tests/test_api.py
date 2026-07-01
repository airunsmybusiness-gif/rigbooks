"""End-to-end API tests: auth, CSV import, CRUD with tax hooks, reports."""
import io

SAMPLE_CSV = """Date,Description,Debit,Credit
2025-01-15,PETRO-CANADA #1234 EDMONTON,157.50,0
2025-01-16,WIRE TSF LONG RUN EXPLORATION,0,"5,250.00"
2025-01-17,TIM HORTONS #555,21.00,0
2025-01-18,MANULIFE INSURANCE PREM,210.00,0
2025-01-19,ATM WITHDRAWAL BANKING CENTRE,400.00,0
"""


def test_auth_flow(client, auth):
    assert client.get("/api/auth/status").json()["needs_setup"] is False
    r = client.get("/api/auth/me", headers=auth)
    assert r.json()["email"] == "driver@example.com"
    assert client.get("/api/auth/me").status_code == 401
    bad = client.post("/api/auth/login", json={
        "email": "driver@example.com", "password": "wrong"})
    assert bad.status_code == 401


def test_csv_import_classifies_and_calculates_itc(client, auth):
    r = client.post("/api/transactions/import", headers=auth,
                    files={"file": ("stmt.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")})
    assert r.status_code == 200
    assert r.json()["created"] == 5

    # Re-import is idempotent.
    r2 = client.post("/api/transactions/import", headers=auth,
                     files={"file": ("stmt.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")})
    assert r2.json() == {"created": 0, "skipped_duplicates": 5}

    txs = client.get("/api/transactions?start=2025-01-01&end=2025-12-31",
                     headers=auth).json()["items"]
    by_desc = {t["description"]: t for t in txs}
    fuel = by_desc["PETRO-CANADA #1234 EDMONTON"]
    assert fuel["category"] == "Fuel & Petroleum"
    assert fuel["itc"] == round(157.50 * 0.05 / 1.05, 2)
    assert by_desc["WIRE TSF LONG RUN EXPLORATION"]["category"] == "Revenue - Oilfield Services"
    assert by_desc["TIM HORTONS #555"]["itc"] == round(21.0 * 0.05 / 1.05 * 0.5, 2)
    assert by_desc["MANULIFE INSURANCE PREM"]["itc"] == 0.0  # exempt
    assert by_desc["ATM WITHDRAWAL BANKING CENTRE"]["status"] == "exclude"

    # Recategorizing recalculates ITC and is audited.
    tx_id = by_desc["MANULIFE INSURANCE PREM"]["id"]
    upd = client.put(f"/api/transactions/{tx_id}", headers=auth,
                     json={"category": "Other Business"}).json()
    assert upd["itc"] == round(210.0 * 0.05 / 1.05, 2)


def test_expense_hook_applies_year_rules(client, auth):
    r = client.post("/api/expenses", headers=auth, json={
        "date": "2025-03-01", "description": "New tires", "amount": 1050.0,
        "category": "Vehicle Repairs", "source": "cash", "paid_by": "Greg",
        "receipt_ref": "R-042"})
    assert r.status_code == 201
    assert r.json()["itc"] == 50.0  # 1050 * 5/105


def test_revenue_gst_extraction(client, auth):
    r = client.post("/api/revenue", headers=auth, json={
        "date": "2025-02-10", "client": "Long Run", "job": "Hotshot to Redwater",
        "amount": 2100.0, "gst_included": True}).json()
    assert r["gst_amount"] == 100.0
    r2 = client.post("/api/revenue", headers=auth, json={
        "date": "2025-02-11", "client": "PwC", "amount": 500.0,
        "gst_included": False}).json()
    assert r2["gst_amount"] == 0.0


def test_trip_defaults_and_mileage(client, auth):
    r = client.post("/api/trips", headers=auth, json={
        "date": "2025-02-12", "origin": "Edmonton", "destination": "Redwater",
        "purpose": "Haul", "odometer_start": 100000, "odometer_end": 100320,
        "business_km": 320}).json()
    assert r["total_km"] == 320.0
    assert r["jurisdiction_km"] == {"AB": 320.0}


def test_fuel_and_ifta_report(client, auth):
    client.post("/api/fuel", headers=auth, json={
        "date": "2025-02-13", "vendor": "Flying J", "jurisdiction": "AB",
        "litres": 200, "amount": 315.0})
    client.post("/api/trips", headers=auth, json={
        "date": "2025-02-14", "origin": "Edmonton", "destination": "Regina",
        "business_km": 780, "total_km": 780,
        "jurisdiction_km": {"AB": 480, "SK": 300}})
    report = client.get("/api/reports/ifta?year=2025&quarter=1", headers=auth).json()
    assert report["total_litres"] == 200.0
    juris = {l["jurisdiction"] for l in report["lines"]}
    assert {"AB", "SK"} <= juris


def test_invoice_lifecycle_and_pdf(client, auth):
    cust = client.post("/api/customers", headers=auth, json={
        "name": "Long Run Exploration", "is_ccpc": True}).json()
    inv = client.post("/api/invoices", headers=auth, json={
        "customer_id": cust["id"], "date": "2025-03-05",
        "lines": [{"description": "Hotshot delivery", "quantity": 1,
                   "unit_price": 850.0},
                  {"description": "Wait time (hrs)", "quantity": 3,
                   "unit_price": 95.0}]}).json()
    assert inv["subtotal"] == 1135.0
    assert inv["gst"] == 56.75
    assert inv["total"] == 1191.75
    assert inv["number"].startswith("INV-")

    pdf = client.get(f"/api/invoices/{inv['id']}/pdf", headers=auth)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"

    # Marking paid books revenue automatically (dated on payment day).
    from datetime import date
    year = date.today().year
    period = f"start={year}-01-01&end={year}-12-31"
    before = client.get(f"/api/revenue?{period}", headers=auth).json()["total"]
    client.put(f"/api/invoices/{inv['id']}", headers=auth, json={"status": "paid"})
    after = client.get(f"/api/revenue?{period}", headers=auth).json()["total"]
    assert after == before + 1


def test_home_office_itc_excludes_exempt_costs(client, auth):
    ho = client.put("/api/home-office/2025", headers=auth, json={
        "rent": 12000, "property_tax": 3000, "insurance": 1200,
        "electricity": 1800, "gas": 1400, "water": 600, "internet": 960,
        "pct": 15}).json()
    assert ho["total"] == 20960.0
    assert ho["deductible"] == 3144.0
    # ITC only on GST-bearing costs (not property tax / insurance).
    gst_bearing = (12000 + 1800 + 1400 + 600 + 960) * 0.15
    assert ho["itc"] == round(gst_bearing * 0.05 / 1.05, 2)


def test_meals_and_t4a_reports(client, auth):
    client.post("/api/meals", headers=auth, json={
        "date": "2025-04-01", "method": "simplified", "meals_count": 3,
        "long_haul": True, "location": "Fort McMurray"})
    client.post("/api/expenses", headers=auth, json={
        "date": "2025-04-02", "vendor": "Acme Accounting CCPC",
        "description": "Year-end", "amount": 1500.0,
        "category": "Professional Fees", "source": "other"})
    t4a = client.get("/api/reports/t4a?year=2025", headers=auth).json()
    assert any(c["vendor"] == "Acme Accounting CCPC" and c["total_fees"] >= 1500
               for c in t4a["candidates"])


def test_dashboard_summary_and_exports(client, auth):
    dash = client.get("/api/reports/dashboard?start=2025-01-01&end=2025-12-31",
                      headers=auth).json()
    assert dash["revenue"]["total"] > 0
    assert dash["expenses"]["total"] > 0
    assert dash["gst34"]["line_105_gst_collected"] > 0
    assert len(dash["monthly"]) == 12
    assert dash["mileage"]["business_km"] == 1100.0  # 320 + 780

    csv_r = client.get("/api/reports/t2125.csv?start=2025-01-01&end=2025-12-31",
                       headers=auth)
    assert csv_r.status_code == 200
    assert "Fuel & Petroleum" in csv_r.text

    pdf_r = client.get("/api/reports/summary.pdf?start=2025-01-01&end=2025-12-31",
                       headers=auth)
    assert pdf_r.content[:4] == b"%PDF"


def test_rules_override_and_reset(client, auth):
    r = client.put("/api/rules/2025", headers=auth,
                   json={"mileage": {"tier1_rate": 0.75}}).json()
    assert r["mileage"]["tier1_rate"] == 0.75
    r2 = client.delete("/api/rules/2025/overrides", headers=auth).json()
    assert r2["mileage"]["tier1_rate"] == 0.72


def test_audit_trail_records_everything(client, auth):
    logres = client.get("/api/reports/audit-log", headers=auth).json()
    actions = {(a["action"], a["entity"]) for a in logres["items"]}
    assert ("import", "bank_transactions") in actions
    assert ("create", "expenses") in actions
    assert ("update", "cra_rules") in actions


def test_backup_roundtrip(client, auth):
    backup = client.get("/api/reports/backup", headers=auth)
    assert backup.status_code == 200
    data = backup.json()
    assert data["_meta"]["app"] == "RigBooks"
    assert len(data["bank_transactions"]) == 5
