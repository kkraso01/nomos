"""Functional tests for the grounded research assistant."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login():
    p = f"rs{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed(h):
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": "261", "title": "Insolvency Law of 2015", "language": "en",
        "raw_text": "Article 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency.\n(2) The court may appoint a liquidator."})


def test_grounded_supported():
    h = _login()
    _seed(h)
    out = client.post("/research/query", headers=h, json={"query": "Company wound up on insolvency"}).json()
    assert out["supported"] is True
    assert out["authorities"] and out["answer"]
    # answer anchored in retrieved text, not fabricated
    assert "supporting text states" in out["answer"]


def test_unsupported_path():
    h = _login()
    _seed(h)
    out = client.post("/research/query", headers=h,
                      json={"query": "quantum teleportation of zebras"}).json()
    assert out["supported"] is False
    assert "No sufficiently supported authority" in out["answer"]


def test_citation_validation():
    h = _login()
    _seed(h)
    ok = client.post("/research/validate-citation", headers=h,
                     json={"text": "Article 5 of Law 261 of 2015"}).json()
    assert ok["parsed"] is True and ok["exists"] is True
    bad = client.post("/research/validate-citation", headers=h,
                      json={"text": "Article 99 of Law 54321"}).json()
    assert bad["parsed"] is True and bad["exists"] is False