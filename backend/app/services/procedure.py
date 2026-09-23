"""Deterministic procedural deadline calculator.

Mode semantics:
- calendar_days: add `base_days` calendar days (skip none).
- business_days: add `base_days` business days (weekends + public holidays skipped).
- day_of_month: next/this occurrence of `day_of_month`.
- last_day_month: last day of the month of the trigger (or next month).

Ambiguous rules/triggers return certainty=REVIEW_REQUIRED with no guessed date.
The result is deterministic and carries its legal source.
"""
import hashlib
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..models.procedure import ProceduralRule

REVIEW_REQUIRED = "REVIEW_REQUIRED"

# Representative Cyprus public holidays (2021-2025). A fuller framework can load
# these from a table; keeping them as a framework default.
CY_HOLIDAYS = {
    (1, 1), (1, 6), (3, 25),
    (12, 25), (12, 26),
}


def content_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def is_business_day(d: date, holidays: set[tuple[int, int]] | None = None) -> bool:
    holidays = holidays or CY_HOLIDAYS
    if d.weekday() >= 5:
        return False
    return (d.month, d.day) not in holidays


def _add_business_days(start: date, n: int, holidays) -> date:
    d = start
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    while remaining > 0:
        d += timedelta(days=step)
        if is_business_day(d, holidays):
            remaining -= 1
    return d


def calculate_deadline(rule: ProceduralRule, trigger_date, holidays: set[tuple[int, int]] | None = None) -> dict:
    holidays = holidays or CY_HOLIDAYS
    if isinstance(trigger_date, datetime):
        trigger_date = trigger_date.date()
    elif not isinstance(trigger_date, date):
        raise ValueError("trigger_date must be a date")

    if rule.ambiguous:
        return {"certainty": REVIEW_REQUIRED, "deadline": None,
                "reason": "Rule is ambiguous; review required before computing a deadline.",
                "source": rule.source_note or rule.law_ref}

    try:
        if rule.calculate_mode == "calendar_days":
            delta = timedelta(days=rule.base_days)
            deadline = trigger_date + delta if rule.direction == "after" else trigger_date - delta
        elif rule.calculate_mode == "business_days":
            n = rule.base_days if rule.direction == "after" else -rule.base_days
            deadline = _add_business_days(trigger_date, n, holidays)
        elif rule.calculate_mode == "day_of_month":
            dom = rule.day_of_month or 1
            target = trigger_date.replace(day=1) + timedelta(days=dom - 1)
            if target < trigger_date or rule.direction == "after":
                # next occurrence
                if target <= trigger_date:
                    target = _next_day_of_month(trigger_date, dom)
            deadline = target
        elif rule.calculate_mode == "last_day_month":
            if rule.direction == "after":
                nxt = trigger_date.replace(day=28) + timedelta(days=4)
                deadline = nxt.replace(day=1) - timedelta(days=1)
            else:
                deadline = trigger_date.replace(day=28) - timedelta(days=28)
                deadline = deadline.replace(day=28) + timedelta(days=4)
                deadline = deadline.replace(day=1) - timedelta(days=1)
        else:
            return {"certainty": REVIEW_REQUIRED, "deadline": None,
                    "reason": f"Unsupported calculate_mode '{rule.calculate_mode}'", "source": rule.source_note}
    except Exception:
        return {"certainty": REVIEW_REQUIRED, "deadline": None,
                "reason": "Could not compute a deterministic deadline from trigger.", "source": rule.source_note}

    return {"certainty": "DETERMINED", "deadline": deadline.isoformat(),
            "mode": rule.calculate_mode, "limit_type": rule.limit_type,
            "source": rule.source_note or rule.law_ref, "law_ref": rule.law_ref}


def _next_day_of_month(trigger: date, dom: int) -> date:
    y, m = trigger.year, trigger.month
    for _ in range(24):
        m += 1
        if m > 12:
            m = 1
            y += 1
        last = (date(y, m, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        day = min(dom, last.day)
        candidate = date(y, m, day)
        if candidate > trigger:
            return candidate
    return trigger


def register_rule(db: Session, *, rule_key: str, title: str, jurisdiction: str,
                  calculate_mode: str, base_days: int = 0, day_of_month: int | None = None,
                  direction: str = "after", limit_type: str = "maximum",
                  ambiguous: bool = False, source_note: str | None = None,
                  law_ref: str | None = None) -> ProceduralRule:
    h = content_hash(f"{rule_key}|{calculate_mode}|{base_days}|{day_of_month}|{direction}|{ambiguous}|{limit_type}")
    existing = db.query(ProceduralRule).filter_by(
        rule_key=rule_key, content_hash=h).first()
    if existing is not None:
        return existing
    vnum = (db.query(ProceduralRule).filter_by(rule_key=rule_key).count()) + 1
    rule = ProceduralRule(rule_key=rule_key, title=title, jurisdiction=jurisdiction,
                          calculate_mode=calculate_mode, base_days=base_days,
                          day_of_month=day_of_month, direction=direction,
                          limit_type=limit_type, ambiguous=ambiguous,
                          source_note=source_note, law_ref=law_ref,
                          version_number=vnum, content_hash=h)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule