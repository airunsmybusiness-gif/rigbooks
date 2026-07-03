"""Bulk-import formats, split/bulk operations, tax optimizer, year-end."""
import io
import zipfile
from datetime import date

YEAR = date.today().year

# CIBC chequing export: no header row.
CIBC_CHEQUING = f"""{YEAR}-03-01,E-TRANSFER SEND LILIBETH PERSONAL,2500.00,
{YEAR}-03-02,UFA CARDLOCK 88 NISKU AB,412.88,
{YEAR}-03-03,EFT CREDIT PRAIRIE ENERGY RESOURCES,,18500.00
{YEAR}-03-04,PAYMENT THANK YOU/PAIEMENT MERCI,1200.00,
"""

# CIBC credit card export: masked card number in column 5.
CIBC_CARD = f"""{YEAR}-03-05,MARKS WORK WEARHOUSE EDMONTON,289.99,,4500********1234
{YEAR}-03-06,BOSTON PIZZA NISKU,64.50,,4500********1234
{YEAR}-03-07,PAYMENT THANK YOU,,1200.00,4500********1234
"""

# Generic single signed-amount export (negative = money out).
SIGNED = f"""Date,Description,Amount
{YEAR}-03-08,ACKLANDS GRAINGER PARTS,-312.75
{YEAR}-03-09,EFT CREDIT NORTHSTAR COMPLETIONS,9800.00
"""


def _import(client, auth, name, body):
    return client.post("/api/transactions/import", headers=auth,
                       files={"file": (name, io.BytesIO(body.encode()), "text/csv")}).json()


def test_cibc_chequing_format(client, auth):
    r = _import(client, auth, "cibc_chequing.csv", CIBC_CHEQUING)
    assert r["created"] == 4
    txs = client.get(f"/api/transactions?start={YEAR}-03-01&end={YEAR}-03-04",
                     headers=auth).json()["items"]
    by = {t["description"]: t for t in txs}
    assert by["E-TRANSFER SEND LILIBETH PERSONAL"]["status"] == "shareholder"
    assert by["UFA CARDLOCK 88 NISKU AB"]["category"] == "Fuel & Petroleum"
    assert by["EFT CREDIT PRAIRIE ENERGY RESOURCES"]["credit"] == 18500.0
    # Own credit-card payment excluded to avoid double counting.
    assert by["PAYMENT THANK YOU/PAIEMENT MERCI"]["status"] == "exclude"


def test_cibc_credit_card_format(client, auth):
    r = _import(client, auth, "cibc_card.csv", CIBC_CARD)
    assert r["created"] == 3
    txs = client.get(f"/api/transactions?start={YEAR}-03-05&end={YEAR}-03-07",
                     headers=auth).json()["items"]
    by = {t["description"]: t for t in txs}
    assert by["MARKS WORK WEARHOUSE EDMONTON"]["category"] == "Safety Gear & PPE"
    assert by["MARKS WORK WEARHOUSE EDMONTON"]["debit"] == 289.99
    assert by["BOSTON PIZZA NISKU"]["category"] == "Meals (50%)"


def test_signed_amount_format(client, auth):
    r = _import(client, auth, "signed.csv", SIGNED)
    assert r["created"] == 2
    txs = client.get(f"/api/transactions?start={YEAR}-03-08&end={YEAR}-03-09",
                     headers=auth).json()["items"]
    by = {t["description"]: t for t in txs}
    assert by["ACKLANDS GRAINGER PARTS"]["debit"] == 312.75
    assert by["EFT CREDIT NORTHSTAR COMPLETIONS"]["credit"] == 9800.0


def test_bulk_recategorize(client, auth):
    txs = client.get(f"/api/transactions?start={YEAR}-03-01&end={YEAR}-03-09",
                     headers=auth).json()["items"]
    ids = [t["id"] for t in txs if t["category"] == "Equipment Repairs & Parts"]
    assert ids
    r = client.put("/api/transactions/bulk", headers=auth,
                   json={"ids": ids, "category": "Shop Supplies"}).json()
    assert r["updated"] == len(ids)


def test_split_transaction(client, auth):
    txs = client.get(f"/api/transactions?start={YEAR}-03-05&end={YEAR}-03-05",
                     headers=auth).json()["items"]
    tx = txs[0]  # Marks 289.99 — half PPE, half personal
    r = client.post(f"/api/transactions/{tx['id']}/split", headers=auth, json={
        "parts": [
            {"amount": 200.00, "category": "Safety Gear & PPE", "note": "FR gear"},
            {"amount": 89.99, "category": "Owner Withdrawal", "note": "personal"},
        ]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["parent"]["status"] == "exclude"
    assert len(body["parts"]) == 2
    assert body["parts"][1]["status"] == "shareholder"
    # A split child can't be split again.
    again = client.post(f"/api/transactions/{body['parts'][0]['id']}/split",
                        headers=auth, json={"parts": [
                            {"amount": 100, "category": "Travel"},
                            {"amount": 100, "category": "Travel"}]})
    assert again.status_code == 409
    # Bad totals on a fresh line are rejected.
    fresh = client.get(f"/api/transactions?start={YEAR}-03-06&end={YEAR}-03-06",
                       headers=auth).json()["items"][0]
    bad = client.post(f"/api/transactions/{fresh['id']}/split", headers=auth,
                      json={"parts": [{"amount": 10, "category": "Travel"},
                                      {"amount": 20, "category": "Travel"}]})
    assert bad.status_code == 422


def test_convert_to_asset(client, auth):
    csv_body = f"{YEAR}-04-01,WAJAX EQUIPMENT WELDER PURCHASE,8400.00,\n"
    _import(client, auth, "cap.csv", csv_body)
    txs = client.get(f"/api/transactions?start={YEAR}-04-01&end={YEAR}-04-01",
                     headers=auth).json()["items"]
    r = client.post(f"/api/transactions/{txs[0]['id']}/to-asset", headers=auth,
                    json={"name": "Miller welder", "cca_class": "8"}).json()
    assert r["cost"] == 8000.0  # net of 5% GST
    eq = client.get("/api/equipment?q=Miller", headers=auth).json()["items"]
    assert eq and eq[0]["cca_class"] == "8"


def test_expense_csv_import_and_template(client, auth):
    t = client.get("/api/expenses/import-template", headers=auth)
    assert "Date,Vendor" in t.text
    body = (f"Date,Vendor,Description,Amount,Category,Receipt\n"
            f"{YEAR}-04-02,Enform,H2S Alive renewal,210.00,Training & Certifications,R-9\n"
            f"bad row,,,,\n")
    r = client.post("/api/expenses/import", headers=auth,
                    files={"file": ("hist.csv", io.BytesIO(body.encode()), "text/csv")}).json()
    assert r["created"] == 1 and r["skipped"] == 1


def test_tax_optimizer_findings(client, auth):
    r = client.get(f"/api/tax/optimizer?start={YEAR}-01-01&end={YEAR}-12-31",
                   headers=auth).json()
    titles = [f["title"] for f in r["findings"]]
    assert any("not on the loan ledger" in t for t in titles)  # unposted draws
    assert any("meals add-back" in t.lower() for t in titles)
    assert r["counts"]["action"] >= 1


def test_grip_warning(client, auth):
    holder = client.post("/api/shareholders", headers=auth,
                         json={"name": "G. Tester"}).json()
    client.post("/api/dividends", headers=auth, json={
        "shareholder_id": holder["id"], "date": f"{YEAR}-06-01",
        "amount": 50000, "kind": "eligible", "settlement": "cash"})
    client.put("/api/tax/grip", headers=auth, json={str(YEAR): 10000})
    r = client.get(f"/api/tax/optimizer?start={YEAR}-01-01&end={YEAR}-12-31",
                   headers=auth).json()
    assert any("GRIP" in f["title"] for f in r["findings"])


def test_schedule1_and_personal_bridge(client, auth):
    s1 = client.get(f"/api/tax/schedule1?start={YEAR}-01-01&end={YEAR}-12-31",
                    headers=auth).json()
    assert s1["lines"][0]["line"].startswith("Net income")
    assert s1["lines"][-1]["line"] == "Net income for tax purposes"

    pb = client.get(f"/api/tax/personal-bridge?year={YEAR}", headers=auth).json()
    assert pb["shareholders"]
    est = pb["shareholders"][-1]["estimate"]
    assert est["taxable_income"] > 0


def test_yearend_checklist_and_zip(client, auth):
    chk = client.get(f"/api/reports/yearend/checklist?start={YEAR}-01-01&end={YEAR}-12-31",
                     headers=auth).json()
    assert len(chk["items"]) == 7
    assert chk["ready"] is False  # unposted draws etc.

    z = client.get(f"/api/reports/yearend.zip?start={YEAR}-01-01&end={YEAR}-12-31",
                   headers=auth)
    assert z.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    names = zf.namelist()
    assert "01_financial_summary.pdf" in names
    assert "05_cca_schedule8.csv" in names
    assert "06_schedule1_working_paper.csv" in names
    assert "10_tax_optimization_summary.md" in names
    memo = zf.read("10_tax_optimization_summary.md").decode()
    assert "Year-end checklist" in memo


def test_salted_encrypted_backup(client, auth):
    a = client.get("/api/reports/backup?password=fieldpass99", headers=auth)
    b = client.get("/api/reports/backup?password=fieldpass99", headers=auth)
    assert a.content[:4] == b"OFB2"
    assert a.content[4:20] != b.content[4:20]  # unique salt per file
    ok = client.post("/api/reports/backup/restore?password=fieldpass99",
                     headers=auth,
                     files={"file": ("b.ofb", io.BytesIO(a.content))})
    assert ok.status_code == 200
