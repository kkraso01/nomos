"""Functional tests for audit export, firm knowledge and drafting."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _org(prefix):
    p = f"{prefix}{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_audit_export():
    h = _org("aexp")
    js = client.get("/audit/export?format=json", headers=h).json()
    assert js["count"] >= 1 and any(r["action"] == "org.register" for r in js["records"])
    csv = client.get("/audit/export?format=csv", headers=h)
    assert csv.status_code == 200 and "action" in csv.text


def test_firm_knowledge_tenancy():
    hA = _org("fA")
    hB = _org("fB")
    client.post("/firm/precedents", headers=hA, json={
        "title": "Confidential Clause", "kind": "work_product",
        "body": "all proprietary info is confidential under this agreement"})
    rA = client.get("/firm/search?q=confidential", headers=hA).json()
    assert rA["count"] == 1
    r = rA["results"][0]
    assert r["internal"] is True and r["primary_authority"] is False
    rB = client.get("/firm/search?q=confidential", headers=hB).json()
    assert rB["count"] == 0


def test_draft_memo_verification():
    h = _org("drf")
    # seed a law so one citation verifies
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": "261", "title": "Insolvency Law", "raw_text":
        "Article 5. Winding up.\n(1) A company may be wound up on insolvency."})
    out = client.post("/draft/memo", headers=h, json={
        "facts": ["liable"], "issues": ["insolvency?"],
        "citations": ["Article 5 of Law 261 of 2015", "Article 99 of Law 54321"]}).json()
    assert out["status"] == "draft" and out["lawyer_review_required"] is True
    assert [v["cite"] for v in out["verified_citations"]] == ["Article 5 of Law 261 of 2015"]
    assert out["nonexistent_citations_rejected"] == ["Article 99 of Law 54321"]