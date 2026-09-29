"""Task-4: temporal legislation + amendments as events."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login():
    p = f"amd{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _art5(nodes):
    return next(n["text"] for n in nodes if n["node_type"] == "ARTICLE" and n["number"] == "5")


def test_amendment_as_event_produces_applicable_version():
    h = _login()
    cid = f"AL-{uuid.uuid4().hex[:6]}"
    v1 = "Article 1. Short title.\n(1) This Law may be cited as the A Law.\nArticle 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency."
    assert client.post("/corpus/legislation", headers=h, json={
        "canonical_id": cid, "title": "A Law", "jurisdiction": "CY",
        "raw_text": v1, "effective_from": "2020-01-01T00:00:00Z"}).status_code == 201

    # amend Article 5 effective 2022-06-01
    am = client.post("/amendments", headers=h, json={
        "jurisdiction": "CY", "affected_canonical_id": cid, "operation": "REPLACE",
        "effective_date": "2022-06-01T00:00:00Z", "node_type": "ARTICLE", "node_number": "5",
        "new_text": "(1) A company may be wound up by the court in the event of insolvency at the company request.\n(2) The court may appoint a liquidator or administrator."}).json()
    assert am["operation"] == "REPLACE"
    assert "insolvency" in am["previous_text"]

    # as-of 2021 -> original (v1); as-of 2023 -> amended
    a2021 = client.get(f"/corpus/legislation/{cid}/as-of", headers=h, params={"as_of": "2021-06-01T00:00:00Z"}).json()
    a2023 = client.get(f"/corpus/legislation/{cid}/as-of", headers=h, params={"as_of": "2023-06-01T00:00:00Z"}).json()
    assert "at the company request" not in _art5(a2021["nodes"])
    assert "at the company request" in _art5(a2023["nodes"])
    assert a2021["version_number"] < a2023["version_number"]

    # amendment recorded as an event with evidence + dates
    l = client.get(f"/amendments/{cid}", headers=h).json()["amendments"]
    assert len(l) == 1 and l[0]["operation"] == "REPLACE"
    assert l[0]["effective_date"].startswith("2022")

    # diff between applicable and current
    d = client.get(f"/amendments/{cid}/diff/{a2021['version_id']}/{a2023['version_id']}", headers=h).json()
    assert d["changed_nodes"] >= 1
    assert d["unified_diff"] or d["changes"]