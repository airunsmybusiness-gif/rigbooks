"""Migration wizard: historical-data CSV imports for all template kinds."""
import io
from datetime import date

YEAR = date.today().year


def _imp(client, auth, kind, body):
    return client.post(f"/api/import/{kind}", headers=auth,
                       files={"file": (f"{kind}.csv", io.BytesIO(body.encode()),
                                       "text/csv")})


def test_templates_downloadable(client, auth):
    for kind in ("bank_transactions", "jobs", "shareholder_history",
                 "dividends", "expenses", "clients", "equipment"):
        r = client.get(f"/api/import/template/{kind}", headers=auth)
        assert r.status_code == 200, kind
        assert "," in r.text.splitlines()[0]
    assert client.get("/api/import/template/nonsense", headers=auth).status_code == 404


def test_bank_transactions_migration(client, auth):
    body = ("date,description,debit,credit,category,receipt_ref\n"
            "2023-04-05,UFA CARDLOCK HISTORICAL,350.00,,,R-H1\n"          # auto-classified
            "2023-04-08,EFT CREDIT OLD CLIENT LTD,,12000.00,Revenue - Contract Services,\n")
    r = _imp(client, auth, "bank_transactions", body).json()
    assert r["created"] == 2 and not r["errors"]
    # Re-import is idempotent.
    r2 = _imp(client, auth, "bank_transactions", body).json()
    assert r2["created"] == 0
    txs = client.get("/api/transactions?start=2023-01-01&end=2023-12-31",
                     headers=auth).json()["items"]
    by = {t["description"]: t for t in txs}
    assert by["UFA CARDLOCK HISTORICAL"]["category"] == "Fuel & Petroleum"
    assert by["UFA CARDLOCK HISTORICAL"]["itc"] == round(350 * 0.05 / 1.05, 2)
    assert by["UFA CARDLOCK HISTORICAL"]["receipt_ref"] == "R-H1"
    assert by["EFT CREDIT OLD CLIENT LTD"]["status"] == "exclude"


def test_jobs_migration_creates_clients(client, auth):
    body = ("number,title,client_name,rate_type,day_rate,hourly_rate,holdback_pct,status,start_date\n"
            "WO-H090,Historic turnaround,Legacy Oil Co,day_rate,2000,0,10,closed,2023-05-01\n")
    r = _imp(client, auth, "jobs", body).json()
    assert r["created"] == 1, r
    jobs = client.get("/api/jobs?q=WO-H090", headers=auth).json()["items"]
    assert jobs and jobs[0]["client_name"] == "Legacy Oil Co"
    assert jobs[0]["status"] == "closed"


def test_shareholder_history_and_dividends_migration(client, auth):
    body = ("date,shareholder_name,type,amount,memo\n"
            "2023-02-01,Migrated Owner,withdrawal,4000,historic draw\n"
            "2023-06-01,Migrated Owner,contribution,1000,cash in\n"
            "2023-07-01,Migrated Owner,teleport,50,bad type\n")
    r = _imp(client, auth, "shareholder_history", body).json()
    assert r["created"] == 2
    assert len(r["errors"]) == 1

    div = ("date,shareholder_name,amount,kind,settlement,resolution_ref\n"
           "2023-12-31,Migrated Owner,3000,non_eligible,loan,RES-2023-01\n")
    assert _imp(client, auth, "dividends", div).json()["created"] == 1

    holders = client.get("/api/shareholders?q=Migrated", headers=auth).json()["items"]
    led = client.get(f"/api/shareholder/{holders[0]['id']}/ledger",
                     headers=auth).json()
    assert led["balance"] == 0.0  # 4000 - 1000 - 3000


def test_receipt_search(client, auth):
    txs = client.get("/api/transactions?start=2023-01-01&end=2023-12-31&q=R-H1",
                     headers=auth).json()["items"]
    assert len(txs) == 1
    assert txs[0]["receipt_ref"] == "R-H1"


def test_attachment_on_bank_transaction(client, auth):
    txs = client.get("/api/transactions?start=2023-01-01&end=2023-12-31",
                     headers=auth).json()["items"]
    tx = txs[0]
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    r = client.post(f"/api/attachments/bank_transactions/{tx['id']}",
                    headers=auth,
                    files={"file": ("receipt.png", io.BytesIO(png), "image/png")})
    assert r.status_code == 201, r.text
    lst = client.get(f"/api/attachments/bank_transactions/{tx['id']}",
                     headers=auth).json()
    assert len(lst) == 1
    blob = client.get(f"/api/attachments/file/{lst[0]['id']}", headers=auth)
    assert blob.content[:4] == b"\x89PNG"


def test_yearend_zip_has_accountant_exports(client, auth):
    import zipfile
    z = client.get(f"/api/reports/yearend.zip?start={YEAR}-01-01&end={YEAR}-12-31",
                   headers=auth)
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert "11_gifi_s125.csv" in names
    assert "12_general_ledger_quickbooks.csv" in names
