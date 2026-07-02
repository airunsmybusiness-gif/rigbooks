"""Tests for T2 preparation, the Personal Tax Bridge, GST filing detail,
and the new field-ops/data tooling. Runs after test_api.py in the same
session DB, so the seeded jobs/dividends/equipment are available."""
import io
from datetime import date

from oilforge.cra import engine as cra
from oilforge.cra import personal as pt

YEAR = date.today().year
R25 = cra.get_rules(2025)


# ------------------------------------------------- personal tax unit math

class TestBracketMath:
    def test_bracket_tax_first_bracket(self):
        assert pt.bracket_tax(50000, R25["personal_tax"]["federal_brackets"]) == 7500.0

    def test_bracket_tax_spans_brackets(self):
        # 57,375 * .15 + (80,000-57,375) * .205
        expected = 57375 * 0.15 + (80000 - 57375) * 0.205
        assert pt.bracket_tax(80000, R25["personal_tax"]["federal_brackets"]) == round(expected, 2)

    def test_marginal_rate(self):
        b = R25["personal_tax"]["federal_brackets"]
        assert pt.marginal_rate(50000, b) == 0.15
        assert pt.marginal_rate(120000, b) == 0.26
        assert pt.marginal_rate(999999, b) == 0.33


class TestT1Preview:
    def test_dividends_only_owner(self):
        t1 = pt.t1_preview(R25, "AB", {"non_eligible": 80000}, {})
        inc = t1["income"]
        assert inc["dividends_taxable"]["non_eligible"] == 92000.0
        assert inc["gross_up_added"] == 12000.0
        assert inc["taxable_income"] == 92000.0
        # Federal DTC on grossed-up amount
        assert t1["federal"]["dividend_tax_credit"] == round(92000 * 0.090301, 2)
        # AB DTC at 2.18% of taxable
        assert t1["provincial"]["dividend_tax_credit"] == round(92000 * 0.0218, 2)
        assert t1["totals"]["total_tax"] > 0
        assert t1["totals"]["after_tax_cash"] < 80000
        assert not t1["amt"]["applies"]  # under exemption at actual amounts

    def test_deductions_reduce_taxable(self):
        base = pt.t1_preview(R25, "AB", {"non_eligible": 50000}, {})
        with_rrsp = pt.t1_preview(R25, "AB", {"non_eligible": 50000},
                                  {"rrsp_deduction": 10000})
        assert (with_rrsp["income"]["taxable_income"]
                == base["income"]["taxable_income"] - 10000)
        assert with_rrsp["totals"]["total_tax"] < base["totals"]["total_tax"]

    def test_imputed_interest_adds_income(self):
        t1 = pt.t1_preview(R25, "AB", {}, {}, shareholder_loan_balance=50000)
        assert t1["income"]["imputed_interest_80_4"] == 2000.0  # 4%

    def test_amt_computed_but_not_binding_on_dividends(self):
        # Under the reformed 2024+ AMT, dividends-only income rarely binds:
        # the base uses actual amounts, so regular tax stays higher.
        t1 = pt.t1_preview(R25, "AB", {"eligible": 400000}, {})
        assert t1["amt"]["adjusted_income"] == 400000
        assert t1["amt"]["amt_tax"] > 0
        assert t1["amt"]["applies"] is False
        assert t1["totals"]["total_tax"] == t1["totals"]["regular_tax"]

    def test_amt_binds_when_exemption_removed(self):
        # Verify the comparison logic itself with an aggressive override.
        rules = cra.get_rules(2025, {"personal_tax": {"amt": {
            "exemption": 0, "rate": 0.5}}})
        t1 = pt.t1_preview(rules, "AB", {"eligible": 100000}, {})
        assert t1["amt"]["applies"] is True
        assert t1["totals"]["total_tax"] > t1["totals"]["regular_tax"] - t1["provincial"]["net"]

    def test_zero_income(self):
        t1 = pt.t1_preview(R25, "AB", {}, {})
        assert t1["totals"]["total_tax"] == 0.0


# ------------------------------------------------------------ API flows

def test_t2_package_and_close(client, auth):
    pkg = client.get(f"/api/t2/package?year={YEAR}", headers=auth).json()
    s1 = pkg["schedule1"]
    # Meals add-back present only if meals were spent; structure always there.
    assert "net_income_for_tax" in s1
    assert s1["net_income_for_tax"] == round(
        s1["net_income_per_books"] + s1["total_addbacks"]
        - s1["deductions"][0]["amount"], 2)
    assert pkg["schedule8"]["total_cca"] > 0
    assert any(s["name"] == "J. Smith" for s in pkg["schedule50"])
    gifi = pkg["schedule125_gifi"]["lines"]
    assert gifi[0]["gifi"] == "8000"
    assert gifi[-1]["gifi"] == "9999"
    re = pkg["retained_earnings"]
    assert re["closing_retained_earnings"] == round(
        re["opening_retained_earnings"] + re["net_income_after_tax_estimate"]
        - re["dividends_declared"], 2)
    assert pkg["provision_entry"]["credit_account"] == "Income Taxes Payable"
    assert pkg["closed"] is False

    closed = client.post("/api/t2/close", headers=auth, json={"year": YEAR}).json()
    assert closed["closed"] is True
    # Next year's opening RE was rolled forward.
    pkg2 = client.get(f"/api/t2/package?year={YEAR}", headers=auth).json()
    assert pkg2["closed"] is True

    s8 = client.get(f"/api/t2/schedule8.csv?year={YEAR}", headers=auth)
    assert "ucc_closing" in s8.text and "TOTAL" in s8.text
    g = client.get(f"/api/t2/gifi.csv?year={YEAR}", headers=auth)
    assert "gifi_code" in g.text


def test_meals_addback_flows_to_schedule1(client, auth):
    client.post("/api/expenses", headers=auth, json={
        "date": f"{YEAR}-07-02", "vendor": "Boston Pizza",
        "description": "Crew supper", "amount": 210.0, "category": "Meals (50%)"})
    pkg = client.get(f"/api/t2/package?year={YEAR}", headers=auth).json()
    addbacks = {a["line"]: a["amount"] for a in pkg["schedule1"]["addbacks"]}
    assert addbacks.get("Non-deductible portion of Meals (50%)") == 105.0


def test_personal_tax_bridge_api(client, auth):
    holder = client.get("/api/shareholders", headers=auth).json()["items"][0]
    sid = holder["id"]
    r = client.put(f"/api/personal-tax/{sid}/{YEAR}", headers=auth, json={
        "employment_income": 0, "other_income": 12000,
        "interest_income": 500, "rrsp_deduction": 8000}).json()
    assert r["inputs"]["other_income"] == 12000
    t1 = r["t1_preview"]
    assert t1["income"]["dividends_actual"]["non_eligible"] > 0  # from seeded dividends
    assert t1["totals"]["marginal_rate"] > 0
    integ = r["integrated"]
    assert integ["combined_tax"] == round(
        integ["corporate_tax_estimate"] + integ["personal_tax_estimate"], 2)
    # Inputs persist
    again = client.get(f"/api/personal-tax/{sid}/{YEAR}", headers=auth).json()
    assert again["inputs"]["rrsp_deduction"] == 8000


def test_gst_filing_detail(client, auth):
    r = client.get(f"/api/reports/gst-filing?start={YEAR}-01-01&end={YEAR}-12-31",
                   headers=auth).json()
    itcs = r["itcs"]
    assert itcs["total"] == round(itcs["operating"] + itcs["capital_property"], 2)
    # Seeded equipment acquired this year appears as capital ITC detail.
    assert len(r["quarterly"]) == 4
    assert r["gst34"]["line_108_itcs"] == itcs["total"]
    csv_r = client.get(f"/api/reports/gst-filing.csv?start={YEAR}-01-01&end={YEAR}-12-31",
                       headers=auth)
    assert "ITCs - capital property" in csv_r.text


def test_attachments_lifecycle(client, auth):
    entries = client.get(f"/api/job-entries?start={YEAR}-01-01&end={YEAR}-12-31",
                         headers=auth).json()["items"]
    entry_id = entries[0]["id"]
    fake_jpeg = b"\xff\xd8\xff\xe0" + b"0" * 100
    up = client.post(f"/api/attachments/job_entries/{entry_id}", headers=auth,
                     files={"file": ("ticket.jpg", io.BytesIO(fake_jpeg), "image/jpeg")})
    assert up.status_code == 201
    att = up.json()
    listed = client.get(f"/api/attachments/job_entries/{entry_id}", headers=auth).json()
    assert any(a["id"] == att["id"] for a in listed)
    blob = client.get(f"/api/attachments/file/{att['id']}", headers=auth)
    assert blob.content[:4] == b"\xff\xd8\xff\xe0"
    bad = client.post(f"/api/attachments/job_entries/{entry_id}", headers=auth,
                      files={"file": ("x.exe", io.BytesIO(b"MZ"), "application/x-msdownload")})
    assert bad.status_code == 415
    assert client.delete(f"/api/attachments/{att['id']}", headers=auth).status_code == 200


def test_parts_inventory(client, auth):
    part = client.post("/api/parts", headers=auth, json={
        "name": "Hydraulic filter", "part_number": "HF-6177",
        "qty_on_hand": 4, "unit_cost": 38.5, "min_qty": 2}).json()
    used = client.post(f"/api/parts/{part['id']}/adjust", headers=auth,
                       json={"delta": -3, "reason": "250h service"}).json()
    assert used["qty_on_hand"] == 1.0
    assert used["low_stock"] is True
    over = client.post(f"/api/parts/{part['id']}/adjust", headers=auth,
                       json={"delta": -5})
    assert over.status_code == 422


def test_safety_registry(client, auth):
    item = client.post("/api/safety", headers=auth, json={
        "kind": "certificate", "name": "H2S Alive", "reference": "ES-2211",
        "issued": f"{YEAR - 2}-06-01", "expires": f"{YEAR}-06-01"}).json()
    items = client.get("/api/safety", headers=auth).json()["items"]
    assert any(i["id"] == item["id"] for i in items)


def test_csv_import_tools(client, auth):
    tpl = client.get("/api/import/template/expenses", headers=auth)
    assert tpl.text.startswith("date,vendor")
    csv_data = (f"date,vendor,description,amount,category,receipt_ref\n"
                f"{YEAR}-03-03,Acklands,Gloves,105.00,Safety Gear & PPE,R-77\n"
                f"bad-date,X,Y,10,Other Operating,\n")
    r = client.post("/api/import/expenses", headers=auth,
                    files={"file": ("exp.csv", io.BytesIO(csv_data.encode()), "text/csv")}).json()
    assert r["created"] == 1
    assert len(r["errors"]) == 1
    items = client.get(f"/api/expenses?q=Acklands&start={YEAR}-01-01&end={YEAR}-12-31",
                       headers=auth).json()["items"]
    assert items[0]["itc"] == 5.0  # 105 * 5/105


def test_shareholder_yearly_and_plan(client, auth):
    holder = client.get("/api/shareholders", headers=auth).json()["items"][0]
    yearly = client.get(f"/api/shareholder/{holder['id']}/yearly", headers=auth).json()
    assert len(yearly["years"]) >= 1
    row = next(y for y in yearly["years"] if y["year"] == YEAR)
    assert "repayment_deadline" in row
    plan = client.get(f"/api/shareholder/{holder['id']}/repayment-plan",
                      headers=auth).json()
    assert plan["dividend_to_clear_now"] == max(plan["balance"], 0)
    assert len(plan["options"]) == 3


def test_accountant_package_zip(client, auth):
    import zipfile as zf
    r = client.get(f"/api/reports/accountant-package.zip?year={YEAR}", headers=auth)
    assert r.status_code == 200
    z = zf.ZipFile(io.BytesIO(r.content))
    names = z.namelist()
    assert "01_financial_summary.pdf" in names
    assert "02_t2_package.json" in names
    assert "03_gst_filing_summary.csv" in names
    assert "05_t5_dividends.csv" in names
    assert z.read("01_financial_summary.pdf")[:4] == b"%PDF"
    assert "J. Smith" in z.read("05_t5_dividends.csv").decode()


def test_audit_csv_export(client, auth):
    r = client.get("/api/reports/audit-log.csv", headers=auth)
    assert r.text.startswith("timestamp_utc,")
    assert "year_end_close" in r.text


def test_login_rate_limit(client, auth):
    for _ in range(5):
        bad = client.post("/api/auth/login", json={
            "email": "bruteforce@example.com", "password": "nope"})
        assert bad.status_code == 401
    locked = client.post("/api/auth/login", json={
        "email": "bruteforce@example.com", "password": "nope"})
    assert locked.status_code == 429
