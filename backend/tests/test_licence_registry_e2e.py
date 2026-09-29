"""Task-2: licence-aware source registry + metadata + enforcement."""
import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

ALLOWED_STATUSES = {"APPROVED_OPEN", "APPROVED_WITH_ATTRIBUTION", "APPROVED_API_ONLY",
                    "PERMISSION_REQUIRED", "RESTRICTED", "UNKNOWN", "DISABLED"}


def _login():
    p = f"lic{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_registry_metadata_and_statuses():
    h = _login()
    assert client.post("/sources/seed", headers=h).status_code == 200
    reg = client.get("/sources/registry", headers=h).json()
    by_name = {s["name"]: s for s in reg}

    # all statuses valid
    for s in reg:
        assert s["reuse_status"] in ALLOWED_STATUSES

    # data.gov.cy confirmed CC BY 4.0 + commercial clearance via seed
    cy = by_name.get("Cyprus National Open Data Portal")
    assert cy is not None
    assert cy["licence"] == "CC BY 4.0"
    assert cy.get("commercial_reuse_allowed") is True

    # CyLaw is PERMISSION_REQUIRED
    assert by_name["CyLaw"]["reuse_status"] == "PERMISSION_REQUIRED"


def test_unknown_and_permission_required_blocked():
    h = _login()
    assert client.post("/sources/seed", headers=h).status_code == 200
    reg = client.get("/sources/registry", headers=h).json()
    by_name = {s["name"]: s for s in reg}
    cylaw = by_name["CyLaw"]
    gazette = by_name.get("Government Gazette of the Republic of Cyprus")
    # UNKNOWN is not permission
    if gazette:
        r = client.post(f"/sources/{gazette['id']}/ingest", headers=h,
                        json={"canonical_key": "gz/x", "raw_payload": "x"})
        assert r.status_code == 403
    r = client.post(f"/sources/{cylaw['id']}/ingest", headers=h,
                    json={"canonical_key": "cylaw/x", "raw_payload": "x"})
    assert r.status_code == 403


def test_commercial_clearance_required_for_approved():
    h = _login()
    assert client.post("/sources/seed", headers=h).status_code == 200
    reg = client.get("/sources/registry", headers=h).json()
    by_name = {s["name"]: s for s in reg}
    # EUR-Lex approved-open but no recorded commercial clearance -> blocked in paid mode
    eur = by_name["EUR-Lex / CELLAR"]
    if eur.get("commercial_reuse_allowed") is False:
        r = client.post(f"/sources/{eur['id']}/ingest", headers=h,
                        json={"canonical_key": "eu/x", "raw_payload": "x"})
        assert r.status_code == 403
        # record clearance (audited) -> then ingest
        cl = client.put(f"/sources/registry/{eur['id']}/clearance", headers=h,
                        json={"commercial_reuse_allowed": True})
        assert cl.status_code == 200 and cl.json()["commercial_reuse_allowed"] is True
        r2 = client.post(f"/sources/{eur['id']}/ingest", headers=h,
                         json={"canonical_key": f"eu/{uuid.uuid4().hex[:6]}", "raw_payload": "x"})
        assert r2.status_code == 201