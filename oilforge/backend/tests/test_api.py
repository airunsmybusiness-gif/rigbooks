"""End-to-end API tests: the full owner-operator workflow — jobs, field
tickets, progress billing with holdback, bank import, shareholder draws,
year-end dividend cleanup, statements and exports."""
import io
from datetime import date

YEAR = date.today().year

SAMPLE_CSV = f"""Date,Description,Debit,Credit
{YEAR}-02-01,EFT CREDIT PRAIRIE ENERGY RESOURCES,0,"21,000.00"
{YEAR}-02-03,UFA CARDLOCK 0042 NISKU,842.10,0
{YEAR}-02-05,E-TRANSFER SEND J SMITH PERSONAL,5000.00,0
{YEAR}-02-07,WCB ALBERTA PREMIUM,610.00,0
{YEAR}-02-09,NAPA AUTO PARTS EDMONTON,312.55,0
{YEAR}-02-11,ATM WITHDRAWAL MAIN BRANCH,800.00,0
"""


def _post(client, auth, path, body):
    r = client.post(path, headers=auth, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_auth(client, auth):
    assert client.get("/api/auth/status").json()["needs_setup"] is False
    assert client.get("/api/auth/me", headers=auth).json()["email"] == "owner@example.com"
    assert client.get("/api/auth/me").status_code == 401


def test_bank_import_and_shareholder_classification(client, auth):
    r = client.post("/api/transactions/import", headers=auth,
                    files={"file": ("feb.csv", io.BytesIO(SAMPLE_CSV.encode()), "text/csv")})
    assert r.json()["created"] == 6
    txs = client.get(f"/api/transactions?start={YEAR}-01-01&end={YEAR}-12-31",
                     headers=auth).json()["items"]
    by_desc = {t["description"]: t for t in txs}
    assert by_desc["UFA CARDLOCK 0042 NISKU"]["category"] == "Fuel & Petroleum"
    assert by_desc["UFA CARDLOCK 0042 NISKU"]["itc"] == round(842.10 * 0.05 / 1.05, 2)
    assert by_desc["WCB ALBERTA PREMIUM"]["itc"] == 0.0
    # Owner transfers auto-classify as shareholder activity.
    assert by_desc["E-TRANSFER SEND J SMITH PERSONAL"]["status"] == "shareholder"
    assert by_desc["ATM WITHDRAWAL MAIN BRANCH"]["status"] == "shareholder"
    assert by_desc["EFT CREDIT PRAIRIE ENERGY RESOURCES"]["category"] == "Revenue - Contract Services"


def test_job_flow_with_progress_billing_and_holdback(client, auth):
    cl = _post(client, auth, "/api/clients", {"name": "Prairie Energy Resources"})
    site = _post(client, auth, "/api/sites", {
        "name": "Well 7-11", "lsd": "07-11-048-09W5", "client_id": cl["id"]})
    job = _post(client, auth, "/api/jobs", {
        "client_id": cl["id"], "site_id": site["id"],
        "title": "Completions support", "rate_type": "day_rate",
        "day_rate": 2400, "mobilization_fee": 1500, "holdback_pct": 10,
        "start_date": f"{YEAR}-03-01"})
    assert job["number"] == "WO-0001"

    _post(client, auth, "/api/job-entries", {
        "job_id": job["id"], "date": f"{YEAR}-03-01", "kind": "mobilization",
        "description": "Mob to site", "quantity": 1, "rate": 1500})
    for day in (2, 3, 4):
        _post(client, auth, "/api/job-entries", {
            "job_id": job["id"], "date": f"{YEAR}-03-0{day}", "kind": "day",
            "description": "Day rate", "quantity": 1, "rate": 2400,
            "ticket_ref": f"FT-10{day}"})

    _post(client, auth, "/api/expenses", {
        "date": f"{YEAR}-03-02", "vendor": "Sunbelt", "description": "Light tower",
        "amount": 630.0, "category": "Equipment Rental", "job_id": job["id"]})

    inv = client.post(f"/api/invoices/from-job/{job['id']}", headers=auth).json()
    assert inv["subtotal"] == 8700.0                      # 1500 + 3x2400
    assert inv["gst"] == 435.0
    assert inv["holdback"] == 870.0
    assert inv["amount_due_now"] == 8700.0 + 435.0 - 870.0
    assert len(inv["lines"]) == 4

    # All entries now billed; a second progress invoice has nothing to pull.
    r = client.post(f"/api/invoices/from-job/{job['id']}", headers=auth)
    assert r.status_code == 422

    prof = client.get(f"/api/jobs/{job['id']}/profitability", headers=auth).json()
    assert prof["earned"] == 8700.0
    assert prof["costs"] == 630.0
    assert prof["margin"] == 8070.0
    assert prof["holdback_outstanding"] == 870.0

    # Release the holdback -> amount due covers the full total.
    upd = client.put(f"/api/invoices/{inv['id']}", headers=auth,
                     json={"holdback_released": True}).json()
    assert upd["amount_due_now"] == upd["total"]

    pdf = client.get(f"/api/invoices/{inv['id']}/pdf", headers=auth)
    assert pdf.content[:4] == b"%PDF"


def test_shareholder_ledger_dividend_cleanup(client, auth):
    holder = _post(client, auth, "/api/shareholders",
                   {"name": "J. Smith", "ownership_pct": 100})
    sid = holder["id"]

    # Draws through the year (would come from bank posting in real use).
    for month, amt in ((3, 6000), (5, 7000), (8, 6500)):
        _post(client, auth, "/api/shareholder-txns", {
            "shareholder_id": sid, "date": f"{YEAR}-{month:02d}-15",
            "type": "withdrawal", "amount": amt})
    # Owner paid a corp expense personally.
    _post(client, auth, "/api/shareholder-txns", {
        "shareholder_id": sid, "date": f"{YEAR}-06-01",
        "type": "corp_expense_paid_personally", "amount": 500,
        "memo": "Hotel for rig move"})

    led = client.get(f"/api/shareholder/{sid}/ledger", headers=auth).json()
    assert led["balance"] == 6000 + 7000 + 6500 - 500
    assert led["assessment"]["owing_to_corp"] is True

    # Year-end: accountant declares a non-eligible dividend against the loan.
    _post(client, auth, "/api/dividends", {
        "shareholder_id": sid, "date": f"{YEAR}-12-31", "amount": 19000,
        "kind": "non_eligible", "settlement": "loan",
        "resolution_ref": f"RES-{YEAR}-01"})

    led = client.get(f"/api/shareholder/{sid}/ledger", headers=auth).json()
    assert led["balance"] == 0.0
    assert led["assessment"]["owing_to_corp"] is False

    t5 = client.get(f"/api/shareholder/{sid}/t5?year={YEAR}", headers=auth).json()
    assert t5["kinds"]["non_eligible"]["actual"] == 19000.0
    assert t5["kinds"]["non_eligible"]["taxable"] == round(19000 * 1.15, 2)

    reg = client.get(f"/api/reports/dividend-register/{sid}.pdf?year={YEAR}",
                     headers=auth)
    assert reg.content[:4] == b"%PDF"


def test_post_bank_withdrawal_to_ledger(client, auth):
    txs = client.get(f"/api/transactions?start={YEAR}-01-01&end={YEAR}-12-31"
                     "&unposted=true", headers=auth).json()["items"]
    assert len(txs) >= 2
    holder = client.get("/api/shareholders", headers=auth).json()["items"][0]
    target = next(t for t in txs if "ATM" in t["description"])
    posted = client.post("/api/shareholder/post-from-bank", headers=auth,
                         json={"bank_txn_id": target["id"],
                               "shareholder_id": holder["id"]})
    assert posted.status_code == 201
    assert posted.json()["type"] == "withdrawal"
    assert posted.json()["amount"] == 800.0
    # Idempotent: same bank line can't be posted twice.
    again = client.post("/api/shareholder/post-from-bank", headers=auth,
                        json={"bank_txn_id": target["id"],
                              "shareholder_id": holder["id"]})
    assert again.status_code == 409


def test_journal_export(client, auth):
    r = client.get(f"/api/shareholder/journal.csv?start={YEAR}-01-01&end={YEAR}-12-31",
                   headers=auth)
    assert r.status_code == 200
    body = r.text
    assert "Due from Shareholder - J. Smith" in body
    assert "Retained Earnings - Dividends Declared" in body
    # Withdrawals debit the loan; the dividend credits it.
    assert body.count("Owner withdrawal") >= 3


def test_equipment_and_cca_report(client, auth):
    _post(client, auth, "/api/equipment", {
        "name": "Skid steer", "cca_class": "38", "cost": 120000,
        "acquired": f"{YEAR}-01-15"})
    eq = _post(client, auth, "/api/equipment", {
        "name": "Service truck", "cca_class": "10", "cost": 68000,
        "acquired": f"{YEAR}-02-01"})
    _post(client, auth, "/api/maintenance", {
        "equipment_id": eq["id"], "date": f"{YEAR}-04-10", "kind": "service",
        "description": "Oil change + filters", "cost": 420.0, "vendor": "NAPA"})
    cca = client.get(f"/api/reports/cca?year={YEAR}", headers=auth).json()
    classes = {r["class"]: r for r in cca["classes"]}
    assert classes["38"]["cca"] == round(120000 * 1.5 * 0.30, 2)
    assert classes["10"]["cca"] == round(68000 * 1.5 * 0.30, 2)


def test_statements_and_dashboard(client, auth):
    dash = client.get(f"/api/reports/dashboard?start={YEAR}-01-01&end={YEAR}-12-31",
                      headers=auth).json()
    assert dash["revenue"]["invoiced"] > 0
    assert dash["kpis"]["cash_position"] != 0
    assert len(dash["cash_flow"]) == 12
    assert dash["job_margins"][0]["margin"] > 0
    assert any(u["running_costs"] > 0 for u in dash["equipment_utilization"])

    st = client.get(f"/api/reports/statements?start={YEAR}-01-01&end={YEAR}-12-31",
                    headers=auth).json()
    tb = st["trial_balance"]
    assert tb["total_debits"] == tb["total_credits"]
    assert st["summary"]["income"]["cca"] > 0

    pdf = client.get(f"/api/reports/statements.pdf?start={YEAR}-01-01&end={YEAR}-12-31",
                     headers=auth)
    assert pdf.content[:4] == b"%PDF"


def test_encrypted_backup_roundtrip(client, auth):
    enc = client.get("/api/reports/backup?password=fieldpass99", headers=auth)
    assert enc.status_code == 200
    assert not enc.content.startswith(b"{")          # actually encrypted

    # Wrong password fails cleanly.
    bad = client.post("/api/reports/backup/restore?password=wrong", headers=auth,
                      files={"file": ("b.ofb", io.BytesIO(enc.content))})
    assert bad.status_code == 422

    plain = client.get("/api/reports/backup", headers=auth)
    assert plain.json()["_meta"]["app"] == "OilForge"
    assert len(plain.json()["bank_transactions"]) == 6


def test_rules_override_and_audit_trail(client, auth):
    r = client.put(f"/api/rules/{YEAR}", headers=auth,
                   json={"shareholder_loan": {"prescribed_rate": 0.05}}).json()
    assert r["shareholder_loan"]["prescribed_rate"] == 0.05
    client.delete(f"/api/rules/{YEAR}/overrides", headers=auth)

    logres = client.get("/api/reports/audit-log", headers=auth).json()
    actions = {(a["action"], a["entity"]) for a in logres["items"]}
    assert ("import", "bank_transactions") in actions
    assert ("create", "dividend_declarations") in actions
    assert ("export", "shareholder_journal") in actions


def test_migration_placeholder(client, auth):
    r = client.post("/api/reports/migration/import?source=quickbooks",
                    headers=auth,
                    files={"file": ("old.csv", io.BytesIO(b"Date,Amount\n2024-01-01,5"))})
    assert r.json()["status"] == "received"
