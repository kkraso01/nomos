"""Entitlements: plan-to-feature gating enforced server-side.

Business modules declare a required feature; an org must be entitled to use it
or the call is denied (403). This is a local functional gate for Phase J, not a
production billing system.
"""
from fastapi import HTTPException, status

# feature -> set of plans that include it
FEATURES = {
    "AI_REMOTE": {"pro", "enterprise"},
    "SEMANTIC_SEARCH": {"pro", "enterprise"},
    "FIRM_KNOWLEDGE": {"standard", "pro", "enterprise"},
    "DRAFTING": {"standard", "pro", "enterprise"},
    "ADVANCED_SEARCH": {"pro", "enterprise"},
}


def is_entitled(plan: str, feature: str) -> bool:
    allowed = FEATURES.get(feature)
    if allowed is None:
        return True  # unknown feature default-open
    return plan in allowed


def require_entitlement(plan: str, feature: str) -> None:
    if not is_entitled(plan, feature):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Organisation plan '{plan}' is not entitled to feature '{feature}'")