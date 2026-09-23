"""Functional tests for the citation graph."""
import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.services.citation import CitationValidationError, create_edge

client = TestClient(app)
from app.db import SessionLocal


def _login():
    p = f"cit{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_citation_graph_via_api():
    h = _login()
    # seed a judgment + law article
    client.post("/corpus/judgment", headers=h, json={
        "canonical_id": f"CJ-{uuid.uuid4().hex[:6]}", "title": "X v Y",
        "case_number": "10/2019", "raw_text": "The court held X. Cited Article 5."})
    jref = f"judgment-10/2019"
    law_cid = f"L{uuid.uuid4().hex[:6]}"
    client.post("/corpus/legislation", headers=h, json={
        "canonical_id": law_cid, "title": "T", "language": "en",
        "raw_text": "Article 5. Rule.\n(1) liability is established."})
    lref = f"law-{law_cid}-art-5"

    e = {"source_kind": "judgment_node", "source_ref": jref,
         "target_kind": "legislation_node", "target_ref": lref, "treatment": "CITES"}
    assert client.post("/citation", headers=h, json=e).status_code == 201

    # nonexistent target rejected
    bad = dict(e, target_ref="law-999-zzz")
    assert client.post("/citation", headers=h, json=bad).status_code == 400

    # semantic without evidence rejected
    sem = dict(e, treatment="OVERRULES")
    assert client.post("/citation", headers=h, json=sem).status_code == 400
    sem["evidence"] = {"quote": "the provision is overruled"}
    r = client.post("/citation", headers=h, json=sem)
    assert r.status_code == 201 and r.json()["review_status"] == "review_required"

    # traversal
    t = client.get(f"/citation/node/judgment_node/{jref}", headers=h).json()
    assert t["counts"]["cited"] >= 2


def test_nonexistent_citation_blocked_at_service():
    from app.db import SessionLocal as SL
    s = SL()
    try:
        create_edge(s, source_kind="judgment_node", source_ref="nope",
                    target_kind="legislation_node", target_ref="nope2")
        raise AssertionError("should have raised")
    except CitationValidationError:
        pass
    finally:
        s.close()