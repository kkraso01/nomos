"""Case comparison with separate similarity dimensions (jurisdiction-agnostic)."""
import re
from collections import Counter

from sqlalchemy.orm import Session

from ..models.core import Judgment, JudgmentSection, JudgmentParagraph, CaseCitation


_REMEDY_TERMS = {"damages", "compensation", "injunction", "specific performance",
                 "costs", "rescission", "repayment", "interest", "dismissed"}


def _tokens(text: str):
    return re.findall(r"[a-zA-Z\u0370-\u03ff]{3,}", (text or "").lower())


def _jaccard(a: list, b: list):
    if not a or not b:
        return 0.0
    sa, sb = Counter(a), Counter(b)
    inter = sum((sa & sb).values())
    union = sum((sa | sb).values())
    return round(inter / union, 3) if union else 0.0


def _load(db, canonical_id: str) -> Judgment | None:
    return db.query(Judgment).filter_by(canonical_id=canonical_id).first()


def _sections(db, judgment: Judgment) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    sections = db.query(JudgmentSection).filter_by(version_id=judgment.current_version_id)\
        .order_by(JudgmentSection.sort_order).all()
    for s in sections:
        paras = db.query(JudgmentParagraph).filter_by(section_id=s.id)\
            .order_by(JudgmentParagraph.sort_order).all()
        out.setdefault(s.section_type, []).extend(p.text or "" for p in paras)
    return out


def _cited_targets(db, jurisdiction: str, case_id) -> set[str]:
    rows = db.query(CaseCitation).filter_by(source_case_id=case_id).all()
    keys = set()
    for c in rows:
        keys.add(c.target_case_key or str(c.target_case_id))
    return keys


def compare_cases(db: Session, a_id: str, b_id: str) -> dict:
    a = _load(db, a_id)
    b = _load(db, b_id)
    if a is None or b is None:
        return {"ok": False, "missing": [x for x, j in ((a_id, a), (b_id, b)) if j is None]}
    sa = _sections(db, a)
    sb = _sections(db, b)
    targets_a = _cited_targets(db, a.jurisdiction, a.id)
    targets_b = _cited_targets(db, b.jurisdiction, b.id)

    shared_stat = sorted(targets_a & targets_b)
    stat_score = round(len(shared_stat) / max(1, len(targets_a | targets_b)), 3)

    la = _tokens(" ".join(sa.get("holding", []) + sa.get("legal_analysis", [])))
    lb = _tokens(" ".join(sb.get("holding", []) + sb.get("legal_analysis", [])))
    legal_score = _jaccard(la, lb)

    fa = _tokens(" ".join(sa.get("facts", [])))
    fb = _tokens(" ".join(sb.get("facts", [])))
    factual_score = _jaccard(fa, fb)

    proc_ta = _tokens(" ".join(sa.get("procedural_history", [])))
    proc_tb = _tokens(" ".join(sb.get("procedural_history", [])))
    same_court = 1.0 if (a.court and b.court and a.court == b.court) else 0.0
    procedural_score = round(0.5 * same_court + 0.5 * _jaccard(proc_ta, proc_tb), 3)

    def _remedy(segs):
        txt = " ".join(segs.get("order", [])).lower()
        return [t for t in _REMEDY_TERMS if t in txt]
    rem_a, rem_b = _remedy(sa), _remedy(sb)
    shared_rem = set(rem_a) & set(rem_b)
    remedy_score = round(len(shared_rem) / max(1, len(set(rem_a) | set(rem_b))), 3)

    return {"ok": True, "cases": {"a": a.canonical_id, "b": b.canonical_id},
            "similarity": [
                {"dimension": "LEGAL_ISSUE_SIMILARITY", "score": legal_score,
                 "explanation": "Term overlap in holding/legal-analysis sections."},
                {"dimension": "FACTUAL_SIMILARITY", "score": factual_score,
                 "explanation": "Term overlap in the facts section."},
                {"dimension": "PROCEDURAL_SIMILARITY", "score": procedural_score,
                 "explanation": "Same court + procedural-history overlap."},
                {"dimension": "STATUTORY_SIMILARITY", "score": stat_score,
                 "explanation": f"Shared cited authorities: {shared_stat or 'none'}."},
                {"dimension": "REMEDY_SIMILARITY", "score": remedy_score,
                 "explanation": f"Shared remedy outcomes: {sorted(shared_rem) or 'none'}."},
            ]}