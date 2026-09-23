import uuid

from jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..core import security

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = security.decode_token(creds.credentials)
    except jwt.JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    user_id = payload.get("sub")
    user = db.get(models.User, uuid.UUID(user_id))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid user")
    return {"user": user, "org_id": payload.get("org"), "role": payload.get("role")}


def get_org_context(current: dict = Depends(get_current_user)) -> dict:
    return current


def require_org(current: dict = Depends(get_current_user)) -> dict:
    if not current.get("org_id"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No active organisation")
    return current