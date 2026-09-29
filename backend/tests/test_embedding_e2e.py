"""Task-7: structural chunks + replaceable multilingual embeddings (e5-small ONNX)."""
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import SessionLocal
from app.models.core import LegalChunk
from app.services.embedding import get_provider, cosine, _ONNX

client = TestClient(app)
needs_model = pytest.mark.skipif(not os.path.exists(_ONNX) or not get_provider().available(),
                                 reason="embedding model not installed")


def _login():
    p = f"emb{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@needs_model
def test_embed_endpoint_dimensions():
    h = _login()
    r = client.post("/ai/embed", headers=h, json={
        "texts": ["the company may be wound up on insolvency",
                  "η εταιρεία δύναται να τεθεί υπό εκκαθάριση λόγω αφερεγγυότητας"],
        "is_query": False})
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["dimensions"] == 384
    assert len(body["vectors"]) == 2 and len(body["vectors"][0]) == 384
    cos = client.post("/ai/cosine", headers=h, json={"a": body["vectors"][0], "b": body["vectors"][1]})
    assert 0 <= cos.json()["similarity"] <= 1


@needs_model
def test_pipeline_persists_chunk_embeddings():
    from app.services.pipeline import run_pipeline
    from app.services.seed import seed_core, seed_sources_from_yaml
    s = SessionLocal()
    seed_core(s)
    from app.models import SourceRegistry
    seed_sources_from_yaml(s)
    src = s.query(SourceRegistry).filter_by(name="Cyprus National Open Data Portal").first()
    if src is None or not src.commercial_reuse_allowed:
        if src is None:
            raise RuntimeError("cleared source not seeded")
        src.commercial_reuse_allowed = True
        src.bulk_download_allowed = True
        src.adapter_enabled = True
        s.commit()
    cid = f"E-{uuid.uuid4().hex[:6]}"
    run_pipeline(s, source_id=src.id, ingest_key=cid, raw_payload=
                 "Article 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency.\n(2) The court may appoint a liquidator.",
                 canonical_id=cid, title="Embed Law", jurisdiction="CY")
    chunks = s.query(LegalChunk).filter_by(document_key=cid).all()
    assert chunks
    assert all(c.embedding is not None and len(c.embedding) == 384 for c in chunks)
    assert all(c.embedding_provider and c.embedding_model and c.embedding_dimensions == 384 for c in chunks)
    assert all(c.model_run_id is not None for c in chunks)
    s.close()