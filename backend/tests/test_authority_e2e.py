"""Tests for the matter authority model/workflow (task-2):
lawyer-controlled classification, system suggestion = MODEL_INFERENCE, folders,
tenant deny-by-default."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _org(prefix):
    p = f"at{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def _matter(h):
    return client.post("/matters", headers=h, json={"title": "M"}).json()["id"]


def test_save_classify_suggest_folders():
    h, _ = _org("a")
    mid = _matter(h)
    ref = "law-ELW-art-5"

    # save authority referencing canonical ref with a lawyer classification
    r = client.put(f"/matters/{mid}/authorities", headers=h, json={
        "canonical_ref": ref, "authority_type": "legislation", "jurisdiction": "CY",
        "source_scope": "public", "classification": "supporting", "matter_issue": "insolvency",
        "evidence": {"paragraph": "5", "span": [0, 20]}})
    assert r.status_code == 201
    b = r.json()
    assert b["classification"] == "supporting" and b["canonical_ref"] == ref
    assert b["saved_by"] and b["evidence"]["span"] == [0, 20]

    # lawyer re-classifies as adverse
    r2 = client.post(f"/matters/{mid}/authorities/classify", headers=h, json={
        "canonical_ref": ref, "classification": "adverse"})
    assert r2.status_code == 200 and r2.json()["classification"] == "adverse"

    # system SUGGESTS supporting (MODEL_INFERENCE): must NOT change lawyer decision
    r3 = client.post(f"/matters/{mid}/authorities/suggest", headers=h, json={
        "canonical_ref": ref, "suggestion": "supporting"})
    assert r3.status_code == 200
    assert r3.json()["suggestion"] == "supporting"
    assert r3.json()["suggestion_provenance"] == "MODEL_INFERENCE"
    assert r3.json()["classification"] == "adverse"  # lawyer decision preserved

    # list + folder views
    lst = client.get(f"/matters/{mid}/authorities", headers=h).json()
    assert len(lst["authorities"]) == 1 and lst["authorities"][0]["classification"] == "adverse"
    fcls = client.get(f"/matters/{mid}/authorities?classification=adverse", headers=h).json()
    assert fcls["count"] == 1
    folders = client.get(f"/matters/{mid}/authorities/folders", headers=h).json()["folders"]
    assert any(ref == a["canonical_ref"] for a in folders.get("adverse", []))


def test_authority_tenant_isolation():
    hA, _ = _org("aA")
    hB, _ = _org("aB")
    mid = _matter(hA)
    client.put(f"/matters/{mid}/authorities", headers=hA, json={
        "canonical_ref": "law-ELW-art-5", "classification": "supporting"})
    # B cannot see A's matter or its authorities
    assert client.get(f"/matters/{mid}/authorities/folders", headers=hB).status_code == 404
    assert client.get(f"/matters/{mid}/authorities", headers=hB).status_code == 404


def test_follow_notifications():
    h, _ = _org("af")
    client.post("/follow", headers=h, json={"follow_key": "topic:covid", "label": "c"})
    client.post("/follow/notify", headers=h, json={"follow_key": "topic:covid"})
    notif = client.get("/follow/notifications", headers=h).json()["notifications"]
    assert len(notif) >= 1 and notif[0]["kind"] == "followed_update"