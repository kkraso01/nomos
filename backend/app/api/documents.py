import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..core.tenancy import require_org
from ..core import audit
from ..storage.s3 import storage
from ..schemas import DocumentOut

router = APIRouter(prefix="/documents", tags=["documents"])


def _private_key(ctx: dict, filename: str) -> str:
    """Private objects are namespaced by organisation to enforce tenancy at the store level."""
    return f"{ctx['org_id']}/matters/{filename}"


@router.post("/private", response_model=DocumentOut, status_code=201)
def upload_private_document(
    file: UploadFile = File(...),
    matter_id: str = Form(""),
    ctx: dict = Depends(require_org),
    db: Session = Depends(get_db),
):
    # Verify the target matter belongs to the caller's org (tenancy check).
    if matter_id:
        m = db.query(models.Matter).filter(
            models.Matter.id == uuid.UUID(matter_id),
            models.Matter.org_id == ctx["org_id"]).first()
        if m is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Matter not found in organisation")

    data = file.file.read()
    key = _private_key(ctx, file.filename or "upload.bin")
    key = key.replace("\\", "/")
    ctype = file.content_type or "application/octet-stream"
    storage.put_bytes(data, key, private=True, content_type=ctype)

    audit.record_audit(db, action="document.upload.private", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="document",
                       resource_id=None, detail={"key": key, "content_type": ctype, "bytes": len(data)})
    return DocumentOut(key=key, content_type=ctype, private=True, content_length=len(data))


@router.get("/private/{org_ids}/{filename:path}")
def download_private_document(org_ids: str, filename: str, ctx: dict = Depends(require_org)):
    key = f"{org_ids}/matters/{filename}"
    if org_ids != str(ctx["org_id"]):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-organisation access denied")
    data = storage.get_bytes(key, private=True)
    return {"key": key, "bytes": len(data), "preview": data[:400].decode("utf-8", "replace")}