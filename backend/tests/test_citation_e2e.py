"""Functional tests for the jurisdiction-agnostic legal graph (CaseCitation,
JudgmentLegislationLink, ProvisionCrossReference, CaseTreatment, expansion)."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login():
    p = f"cit{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed_judgment(h, cid, title, case_no, body):
    return client.post("/corpus/judgment", headers=h, json={
        "canonical_id": cid, "title": title, "jurisdiction": "CY",
        "court": "Supreme Court", "case_number": case_no, "raw_text": body}).status_code


def test_case_citation_and_treatment():
    h = _login()
    assert _seed_judgment(h, "JA", "A v B", "10/2019", "Facts\none.\nHolding\ntwo.")
    assert _seed_judgment(h, "JB", "C v D", "11/2020", "Facts\none.\nHolding\ntwo.")

    # case citation (CITES) — cross-jurisdiction target supported via key
    r = client.post("/citation/case", headers=h, json={
        "source_case_key": "JA", "source_jurisdiction": "CY",
        "target_case_key": "ECLI:CE:ECHR:2019:0123", "target_jurisdiction": "ECHR", "kind": "CITES"})
    assert r.status_code == 201 and r.json()["review_status"] == "review_required"

    # case treatment (semantic) — starts REVIEW_REQUIRED
    t = client.post("/citation/treatment", headers=h, json={
        "source_case_key": "JA", "source_jurisdiction": "CY",
        "target_case_key": "JB", "target_jurisdiction": "CY",
        "treatment": "DISTINGUISHES", "confidence": "0.9"}).json()
    assert t["treatment"] == "DISTINGUISHES" and t["review_status"] == "review_required"

    # graph expansion
    exp = client.get("/citation/case/JA", headers=h).json()
    cited_keys = [c["key"] for c in exp["cited"]]
    assert "ECLI:CE:ECHR:2019:0123" in cited_keys
    assert any(x["treatment"] == "DISTINGUISHES" for x in exp["treatments"])


def test_provision_reference_link():
    h = _login()
    cid = f"L{uuid.uuid4().hex[:6]}"
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": cid, "title": "T", "jurisdiction": "CY",
        "raw_text": "Article 5. Rule.\n(1) liability is established.\nArticle 15. Limitation.\n(1) claims are time-barred after six years."})
    nodes = client.get(f"/corpus/legislation/{cid}/as-of", headers=h).json()["nodes"]
    art5 = next(n["id"] for n in nodes if n["node_type"] == "ARTICLE" and n["number"] == "5")
    art15 = next(n["id"] for n in nodes if n["node_type"] == "ARTICLE" and n["number"] == "15")
    r = client.post("/citation/provision-reference", headers=h, json={
        "jurisdiction": "CY", "source_node_id": art15,
        "target_node_id": art5, "source_text": "subject to Article 5",
        "source_span_start": 0, "source_span_end": 18, "confidence": "high"})
    assert r.status_code == 201 and r.json()["confidence"] == "high"
    exp = client.get(f"/citation/provision/{art15}", headers=h).json()
    assert any(x["target_node_id"] == art5 for x in exp["references_out"])