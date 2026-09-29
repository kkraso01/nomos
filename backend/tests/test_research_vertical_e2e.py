"""Task-3: research vertical end-to-end (evidence + detail + save/classify into matter)."""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.services.embedding import get_provider, _ONNX

client = TestClient(app)
needs_model = pytest.mark.skipif(not os.path.exists(_ONNX) or not get_provider().available(),
                                 reason="embedding model not installed")


def _login():
    p = f"rv{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def _ingest(src_id):
    from app.services.pipeline import run_pipeline
    s = SessionLocal()
    run_pipeline(s, source_id=src_id, ingest_key="rv-law", title="Winding up Law",
                 kind="legislation", jurisdiction="CY", canonical_id="ELW",
                 raw_payload="Article 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency.\n(2) The court may appoint a liquidator.")
    run_pipeline(s, source_id=src_id, ingest_key="rv-jud", kind="judgment",
                 title="Alpha v Beta", jurisdiction="CY", canonical_id="GRD-1",
                 metadata={"court": "Supreme Court", "case_number": "1/2018"},
                 raw_payload="Facts\nThe seller failed to deliver goods under the contract.\nHolding\nDamages awarded to the buyer.")
    s.close()


def _cleared_source():
    from app.services.seed import seed_core, seed_sources_from_yaml
    from app.models import SourceRegistry
    s = SessionLocal()
    seed_core(s); seed_sources_from_yaml(s)
    src = s.query(SourceRegistry).filter_by(name="Cyprus National Open Data Portal").first()
    for a in ("commercial_reuse_allowed", "bulk_download_allowed", "adapter_enabled"):
        setattr(src, a, True)
    s.commit(); sid = src.id; s.close()
    return sid


@needs_model
def test_research_vertical_rows_with_evidence_and_detail():
    src = _cleared_source(); _ingest(src)
    h, _ = _login()
    out = client.get("/research/vertical?q=company%20wound%20up%20in%20the%20event%20of%20insolvency&limit=10",
                     headers=h).json()
    assert out["count"] >= 1
    top = next((r for r in out["results"] if "law-ELW-art-5" in r["canonical_ref"]), out["results"][0])
    assert top["why"], "result must explain why it matched"
    assert top["evidence"], "legislation result must expose exact provision evidence"
    assert top["detail"]["authority_type"] == "legislation"
    ev_text = top["evidence"][0]["text"].lower()
    assert ("wound up" in ev_text) or ("insolvency" in ev_text)

    # judgment result exposes paragraph evidence with spans
    j_out = client.get("/research/vertical?q=seller%20failed%20to%20deliver%20goods%20under%20the%20contract&limit=10",
                       headers=h).json()
    jtop = next((r for r in j_out["results"] if "judgment-1/2018" in r["canonical_ref"]), None)
    assert jtop is not None
    assert any(e["type"] == "judgment_paragraph" and e["text"] for e in jtop["evidence"])
    assert jtop["detail"]["court"] and jtop["detail"]["case_number"] == "1/2018"


@needs_model
def test_save_and_classify_authority_from_research():
    src = _cleared_source(); _ingest(src)
    h, tok = _login()
    mid = client.post("/matters", headers=h, json={"title": "M"}).json()["id"]
    out = client.get("/research/vertical?q=winding%20up%20insolvency&limit=10", headers=h).json()
    ref = next(r["canonical_ref"] for r in out["results"] if r["kind"] == "legislation_node")
    # save authority referencing the canonical result
    r = client.put(f"/matters/{mid}/authorities", headers=h, json={
        "canonical_ref": ref, "authority_type": "legislation", "jurisdiction": "CY",
        "classification": "supporting", "matter_issue": "winding up", "source_scope": "public"})
    assert r.status_code == 201 and r.json()["classification"] == "supporting"
    # classify adverse
    client.post(f"/matters/{mid}/authorities/classify", headers=h,
                json={"canonical_ref": ref, "classification": "adverse"})
    folders = client.get(f"/matters/{mid}/authorities/folders", headers=h).json()["folders"]
    assert any(a["canonical_ref"] == ref for a in folders.get("adverse", []))