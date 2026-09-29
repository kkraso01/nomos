"""Task-6: end-to-end lawyer research workflow = done-criteria acceptance.

A representative lawyer can, through the HTTP API:
create/open a matter; enter a research question with an optional relevant date;
receive ranked legislation + case authorities; see WHY each matched; inspect exact
evidence; see the historically applicable provision version; save authorities to
the matter; classify them supporting/adverse/neutral; ask a grounded research
question; receive an evidence-linked answer using only verified retrieved
authorities; and inspect every supporting authority.
"""
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
    p = f"lw{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()


def _ingest(src_id):
    from app.services.pipeline import run_pipeline
    s = SessionLocal()
    run_pipeline(s, source_id=src_id, ingest_key="lw-law", title="Winding up Law",
                 kind="legislation", jurisdiction="CY", canonical_id="ELW",
                 effective_from="2020-01-01T00:00:00Z",
                 raw_payload="Article 1. Short title.\n(1) This Law may be cited as the Winding up Law.\n"
                             "Article 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency.\n(2) The court may appoint a liquidator.")
    run_pipeline(s, source_id=src_id, ingest_key="lw-jud", kind="judgment",
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
def test_full_lawyer_research_workflow():
    src = _cleared_source(); _ingest(src)
    h, tok = _login()

    # 1) create/open a matter
    mid = client.post("/matters", headers=h, json={"title": "Insolvency Matter"}).json()["id"]

    # 2) research question with a relevant date -> ranked authorities
    rv = client.get("/research/vertical?q=company%20wound%20up%20in%20the%20event%20of%20insolvency&as_of=2021-06-01T00:00:00Z&limit=10",
                    headers=h).json()
    assert rv["count"] >= 1
    leg = next((r for r in rv["results"] if "law-ELW-art-5" in r["canonical_ref"]), None)
    assert leg is not None
    # 3) why + evidence + applicable version
    assert leg["why"], "result must say why it matched"
    assert leg["evidence"], "exact provision evidence must be exposed"
    # historically applicable version for the event date is exposed and resolved
    assert leg["temporal"] and isinstance(leg["temporal"]["applicable_version"], int)
    assert leg["temporal"]["applicable_version"] >= 1
    assert leg["detail"]["authority_type"] == "legislation"

    # 4) save authority to the matter, classify supporting
    save = client.put(f"/matters/{mid}/authorities", headers=h, json={
        "canonical_ref": "law-ELW-art-5", "authority_type": "legislation", "jurisdiction": "CY",
        "classification": "supporting", "matter_issue": "winding up"})
    assert save.status_code == 201 and save.json()["classification"] == "supporting"

    # add a neutral authority (folder coverage)
    client.put(f"/matters/{mid}/authorities", headers=h, json={
        "canonical_ref": "judgment-1/2018", "authority_type": "judgment",
        "classification": "neutral"})

    # 5) grounded research question -> evidence-linked answer from verified authorities
    ga = client.post("/assistant/ask", headers=h, json={
        "query": "company wound up in the event of insolvency", "matter_id": mid}).json()
    assert ga["supported"] is True
    assert ga["answer"] and ga["propositions"]
    assert all(p["kind"] == "SOURCE FACT" for p in ga["propositions"])
    # 6) inspect every supporting authority
    assert ga["authorities"] and all(a["canonical_ref"] and a["evidence"] for a in ga["authorities"])

    # 7) authority folders reflect supporting/neutral
    folders = client.get(f"/matters/{mid}/authorities/folders", headers=h).json()["folders"]
    assert any(a["canonical_ref"] == "law-ELW-art-5" for a in folders.get("supporting", []))
    assert any(a["canonical_ref"] == "judgment-1/2018" for a in folders.get("neutral", []))

    # tenant isolation: a second org cannot open this matter's authorities
    hB, _ = _login()
    assert client.get(f"/matters/{mid}/authorities", headers=hB).status_code == 404