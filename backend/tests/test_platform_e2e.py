"""End-to-end functional tests for the NOMOS platform foundation.

These exercise the real PostgreSQL / Redis / MinIO stack (via TestClient).
They are idempotent across runs by using unique emails/slugs.
"""
import io
import time
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _login(prefix: str):
    email = f"{prefix}@{uuid.uuid4().hex[:8]}.com"
    resp = client.post("/auth/register", json={
        "org": {"name": prefix, "slug": f"{prefix}-{uuid.uuid4().hex[:6]}"},
        "admin_email": email, "admin_password": "pw123",
    })
    assert resp.status_code == 200, resp.text
    return resp.json(), email


def test_seed_and_reuse_gate():
    tok, _ = _login("seedorg")
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    assert client.post("/sources/seed", headers=h).status_code == 200

    reg = client.get("/sources/registry", headers=h).json()
    by_name = {s["name"]: s for s in reg}
    cylaw = by_name["CyLaw"]
    eur = by_name["EUR-Lex / CELLAR"]

    # PERMISSION_REQUIRED source must be blocked from bulk/systematic ingestion.
    r = client.post(f"/sources/{cylaw['id']}/ingest", headers=h,
                    json={"canonical_key": "cylaw/x", "raw_payload": "x"})
    assert r.status_code == 403, r.text

    # Approved source ingests; identical re-ingest dedupes. (unique key per run)
    ckey = f"eu/t{uuid.uuid4().hex[:8]}"
    # In commercial-service mode an approved source still needs recorded clearance.
    r_blocked = client.post(f"/sources/{eur['id']}/ingest", headers=h, json={
        "canonical_key": ckey, "raw_payload": "Article 1 OK text"})
    assert r_blocked.status_code == 403, "approved source w/o commercial clearance must be blocked"

    # Record human clearance (audited) then ingest succeeds.
    cl = client.put(f"/sources/registry/{eur['id']}/clearance", headers=h, json={
        "commercial_reuse_allowed": True})
    assert cl.status_code == 200 and cl.json()["commercial_reuse_allowed"] is True

    r1 = client.post(f"/sources/{eur['id']}/ingest", headers=h, json={
        "canonical_key": ckey, "raw_payload": "Article 1 OK text"})
    assert r1.status_code == 201, r1.text
    body1 = r1.json()
    assert body1["created_new"] is True

    r2 = client.post(f"/sources/{eur['id']}/ingest", headers=h, json={
        "canonical_key": ckey, "raw_payload": "Article 1 OK text"})
    assert r2.status_code == 201
    assert r2.json()["deduplicated"] is True

    r3 = client.post(f"/sources/{eur['id']}/ingest", headers=h, json={
        "canonical_key": ckey, "raw_payload": "Article 1 CHANGED"})
    assert r3.status_code == 201
    assert r3.json()["version_changed"] is True


def test_tenancy_isolation():
    a, _ = _login("tenA")
    b, _ = _login("tenB")
    hA = {"Authorization": f"Bearer {a['access_token']}"}
    hB = {"Authorization": f"Bearer {b['access_token']}"}

    m = client.post("/matters", headers=hA, json={"title": "Secret Matter"}).json()
    mid = m["id"]

    # B cannot see A's matter.
    assert client.get(f"/matters/{mid}", headers=hB).status_code == 404
    assert client.get("/matters", headers=hB).json() == []

    # B cannot write private doc into A's namespace.
    f = {"file": ("doc.txt", io.BytesIO(b"secret"), "text/plain")}
    up = client.post("/documents/private", headers=hA, files=f).json()
    assert up["private"] is True and up["content_length"] == 6
    orgA = a["org_id"]
    r = client.get(f"/documents/private/{orgA}/doc.txt", headers=hB)
    assert r.status_code == 403

    # A can read own doc back.
    rA = client.get(f"/documents/private/{orgA}/doc.txt", headers=hA)
    assert rA.status_code == 200 and b"secret" in rA.content


def test_idempotent_matter_create():
    tok, _ = _login("idemorg")
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    key = f"k-{uuid.uuid4().hex}"
    body = {"title": "Retry Matter"}
    r1 = client.post("/matters", headers={**h, "Idempotency-Key": key}, json=body)
    r2 = client.post("/matters", headers={**h, "Idempotency-Key": key}, json=body)
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_ai_capability_request():
    tok, _ = _login("aiorg")
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    # Deterministic local L0 capability, no provider knowledge needed from caller.
    r = client.post("/ai/capability", headers=h, json={
        "capability": "CLASSIFY_DOCUMENT", "prompt": "This Act governs x"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["provider"] == "L0_LOCAL" and body["output"] == "statute"


def test_durable_background_job():
    tok, _ = _login("jobsorg")
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    j = client.post("/jobs", headers=h).json()
    jid = j["job_id"]
    status, waited = None, 0
    while waited < 15:
        status = client.get(f"/jobs/{jid}", headers=h).json()
        if status.get("status") in ("finished", "failed"):
            break
        time.sleep(1)
        waited += 1
    assert status["status"] == "finished", status
    assert status["result"]["final"] == "done"
    assert len(status["result"]["progress_log"]) == 5