"""Task-5: server-side subscription usage enforcement (FREE limited, PRO unlimited)."""
import uuid
import redis
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.core.tiers import check_usage, tier_for_plan, usage_limit

client = TestClient(app)


def _org(plan):
    p = f"ti{uuid.uuid4().hex[:5]}"
    r = client.post("/auth/register", json={"org": {"name": p, "slug": p},
                                            "admin_email": f"{p}@x.com", "admin_password": "pw123"})
    tok = r.json()
    tok["plan"] = plan
    return {"Authorization": f"Bearer {tok['access_token']}"}, tok


def test_tier_mapping_and_limits():
    assert tier_for_plan("pro") == "pro"
    assert tier_for_plan("starter") == "free"
    assert usage_limit("free", "search_per_day") == 25
    assert usage_limit("pro", "search_per_day") is None


def test_check_usage_limits_free_and_unlimited_pro():
    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    oid = uuid.uuid4()
    # PRO: unlimited
    for _ in range(60):
        assert check_usage(r, oid, "pro", "search_per_day")["allowed"] is True
    # FREE: limited to 25/day
    r.delete(f"usage:{oid}:search_per_day:*")
    foid = uuid.uuid4()
    allowed = [check_usage(r, foid, "free", "search_per_day")["allowed"] for _ in range(26)]
    assert allowed[:25] == [True] * 25 and allowed[25] is False


def test_tier_endpoint():
    h, tok = _org("pro")
    body = client.get("/plan/tier", headers=h).json()
    assert body["tier"] == "free"  # registered orgs default starter -> free before plan set
    assert body["limits"]["search_per_day"] == 25
