from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..core.tenancy import require_org
from ..core import audit
from ..models.procedure import ProceduralRule
from ..services.procedure import register_rule, calculate_deadline, REVIEW_REQUIRED

router = APIRouter(prefix="/procedure", tags=["procedure"])


class RuleIn(BaseModel):
    rule_key: str
    title: str
    jurisdiction: str = "CY"
    calculate_mode: str
    base_days: int = 0
    day_of_month: int | None = None
    direction: str = "after"
    limit_type: str = "maximum"
    ambiguous: bool = False
    source_note: str | None = None
    law_ref: str | None = None


class DeadlineIn(BaseModel):
    rule_id: str
    trigger_date: date


@router.post("/rules", status_code=201)
def add_rule(payload: RuleIn, ctx: dict = Depends(require_org), db: Session = Depends(get_db)):
    rule = register_rule(db, rule_key=payload.rule_key, title=payload.title,
                         jurisdiction=payload.jurisdiction, calculate_mode=payload.calculate_mode,
                         base_days=payload.base_days, day_of_month=payload.day_of_month,
                         direction=payload.direction, limit_type=payload.limit_type,
                         ambiguous=payload.ambiguous, source_note=payload.source_note,
                         law_ref=payload.law_ref)
    audit.record_audit(db, action="procedure.rule.register", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="procedure_rule",
                       resource_id=rule.id)
    return {"rule_id": str(rule.id), "rule_key": rule.rule_key, "version_number": rule.version_number}


@router.post("/deadline")
def compute_deadline(payload: DeadlineIn, ctx: dict = Depends(require_org),
                     db: Session = Depends(get_db)):
    rule = db.get(ProceduralRule, payload.rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found")
    result = calculate_deadline(rule, payload.trigger_date)
    audit.record_audit(db, action="procedure.deadline.compute", org_id=ctx["org_id"],
                       actor_user_id=ctx["user"].id, resource_type="procedure_rule",
                       resource_id=rule.id, detail={"certainty": result.get("certainty")})
    return {"rule_key": rule.rule_key, "trigger_date": payload.trigger_date.isoformat(),
            "certainty": result.get("certainty"), "deadline": result.get("deadline"),
            "mode": result.get("mode"), "limit_type": result.get("limit_type"),
            "reason": result.get("reason"), "source": result.get("source")}