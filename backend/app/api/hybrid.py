from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..config import settings
from .. import models as _models
import redis as _redis_mod
_redis = _redis_mod.Redis.from_url(settings.redis_url, decode_responses=True)
from ..core.tenancy import require_org
from ..core import audit
from ..services.hybrid import hybrid_search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/hybrid")
def hybrid(q: str = Query(...), mode: str = Query("hybrid"), limit: int = Query(10, le=50),
           as_of: datetime | None = Query(None),
           ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    if settings.enforce_usage_limits:
        from ..core.tiers import tier_for_plan, check_usage
        org = db.get(_models.Org, ctx["org_id"])
        tier = tier_for_plan(org.plan if org else None)
        u = check_usage(_redis, ctx["org_id"], tier, "search_per_day")
        if not u["allowed"]:
            from fastapi import HTTPException
            raise HTTPException(429, "Daily free search allowance reached; upgrade to NOMOS Pro for unlimited research.")
    out = hybrid_search(db, q, as_of=as_of, limit=limit, mode=mode)
    audit.record_audit(db, action="search.hybrid", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, detail={"q": q, "mode": mode,
                                                             "count": out["count"]})
    return out