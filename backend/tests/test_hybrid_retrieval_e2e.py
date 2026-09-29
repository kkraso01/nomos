"""Task-8: hybrid retrieval (dense+BM25+exact+temporal), feedback, eval metrics."""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models.core import LegalChunk
from app.services.embedding import get_provider, _ONNX
from app.services.eval_metrics import metrics

client = TestClient(app)
needs_model = pytest.mark.skipif(not os.path.exists(_ONNX) or not get_provider().available(),
                                 reason="embedding model not installed")


def _login():
    p = f"hyb{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _ingest_corpus(src_id):
    from app.services.pipeline import run_pipeline
    s = SessionLocal()
    run_pipeline(s, source_id=src_id, ingest_key="law-elw", kind="legislation",
                 jurisdiction="CY", canonical_id="ELW", title="Winding up Law",
                 effective_from="2020-01-01T00:00:00Z", raw_payload=
                 "Article 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency.\n(2) The court may appoint a liquidator.")
    run_pipeline(s, source_id=src_id, ingest_key="jud-grd", kind="judgment",
                 jurisdiction="CY", canonical_id="GRD-1", title="Alpha v Beta",
                 metadata={"court": "Supreme Court", "case_number": "1/2018"}, raw_payload=
                 "Facts\nThe seller failed to deliver the goods under the contract.\nHolding\nDamages awarded to the buyer.")
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
def test_hybrid_english_and_crosslingual():
    src = _cleared_source(); _ingest_corpus(src)
    h = _login()
    en = client.get("/search/hybrid?q=company%20wound%20up%20insolvency", headers=h).json()
    refs = {r["canonical_ref"] for r in en["results"]}
    assert any("law-ELW-art-5" in r for r in refs)
    el = client.get("/search/hybrid?q=εκκαθάριση%20εταιρείας%20αφερεγγυό", headers=h).json()
    elrefs = {r["canonical_ref"] for r in el["results"]}
    assert any("law-ELW" in r for r in elrefs)


@needs_model
def test_hybrid_temporal_applicable_version():
    src = _cleared_source(); _ingest_corpus(src)
    h = _login()
    # amend Article 5 effective 2022 -> v1 applicable in 2021
    client.post("/amendments", headers=h, json={
        "jurisdiction": "CY", "affected_canonical_id": "ELW", "operation": "REPLACE",
        "effective_date": "2022-06-01T00:00:00Z", "node_type": "ARTICLE", "node_number": "5",
        "new_text": "(1) A company may be wound up by the court in the event of insolvency at the company request."})
    out = client.get("/search/hybrid?q=winding%20up%201421&as_of=2021-06-01T00:00:00Z", headers=h).json()
    tinfos = [r["temporal"] for r in out["results"] if r["temporal"]]
    assert tinfos and any(t["applicable_version"] == 1 for t in tinfos)


def test_feedback_stored_no_finetune():
    h = _login()
    r = client.post("/feedback", headers=h, json={
        "query": "insolvency", "canonical_ref": "law-ELW-art-5", "judgement": "saved_as_authority"})
    assert r.status_code == 201 and r.json()["stored"] is True
    bad = client.post("/feedback", headers=h, json={
        "query": "q", "canonical_ref": "x", "judgement": "not-a-real-judgement"})
    assert bad.status_code == 400


def test_eval_metrics_shapes():
    m = metrics(["law-ELW-art-5", "judgment-GRD-1", "other-x"], {"law-ELW-art-5"})
    assert set(m) == {"recall@10", "recall@50", "mrr", "ndcg@10", "precision@10"}
    assert m["mrr"] == 1.0 and m["recall@10"] == 1.0
    assert metrics([], {"a"})["recall@10"] == 0.0

@needs_model
def test_hybrid_rerank_actually_executes():
    src = _cleared_source(); _ingest_corpus(src)
    from app.services.hybrid import hybrid_search
    s = SessionLocal()
    out = hybrid_search(s, "company wound up in the event of insolvency", limit=10,
                        enable_dense=True, enable_rerank=True)
    assert out["reranked"] is True
    scores = [r.get("rerank_score") for r in out["results"] if r.get("rerank_score") is not None]
    assert len(scores) >= 2, "expected >1 reranked result"
    assert scores == sorted(scores, reverse=True), "rerank must reorder by model score"
    s.close()


@needs_model
def test_eval_runs_on_live_corpus():
    src = _cleared_source(); _ingest_corpus(src)
    from app.services.hybrid import hybrid_search
    from app.services.eval_metrics import evaluate
    s = SessionLocal()

    def retriever(q):
        return [r["canonical_ref"] for r in hybrid_search(s, q, limit=50, enable_rerank=True)["results"]]

    rep = evaluate(retriever)
    res = rep["results"]
    en = res["company wound up in the event of insolvency"]["metrics"]
    # target retrieved in top-10 and ranked (honest, not gamed): recall@10=1.0, mrr>0
    assert en["recall@10"] == 1.0 and en["mrr"] > 0.0
    el = res["εκκαθάριση εταιρείας λόγω αφερεγγυότητας"]["metrics"]
    assert el["recall@10"] >= 0.5
    j = res["the seller failed to deliver goods under the contract"]["metrics"]
    assert j["recall@10"] == 1.0  # fixture ref matches ingested judgment-1/2018
    hard = res["quantum teleportation liability"]["metrics"]
    assert hard["recall@10"] == 0.0  # hard negative stays irrelevant
    s.close()
