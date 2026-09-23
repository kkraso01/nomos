"""Functional tests for procedural deadline calculation."""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.procedure import calculate_deadline, register_rule

client = TestClient(app)


def _login():
    p = f"pr{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_deadline_api():
    h = _login()
    bd = client.post("/procedure/rules", headers=h, json={
        "rule_key": "b1", "title": "appeal 14bd", "calculate_mode": "business_days",
        "base_days": 14, "law_ref": "Art 25"}).json()["rule_id"]
    cal = client.post("/procedure/rules", headers=h, json={
        "rule_key": "c1", "title": "30 days", "calculate_mode": "calendar_days",
        "base_days": 30}).json()["rule_id"]
    amb = client.post("/procedure/rules", headers=h, json={
        "rule_key": "a1", "title": "reasonable time", "calculate_mode": "calendar_days",
        "base_days": 30, "ambiguous": True}).json()["rule_id"]

    r1 = client.post("/procedure/deadline", headers=h, json={"rule_id": bd, "trigger_date": "2021-03-05"}).json()
    assert r1["certainty"] == "DETERMINED" and r1["deadline"] == "2021-03-26"

    r2 = client.post("/procedure/deadline", headers=h, json={"rule_id": cal, "trigger_date": "2021-03-05"}).json()
    assert r2["certainty"] == "DETERMINED" and r2["deadline"] == "2021-04-04"

    r3 = client.post("/procedure/deadline", headers=h, json={"rule_id": amb, "trigger_date": "2021-03-05"}).json()
    assert r3["certainty"] == "REVIEW_REQUIRED" and r3["deadline"] is None
    assert r3["reason"]


def test_business_day_skips_weekend():
    from app.db import SessionLocal as SL
    s = SL()
    r = register_rule(s, rule_key="bd2", title="t", jurisdiction="CY",
                     calculate_mode="business_days", base_days=1)
    res = calculate_deadline(r, __import__("datetime").date(2021, 3, 6))  # Saturday
    # 1 business day after Saturday = Monday 08-03-2021
    assert res["deadline"] == "2021-03-08"
    assert res["certainty"] == "DETERMINED"
    s.close()