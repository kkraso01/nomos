"""Functional tests for matter authority workspace + follow notifications."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login():
    p = f"at{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_authority_workspace():
    h = _login()
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": "L99", "title": "T", "raw_text":
        "Article 3. Rule.\n(1) consequence."})
    ref = "law-L99-art-3"
    mid = client.post("/matters", headers=h, json={"title": "M"}).json()["id"]

    r = client.put(f"/matters/{mid}/authorities/{ref}", headers=h,
                   json={"canonical_ref": ref, "state": "relied_on", "note": "key"})
    assert r.status_code == 200 and r.json()["state"] == "relied_on"
    client.put(f"/matters/{mid}/authorities/{ref}", headers=h,
               json={"canonical_ref": ref, "state": "adverse"})
    lst = client.get(f"/matters/{mid}/authorities", headers=h).json()["authorities"]
    assert any(a["state"] == "adverse" for a in lst)

    # nonexistent authority rejected
    assert client.put("/matters/{}/authorities/fake".format(mid), headers=h,
                      json={"canonical_ref": "fake", "state": "relied_on"}).status_code == 400


def test_follow_notifications():
    h = _login()
    client.post("/follow", headers=h, json={"follow_key": "topic:covid", "label": "c"})
    client.post("/follow/notify", headers=h, json={"follow_key": "topic:covid"})
    notif = client.get("/follow/notifications", headers=h).json()["notifications"]
    assert len(notif) >= 1 and notif[0]["kind"] == "followed_update"