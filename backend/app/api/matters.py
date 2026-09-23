import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..core.tenancy import require_org, get_current_user
from ..core import audit, idempotency
from ..schemas import MatterCreate, MatterOut

router = APIRouter(prefix="/matters", tags=["matters"])


def _get_matter_for_org(db, org_id: uuid.UUID, matter_id: uuid.UUID) -> models.Matter:
    m = db.query(models.Matter).filter(
        models.Matter.id == matter_id, models.Matter.org_id == org_id).first()
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Matter not found")
    return m


@router.post("", response_model=MatterOut, status_code=201)
def create_matter(payload: MatterCreate,
                  request: Request,
                  ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    org_id = ctx["org_id"]

    def _create():
        matter = models.Matter(org_id=org_id, title=payload.title, description=payload.description)
        db.add(matter)
        db.commit()
        db.refresh(matter)
        audit.record_audit(db, action="matter.create", org_id=org_id,
                           actor_user_id=ctx["user"].id, resource_type="matter", resource_id=matter.id)
        return {"id": str(matter.id), "org_id": str(matter.org_id), "title": matter.title,
                "description": matter.description, "created_at": matter.created_at.isoformat()}

    key = request.headers.get("Idempotency-Key")
    if key:
        return idempotency.idempotent_execute(db, f"matter:{key}", _create)
    return _create()


@router.get("", response_model=list[MatterOut])
def list_matters(ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    return db.query(models.Matter).filter(models.Matter.org_id == ctx["org_id"]).all()


@router.get("/{matter_id}", response_model=MatterOut)
def get_matter(matter_id: uuid.UUID, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    return _get_matter_for_org(db, ctx["org_id"], matter_id)