"""Functional tests for the reranker (RERANK_SEARCH capability + /search rerank).

Skipped if the local ONNX model is not present (it is downloaded to HDD
models/reranker-minilm).
"""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

MODEL = "/mnt/jellyfin/Projects/NOMOS/models/reranker-minilm/onnx/model_qint8_arm64.onnx"
needs_model = pytest.mark.skipif(not os.path.exists(MODEL), reason="reranker model not installed")


def _login():
    p = f"rr{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@needs_model
def test_rerank_capability_orders_docs():
    h = _login()
    r = client.post("/ai/capability", headers=h, json={
        "capability": "RERANK_SEARCH", "prompt": "company wound up insolvency",
        "documents": [
            "A company may be wound up by the court in the event of insolvency and a liquidator appointed.",
            "The seller shall pay damages for breach of contract.",
            "Registration of trademarks and appellations of origin.",
        ]}).json()
    assert r["ok"] is True and r["provider"]
    scores = [x["score"] for x in r["scores"]]
    assert scores[0] > scores[1] > scores[2]
    assert "insolvency" in r["scores"][0]["doc"]


@needs_model
def test_search_rerank_flag():
    h = _login()
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": "261", "title": "Insolvency Law of 2015",
        "raw_text": "Article 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency.\n(2) The court may appoint a liquidator."})
    d = client.get("/search?q=insolvency&rerank=true", headers=h).json()
    assert d["reranked"] is True and d["count"] >= 1
    top = d["results"][0]
    assert "rerank_score" in top and top["rerank_score"] is not None