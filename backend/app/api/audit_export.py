import io
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core.audit import AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/export")
def export_audit(format: str = "json", ctx: dict = Depends(require_org),
                 db: Session = Depends(get_db)):
    """Export audit events for the calling organisation (or global) as JSON/CSV."""
    org_id = ctx["org_id"]
    rows = db.query(AuditEvent).filter(
        (AuditEvent.org_id == org_id) | (AuditEvent.org_id.is_(None))
    ).order_by(AuditEvent.created_at).all()

    records = [{"id": str(r.id), "org_id": str(r.org_id) if r.org_id else None,
                "actor_user_id": str(r.actor_user_id) if r.actor_user_id else None,
                "action": r.action, "resource_type": r.resource_type,
                "resource_id": str(r.resource_id) if r.resource_id else None,
                "detail": r.detail,
                "created_at": r.created_at.isoformat() if r.created_at else None}
               for r in rows]

    if format == "csv":
        import csv
        buf = io.StringIO()
        keys = ["id", "org_id", "actor_user_id", "action", "resource_type", "resource_id", "created_at"]
        writer = csv.DictWriter(buf, fieldnames=keys)
        writer.writeheader()
        for rec in records:
            writer.writerow({k: rec.get(k) for k in keys})
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=audit.csv"})
    return {"count": len(records), "records": records}