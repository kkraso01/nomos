"""Task-5: deterministic provision cross-references with exact spans."""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.references import extract_references

client = TestClient(app)


def _login():
    p = f"xref{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def test_extract_references_forms():
    r = extract_references("Άρθρο 15(2)(α), ΚΕΦ. 6, Κεφ. 148, Ν. 123(I)/2020, ECLI:CY:AD:2019:A1, 45/2018")
    kinds = {x["kind"] for x in r}
    assert "article" in kinds and "chapter" in kinds and "law" in kinds
    assert "judgment_ecli" in kinds and "judgment_case" in kinds
    art = next(x for x in r if x["kind"] == "article")
    assert art["article"] == "15" and art["sub"] == "2" and art["para"] == "α"
    assert (art["end"] - art["start"]) == len(art["text"])


def test_scan_creates_internal_provision_links():
    h, _ = _login()
    cid = f"XR-{uuid.uuid4().hex[:6]}"
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": cid, "title": "X", "jurisdiction": "CY",
        "raw_text": "Article 5. Winding up.\n(1) grounds for winding up.\n"
                    "Article 12. References.\n(1) subject to άρθρο 15(3).\n"
                    "Article 15. Interpretation.\n(1) definitions.\n"
                    "Article 20. Cross links.\n(1) see Article 5."})
    nodes = client.get(f"/corpus/legislation/{cid}/as-of", headers=h).json()["nodes"]
    n12 = next(n["id"] for n in nodes if n["node_type"] == "ARTICLE" and n["number"] == "12")
    n15 = next(n["id"] for n in nodes if n["node_type"] == "ARTICLE" and n["number"] == "15")
    n20 = next(n["id"] for n in nodes if n["node_type"] == "ARTICLE" and n["number"] == "20")

    out = client.post(f"/citation/scan-provision-refs?canonical_id={cid}", headers=h).json()
    assert out["created"] >= 1

    refs12 = client.get(f"/citation/provision/{n12}", headers=h).json()
    assert any(x["target_node_id"] == n15 and x["span"] is not None for x in refs12["references_out"])

    refs20 = client.get(f"/citation/provision/{n20}", headers=h).json()
    assert any(x["target_node_id"] == nodes[0]["id"] for x in refs20["references_out"])  # Article 5