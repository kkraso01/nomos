"""Task-6: judgment enrichment with evidence-linked citations + graph expansion."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login():
    p = f"enr{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_judgment_structure_and_enrichment():
    h = _login()
    law_cid = f"EL-{uuid.uuid4().hex[:6]}"
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": law_cid, "title": "Winding up Law", "jurisdiction": "CY",
        "raw_text": "Article 5. Winding up.\n(1) A company may be wound up in the event of insolvency."})
    cid = f"CJ-{uuid.uuid4().hex[:6]}"
    client.post("/corpus/judgment", headers=h, json={
        "canonical_id": cid, "title": "X v Y", "jurisdiction": "CY",
        "court": "Supreme Court", "case_number": "5/2020",
        "raw_text": "Facts\nThe creditor relied on Article 5.\nLegal analysis\nThe court applied the provision.\nHolding\nThe company is wound up; see ECLI:CY:AD:2019:A11."})

    # structure: sections with paragraph-level units
    segs = client.get(f"/corpus/judgment/{cid}/segments", headers=h).json()["segments"]
    types = {s["section_type"] for s in segs}
    assert {"facts", "legal_analysis", "holding"} <= types
    facts = next(s for s in segs if s["section_type"] == "facts")
    assert facts["paragraphs"][0]["para_number"]
    assert "Article 5" in facts["paragraphs"][0]["text"]

    # enrich -> evidence-linked legislation link + case citation
    out = client.post(f"/citation/enrich-judgment?canonical_id={cid}&applicable_law_canonical_id={law_cid}",
                      headers=h).json()
    assert out["legislation_links_created"] >= 1
    assert out["case_citations_created"] >= 1

    # graph expansion exposes applied legislation + cited case with evidence paragraph
    exp = client.get(f"/citation/case/{cid}", headers=h).json()
    assert exp["cited"] and exp["cited"][0]["key"].startswith("ECLI:")
    assert exp["legislation_links"] and exp["legislation_links"][0]["relationship"] == "APPLIES"

    # treatment semantic edge starts REVIEW_REQUIRED (evidence-backed, not invented ok=false)
    t = client.post("/citation/treatment", headers=h, json={
        "source_case_key": cid, "target_case_key": "ECLI:CY:AD:2018:A7",
        "source_jurisdiction": "CY", "target_jurisdiction": "CY", "treatment": "DISTINGUISHES",
        "evidence_paragraph_id": facts["paragraphs"][0]["id"] if "id" in facts["paragraphs"][0] else None,
        "confidence": "0.9"}).json()
    assert t["treatment"] == "DISTINGUISHES" and t["review_status"] == "review_required"