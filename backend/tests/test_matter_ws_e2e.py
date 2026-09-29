"""Functional tests for matter workspace: doc upload, extraction, chronology, review."""
import io
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
TXT = ("The contract provided that the Seller shall pay EUR 5,000.00. "
       "On 15/03/2021 the buyer delivered the goods. "
       "On 20/04/2021 the Warehouse Co signed the acceptance. "
       "Achilleas Vasilou delivered on 30/07/2021.")


def _org(prefix):
    p = f"{prefix}{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def test_matter_workspace_flow():
    h, _ = _org("mws")
    mid = client.post("/matters", headers=h, json={"title": "Matter X"}).json()["id"]
    doc = client.post(f"/matters/{mid}/documents", headers=h,
                      files={"file": ("c.txt", io.BytesIO(TXT.encode()), "text/plain")}).json()
    did = doc["document_id"]
    assert doc["extracted_text_chars"] == len(TXT)

    r = client.post(f"/matters/{mid}/documents/{did}/extract", headers=h).json()
    assert r["proposed_facts"] >= 3 and r["proposed_events"] >= 2

    facts = client.get(f"/matters/{mid}/facts", headers=h).json()["facts"]
    party = next(f for f in facts if f["kind"] == "party")
    dec = client.post(f"/matters/{mid}/facts/{party['id']}/decision", headers=h,
                      json={"status": "accepted"})
    assert dec.status_code == 200 and dec.json()["status"] == "accepted"

    chron = client.get(f"/matters/{mid}/chronology", headers=h).json()["events"]
    dates = [e["event_date"] for e in chron]
    assert dates == sorted(dates)
    date_strings = " ".join(e["event_date"] for e in chron)
    assert "2021-03-15" in date_strings and "2021-07-30" in date_strings


def test_matter_cross_org_isolation():
    hA, _ = _org("mwA")
    hB, _ = _org("mwB")
    mid = client.post("/matters", headers=hA, json={"title": "Private"}).json()["id"]
    # B cannot upload into A's matter
    assert client.post(f"/matters/{mid}/documents", headers=hB,
                       files={"file": ("c.txt", io.BytesIO(b"x"), "text/plain")}).status_code == 404
    # B cannot read A's facts
    assert client.get(f"/matters/{mid}/facts", headers=hB).status_code == 404
    assert client.get(f"/matters/{mid}/chronology", headers=hB).status_code == 404

def test_issue_spotting_from_accepted_facts():
    import uuid
    p = f"iss{uuid.uuid4().hex[:5]}"
    rr = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                             "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    h2 = {"Authorization": f"Bearer {rr.json()['access_token']}"}
    mid = client.post("/matters", headers=h2, json={"title": "M"}).json()["id"]
    doc = client.post(f"/matters/{mid}/documents", headers=h2,
                      files={"file": ("t.txt", io.BytesIO(b"The company became insolvent and the seller shall pay damages for breach."), "text/plain")}).json()
    client.post(f"/matters/{mid}/documents/{doc['document_id']}/extract", headers=h2)
    # accept all proposed facts
    for f in client.get(f"/matters/{mid}/facts", headers=h2).json()["facts"]:
        client.post(f"/matters/{mid}/facts/{f['id']}/decision", headers=h2, json={"status": "accepted"})
    issues = client.post(f"/matters/{mid}/suggest-issues", headers=h2).json()["issues"]
    texts = [i["text"] for i in issues]
    assert any("insolvent" in t for t in texts)
    assert any("damages" in t for t in texts)


def test_pdf_matter_document_parsing():
    import uuid
    try:
        import pymupdf
    except Exception:
        import fitz as pymupdf
    p = f"pdf{uuid.uuid4().hex[:5]}"
    rr = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                             "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    h3 = {"Authorization": f"Bearer {rr.json()['access_token']}"}
    mid = client.post("/matters", headers=h3, json={"title": "P"}).json()["id"]

    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((72, 72), "The seller shall pay damages for the breach on 05/09/2021.")
    data = doc.tobytes(); doc.close()

    up = client.post(f"/matters/{mid}/documents", headers=h3,
                     files={"file": ("c.pdf", io.BytesIO(data), "application/pdf")}).json()
    assert up["extracted_text_chars"] > 0
    did = up["document_id"]
    ex = client.post(f"/matters/{mid}/documents/{did}/extract", headers=h3).json()
    assert ex["proposed_events"] >= 1
    dates = " ".join(e["event_date"] for e in client.get(f"/matters/{mid}/chronology", headers=h3).json()["events"])
    assert "2021-09-05" in dates
