"""Functional tests for entitlements (Phase J): server-side feature denial."""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.core.entitlements import is_entitled

client = TestClient(app)


def _login():
    p = f"ent{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_server_side_denial():
    h = _login()
    # starter plan: AI_REMOTE denied server-side
    r = client.post("/ai/capability", headers=h, json={
        "capability": "DRAFT_RESEARCH_MEMO", "prompt": "memo"})
    assert r.status_code == 403
    assert "not entitled" in r.json()["detail"]

    # upgrade to pro -> allowed (local route still deterministic)
    client.post("/plan", headers=h, json={"plan": "pro"})
    ent = client.get("/plan", headers=h).json()
    assert ent["plan"] == "pro" and ent["features"]["AI_REMOTE"] is True


def test_is_entitled_matrix():
    assert is_entitled("starter", "AI_REMOTE") is False
    assert is_entitled("pro", "AI_REMOTE") is True
    assert is_entitled("starter", "FIRM_KNOWLEDGE") is False
    assert is_entitled("standard", "FIRM_KNOWLEDGE") is True