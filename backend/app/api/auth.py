from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..core import security, audit
from ..schemas import (
    RegisterRequest, LoginRequest, TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Create an organisation, its owner user and membership in one step."""
    if db.query(models.User).filter_by(email=str(req.admin_email).lower()).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    org = models.Org(name=req.org.name, slug=req.org.slug,
                     remote_ai_policy=req.org.remote_ai_policy)
    db.add(org)
    db.flush()

    user = models.User(
        email=str(req.admin_email).lower(),
        hashed_password=security.hash_password(req.admin_password),
        full_name=req.admin_full_name,
    )
    db.add(user)
    db.flush()

    db.add(models.Membership(org_id=org.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(org)
    db.refresh(user)

    audit.record_audit(db, action="org.register", org_id=org.id,
                       actor_user_id=user.id, resource_type="org", resource_id=org.id)

    token = security.create_access_token(user.id, org.id, role="owner")
    return TokenResponse(access_token=token, org_id=org.id, user_id=user.id, role="owner")


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter_by(email=str(req.email).lower()).first()
    if user is None or not user.is_active or not security.verify_password(req.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    membership = (db.query(models.Membership)
                  .filter(models.Membership.user_id == user.id).first())
    org_id = membership.org_id if membership else None
    role = membership.role if membership else "member"

    audit.record_audit(db, action="auth.login", actor_user_id=user.id, org_id=org_id,
                       resource_type="user", resource_id=user.id)
    token = security.create_access_token(user.id, org_id, role)
    return TokenResponse(access_token=token, org_id=org_id, user_id=user.id, role=role)