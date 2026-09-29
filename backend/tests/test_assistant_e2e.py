"""Task-4: grounded research assistant — provenance-first, extractive, no fabrication."""
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
    p = f"as{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def _ingest(src_id):
    from app.services.pipeline import run_pipeline
    s = SessionLocal()
    run_pipeline(s, source_id=src_id, ingest_key="as-law", title="Winding up Law",
                 kind="legislation", jurisdiction="CY", canonical_id="ELW",
                 raw_payload="Article 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency.\n(2) The court may appoint a liquidator.")
    run_pipeline(s, source_id=src_id, ingest_key="as-jud", kind="judgment",
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
def test_supported_answer_is_extractive_with_source_fact_provenance():
    src = _cleared_source(); _ingest(src)
    h, tok = _login()
    r = client.post("/assistant/ask", headers=h, json={
        "query": "company wound up in the event of insolvency"})
    assert r.status_code == 200
    body = r.json()
    assert body["supported"] is True
    # every authority is inspectable (canonical_ref + evidence)
    assert body["authorities"] and all(a["canonical_ref"] and a["evidence"] for a in body["authorities"])
    # propositions are verbatim SOURCE FACT
    assert body["propositions"] and all(p["kind"] == "SOURCE FACT" for p in body["propositions"])
    # the answer is extractive from the retrieved evidence (no invented prose/ECLI)
    joined = " ".join(e["text"] for a in body["authorities"] for e in (a["evidence"] or []) if e.get("text"))
    assert body["answer"].strip()
    # extractive: every content bigram of the answer appears in the retrieved evidence
    # (collapse whitespace so paragraph boundaries don't break the exact-verbatim check)
    import re as _re
    jl = _re.sub(r"\s+", " ", joined).lower()
    toks = _re.sub(r"\s+", " ", body["answer"]).lower().split()
    assert all(" ".join(toks[i:i+2]) in jl for i in range(len(toks) - 1)), "answer must be extractive"
    assert "ECLI:" not in body["answer"]
    # model overlay is clearly labelled inference, not legal fact
    assert body["model_inference"]["kind"] == "MODEL_INFERENCE"
    assert set(body["provenance_legend"]) == {"SOURCE FACT", "STRUCTURED EXTRACTION",
                                              "MODEL INFERENCE", "LAWYER DECISION"}


@needs_model
def test_insufficient_evidence_returns_none_and_no_fabrication():
    src = _cleared_source(); _ingest(src)
    h, _ = _login()
    r = client.post("/assistant/ask", headers=h, json={"query": "quantum teleportation liability"})
    assert r.status_code == 200
    body = r.json()
    assert body["supported"] is False
    assert body["answer"] is None
    assert "No sufficiently supported authority" in body["message"]


@needs_model
def test_adverse_surfaced_and_temporal_preserved():
    src = _cleared_source(); _ingest(src)
    from datetime import datetime, timezone as _tz
    from app.db import SessionLocal
    from app.services.assistant import grounded_answer
    from app.models.authority import classify_authority
    from app import models
    from app.services.pipeline import run_pipeline  # noqa: F401 (ensure importable)
    h, tok = _login()
    s = SessionLocal()
    org = uuid.UUID(tok["org_id"])
    m = models.Matter(org_id=org, title="M"); s.add(m); s.commit(); s.refresh(m); mid = m.id
    classify_authority(s, org_id=org, matter_id=mid, canonical_ref="law-ELW-art-5",
                       classification="adverse", saved_by=uuid.UUID(tok["user_id"]))
    body = grounded_answer(s, query="company wound up in the event of insolvency",
                           matter_id=mid, org_id=org)
    assert any(a["canonical_ref"] == "law-ELW-art-5" and a["provenance"] == "LAWYER DECISION"
               for a in body["adverse"])
    tb = grounded_answer(s, query="company wound up in the event of insolvency",
                         as_of=datetime(2021, 6, 1, tzinfo=_tz.utc), org_id=org)
    assert any(a.get("temporal") for a in tb["authorities"] if a.get("temporal"))
    s.close()