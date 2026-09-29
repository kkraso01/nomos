"""Functional tests for multi-dimension case comparison."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login():
    p = f"sim{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def test_case_comparison_dimensions():
    h, _ = _login()
    for cid, body in [
        ("SIM-A", "Facts\nThe seller delivered defective machinery.\nProcedural history\nBuyer appealed.\nThe law\nBreach gives damages.\nHolding\nAppeal dismissed; damages.\nOrder\nCosts and damages."),
        ("SIM-B", "Facts\nThe contractor delivered defective materials.\nProcedural history\nClient appealed.\nThe law\nBreach sounds in damages.\nHolding\nDamages awarded.\nOrder\nDamages and costs."),
    ]:
        r = client.post("/corpus/judgment", headers=h, json={
            "canonical_id": cid, "title": "c", "court": "Supreme Court",
            "case_number": cid, "raw_text": body})
        assert r.status_code == 201, r.text

    out = client.post("/similarity/compare", headers=h,
                      json={"case_a": "SIM-A", "case_b": "SIM-B"}).json()
    assert out["ok"] is True
    dims = {s["dimension"]: s["score"] for s in out["similarity"]}
    assert set(dims) == {"LEGAL_ISSUE_SIMILARITY", "FACTUAL_SIMILARITY",
                         "PROCEDURAL_SIMILARITY", "STATUTORY_SIMILARITY", "REMEDY_SIMILARITY"}
    for d, s in dims.items():
        assert 0.0 <= s <= 1.0
    assert dims["REMEDY_SIMILARITY"] == 1.0  # both award damages + costs
    assert all(s["explanation"] for s in out["similarity"])

    # missing case -> 404
    assert client.post("/similarity/compare", headers=h,
                       json={"case_a": "SIM-A", "case_b": "NOPE"}).status_code == 404