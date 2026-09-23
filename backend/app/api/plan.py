from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..core.tenancy import require_org
from ..core.entitlements import is_entitled, FEATURES

router = APIRouter(prefix="/plan", tags=["entitlements"])


class PlanIn(BaseModel):
    plan: str  # starter / standard / pro / enterprise


def _get_org(db, org_id):
    return db.get(models.Org, org_id)


@router.post("")
def set_plan(payload: PlanIn, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = _get_org(db, ctx["org_id"])
    if org is None:
        from fastapi import HTTPException
        raise HTTPException(404, "org not found")
    org.plan = payload.plan
    db.commit()
    db.refresh(org)
    return {"org_id": str(org.id), "plan": org.plan}


@router.get("")
def get_entitlements(ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org = _get_org(db, ctx["org_id"])
    plan = org.plan if org else "starter"
    return {"plan": plan,
            "features": {f: is_entitled(plan or "starter", f) for f in sorted(FEATURES)}}