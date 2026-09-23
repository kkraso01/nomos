"""AI Router: business modules request capabilities, never provider/model names."""
import hashlib
import json
import logging
import uuid
from typing import Any

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

CAPABILITIES = {
    "OCR_DOCUMENT",
    "EMBED_TEXT",
    "RERANK_SEARCH",
    "CLASSIFY_DOCUMENT",
    "EXTRACT_JUDGMENT_STRUCTURE",
    "EXTRACT_FACTS",
    "EXTRACT_ISSUES",
    "EXTRACT_CITATIONS",
    "COMPARE_FACTS",
    "COMPARE_CASES",
    "SUMMARIZE_JUDGMENT",
    "ANALYZE_ARGUMENTS",
    "IDENTIFY_ADVERSE_AUTHORITY",
    "DRAFT_RESEARCH_MEMO",
    "DRAFT_ARGUMENT",
}

REMOTE_CAPABILITIES = {
    "SUMMARIZE_JUDGMENT",
    "ANALYZE_ARGUMENTS",
    "IDENTIFY_ADVERSE_AUTHORITY",
    "DRAFT_RESEARCH_MEMO",
    "DRAFT_ARGUMENT",
}


class AIRouter:
    """Routes a capability to the lowest reliable available level (L0..L3).

    L3 remote use is gated by organisation remote_ai_policy:
      REMOTE_AI_DISABLED -> refuse
      PUBLIC_ONLY       -> only for non-private payloads
      PRIVATE_ALLOWED   -> allowed
    """

    def __init__(self):
        self.client = httpx.Client(base_url=settings.openrouter_base_url, timeout=60) \
            if hasattr(settings, "openrouter_base_url") and settings.openrouter_base_url else None

    def _policy_allows(self, org_policy: str, is_private: bool) -> bool:
        policy = (org_policy or settings.remote_ai_policy or "PUBLIC_ONLY").upper()
        if policy == "REMOTE_AI_DISABLED":
            return False
        if policy == "PUBLIC_ONLY" and is_private:
            return False
        return True

    def run_remote(self, capability: str, prompt: str, org_policy: str, is_private: bool = False) -> dict:
        if capability not in REMOTE_CAPABILITIES:
            raise ValueError(f"Capability {capability} has no remote route")
        if not self._policy_allows(org_policy, is_private):
            return {"ok": False, "reason": "remote_ai_policy_blocked", "output": None}
        if not settings.openrouter_api_key:
            return {"ok": False, "reason": "no_provider_configured", "output": None}
        headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
        body = {
            "model": settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = self.client.post("/chat/completions", json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            out = data["choices"][0]["message"]["content"]
            return {"ok": True, "output": out, "provider": settings.openrouter_model}
        except Exception as exc:  # noqa: BLE001
            logger.warning("remote AI call failed for %s: %s", capability, exc)
            return {"ok": False, "reason": "provider_error", "output": None}

    @staticmethod
    def input_hash(payload: Any) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


router = AIRouter()


def get_router() -> AIRouter:
    return router