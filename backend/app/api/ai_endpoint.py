"""AI capability-request endpoint.

Business modules request a capability and a payload; the router resolves the
provider/model. This endpoint also records a model-run log entry (capability,
resolution, input hash, success) without logging raw confidential prompts.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from ..ai.router import CAPABILITIES, REMOTE_CAPABILITIES, get_router
from ..core.tenancy import require_org
from ..models.run_log import ModelRunLog

router = APIRouter(prefix="/ai", tags=["ai"])


class CapabilityRequest(BaseModel):
    capability: str
    prompt: str = Field(..., min_length=1, max_length=20000)
    is_private: bool = False
    documents: list[str] = Field(default_factory=list)


class CapabilityResponse(BaseModel):
    capability: str
    ok: bool
    reason: str | None = None
    output: str | None = None
    provider: str | None = None
    input_hash: str
    scores: list[dict] | None = None


# A local deterministic L0/L1 fallback for capabilities with no configured provider.
_LOCAL_FALLBACKS = {
    "CLASSIFY_DOCUMENT": lambda p: "statute" if ("law" in p.lower() or "act" in p.lower()) else "other",
    "EXTRACT_CITATIONS": lambda p: "",
    "EMBED_TEXT": None,
    "RERANK_SEARCH": None,
}


def _local_rerank(prompt: str, documents: list[str]) -> dict:
    from ..services.rerank import RERANK_router
    try:
        ranked = RERANK_router(prompt, documents)
        return {"ok": True, "output": "reranked", "provider": "ONNX_MiniLM_qint8",
                "scores": ranked, "documents": documents}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"rerank_error: {exc}", "output": None}


@router.post("/capability", response_model=CapabilityResponse)
def run_capability(req: CapabilityRequest, ctx: dict = Depends(require_org),
                   db: Session = Depends(get_db)):
    if req.capability not in CAPABILITIES:
        raise HTTPException(404, f"Unknown capability {req.capability}")

    org = db.get(models.Org, ctx["org_id"])
    policy = org.remote_ai_policy if org else "PUBLIC_ONLY"
    plan = org.plan if org else "starter"
    router_ = get_router()
    inp_hash = router_.input_hash({"capability": req.capability, "prompt": req.prompt})

    # Remote (L3) route is gated by entitlement in addition to remote-AI policy.
    if req.capability in REMOTE_CAPABILITIES:
        from ..core.entitlements import require_entitlement
        require_entitlement(plan, "AI_REMOTE")
        result = router_.run_remote(req.capability, req.prompt, policy, req.is_private)
    else:
        # L0/L1 local route when available; otherwise refuse clearly.
        fallback = _LOCAL_FALLBACKS.get(req.capability)
        if fallback is not None:
            result = {"ok": True, "output": fallback(req.prompt), "provider": "L0_LOCAL"}
        elif req.capability == "EMBED_TEXT":
            result = {"ok": False, "reason": "no_embedding_model_configured", "output": None}
        elif req.capability == "RERANK_SEARCH":
            result = _local_rerank(req.prompt, req.documents)
        else:
            result = {"ok": False, "reason": "no_route_configured", "output": None}

    _record_run(db, ctx["org_id"], req.capability, result, req.prompt, inp_hash)
    return CapabilityResponse(capability=req.capability, ok=result.get("ok", False),
                              reason=result.get("reason"), output=result.get("output"),
                              provider=result.get("provider"),
                              input_hash=inp_hash, scores=result.get("scores"))


def _record_run(db, org_id, capability, result, prompt, input_hash):
    db.add(ModelRunLog(org_id=org_id, capability=capability,
                       provider=None if not result.get("ok") else result.get("provider"),
                       input_hash=input_hash, success=bool(result.get("ok")),
                       reason=result.get("reason")))
    db.commit()