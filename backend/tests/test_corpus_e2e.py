"""Functional tests for temporal legislation, judgments and reference parsing."""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.references import parse_reference

client = TestClient(app)


def _login():
    prefix = f"corp{uuid.uuid4().hex[:6]}"
    r = client.post("/auth/register", json={"org": {"name": prefix, "slug": prefix},
                                            "admin_email": f"{prefix}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_temporal_legislation_resolution():
    h = _login()
    base = "Article 1. Short title.\n(1) This Law may be cited as X.\nArticle 2. Interpretation.\nIn this Law aircraft means a machine supported by the air."
    amended = "Article 1. Short title.\n(1) This Law may be cited as X.\nArticle 2. Interpretation.\nIn this Law aircraft means a machine supported in the atmosphere."
    cid = f"CY-LAW-{uuid.uuid4().hex[:6]}"
    v1 = {"canonical_id": cid, "title": "X Law", "jurisdiction": "CY",
          "raw_text": base, "effective_from": "2020-01-01T00:00:00Z"}
    v2 = {"canonical_id": cid, "title": "X Law", "jurisdiction": "CY",
          "raw_text": amended, "effective_from": "2022-06-01T00:00:00Z"}
    assert client.post("/corpus/legislation", headers=h, json=v1).status_code == 201
    r2 = client.post("/corpus/legislation", headers=h, json=v2).json()
    assert r2["is_new_version"] is True

    a2021 = client.get(f"/corpus/legislation/{cid}/as-of", headers=h,
                       params={"as_of": "2021-06-01T00:00:00Z"}).json()
    assert a2021["version_number"] == 1
    assert "supported by the air" in a2021["nodes"][-1]["text"]

    a2023 = client.get(f"/corpus/legislation/{cid}/as-of", headers=h,
                       params={"as_of": "2023-06-01T00:00:00Z"}).json()
    assert a2023["version_number"] == 2
    assert "supported in the atmosphere" in a2023["nodes"][-1]["text"]

    # identical re-ingest does not create a new version
    r3 = client.post("/corpus/legislation", headers=h, json=v1).json()
    assert r3["is_new_version"] is False


def test_judgment_ingest():
    h = _login()
    j = client.post("/corpus/judgment", headers=h, json={
        "canonical_id": f"CJ-{uuid.uuid4().hex[:6]}", "title": "Mavridis v Demetriou",
        "court": "Supreme Court of Cyprus", "case_number": "45/2018",
        "judgment_date": "2019-03-15T00:00:00Z",
        "raw_text": "The plaintiff appealed.\nThe court held that the contract was valid.\nCosts to the defendant."}).json()
    assert j["version_number"] == 1 and j["is_new_version"] is True


def test_reference_parser_deterministic():
    p = parse_reference("Article 5 of Law 261 of 2004")
    assert p.kind == "legislation_article" and p.article_number == "5" and p.law_number == "261"
    p2 = parse_reference("ECLI:CY:AD:2019:A123")
    assert p2.kind == "judgment" and p2.ecli == "ECLI:CY:AD:2019:A123"
    p3 = parse_reference("Civil Appeal 45/2018")
    assert p3.kind == "judgment" and p3.case_number == "45/2018"
    p4 = parse_reference("Some ordinary prose about liability")
    assert p4.kind == "unknown"