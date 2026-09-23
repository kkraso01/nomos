"""Functional tests for search: lexical EN/EL, exact-reference bypass."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login():
    prefix = f"s{uuid.uuid4().hex[:6]}"
    r = client.post("/auth/register", json={"org": {"name": prefix, "slug": prefix},
                                            "admin_email": f"{prefix}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _seed(h):
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": "261", "title": "Insolvency Law of 2015", "language": "en",
        "raw_text": "Article 1. Short title.\n(1) This Law is the Insolvency Law.\n"
                    "Article 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency."})
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": "GR-20", "title": "Περί Εταιρειών Νόμος", "language": "el",
        "raw_text": "Άρθρο 20. Εκκαθάριση εταιρείας.\n(1) Εταιρεία δύναται να τεθεί υπό εκκαθάριση λόγω αφερεγγυότητας."})


def test_lexical_english_and_greek():
    h = _login()
    _seed(h)
    en = client.get("/search", headers=h, params={"q": "insolvency"}).json()
    assert en["count"] >= 1 and any(r["kind"] == "legislation_node" for r in en["results"])

    el = client.get("/search", headers=h, params={"q": "εκκαθάριση"}).json()
    assert el["count"] >= 1
    assert any(r["language"] == "el" for r in el["results"])


def test_exact_reference_bypass():
    h = _login()
    _seed(h)
    r = client.get("/search", headers=h, params={"q": "Article 5 of Law 261 of 2015"}).json()
    top = r["results"][0]
    assert top["score"] == 100.0
    assert "Exact match" in top["reason_for_match"]
    assert top["metadata"].get("article") == "5"


def test_every_result_has_reason():
    h = _login()
    _seed(h)
    r = client.get("/search", headers=h, params={"q": "wound up"}).json()
    for res in r["results"]:
        assert res["reason_for_match"]