"""Subscription tier config (task-5, wire-ready; NO pricing UI yet).

Aligns the existing plan/entitlement architecture to the approved commercial model
without ever making a lower tier return worse or incorrect law — gaps are
productivity/capacity features only.
"""
from __future__ import annotations

# Plan identifiers used by Org.plan (kept stable with the existing FEATURES gate).
FREE_DEMO = "free"
PRO = "pro"

# What each tier includes (productivity/intelligence/capacity, never correctness).
TIERS = {
    FREE_DEMO: {
        "label": "NOMOS Free / Demo",
        "limit": {"search_per_day": 25, "saved_authorities": 20, "matters": 2},
    },
    PRO: {
        "label": "NOMOS Pro — Research Cyprus law faster.",
        "limit": {"search_per_day": None, "saved_authorities": None, "matters": None},
    },
}

# Commercial model captures for the eventual pricing page (config, not visited by code).
PRICING_CONFIG = {
    "hosted": {
        "per_lawyer_month": 89,
        "per_lawyer_year": 890,
        "firm_month": 399, "firm_users_incl": 5, "additional_user_month": 59,
    },
    "private": {
        "implementation": 6000, "platform_per_year": 12000,
        "users_incl": 10, "additional_user_year_range": [300, 500],
    },
}

# A tier is the *highest* plan the org is entitled to (used to decide limits).
TIER_BY_PLAN = {"free": FREE_DEMO, "starter": FREE_DEMO, "standard": FREE_DEMO,
                "demo": FREE_DEMO, "pro": PRO, "enterprise": PRO}


def tier_for_plan(plan: str | None) -> str:
    return TIER_BY_PLAN.get((plan or "free").lower(), FREE_DEMO)


def usage_limit(tier: str, key: str):
    return TIERS.get(tier, TIERS[FREE_DEMO]).get("limit", {}).get(key)


def check_usage(redis, org_id, tier: str, key: str) -> dict:
    """Enforce a per-org daily usage allowance for the tier.

    FREE/DEMO is rate-limited (productivity/capacity only); PRO is unrestricted.
    Returns {'allowed': bool, 'remaining': int|None}. The cheap/legal tiers are
    NEVER made to return worse/incorrect law — only call volume is limited.
    """
    limit = usage_limit(tier, key)
    if limit is None:
        return {"allowed": True, "remaining": None}
    day = __import__("datetime").datetime.utcnow().strftime("%Y%m%d")
    rk = f"usage:{org_id}:{key}:{day}"
    used = int(redis.incr(rk))
    if used == 1:
        redis.expire(rk, 86400)
    return {"allowed": used <= limit, "remaining": max(0, limit - used)}