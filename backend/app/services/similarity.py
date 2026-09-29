"""Case comparison reporting separate similarity dimensions (Phase E).

Dimensions (per ARCHITECTURE_AND_RETRIEVAL.md sec 11):
  LEGAL_ISSUE_SIMILARITY, FACTUAL_SIMILARITY, PROCEDURAL_SIMILARITY,
  STATUTORY_SIMILARITY, REMEDY_SIMILARITY

Implementation is deterministic (L0): term/segment overlap + shared citation-graph
references + metadata, so it never pretends to judge legal force. Each dimension
returns a score and an explanation of *why*.
"""
import re
from collections import Counter

from sqlalchemy.orm import Session

from ..models.corpus import Judgment, JudgmentNode
from ..models.citation import CitationEdge


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


def _load_version(db, canonical_id: str) -> Judgment | None:
    return db.query(Judgment).filter_by(canonical_id=canonical_id).first()


def _segments(db, judgment: Judgment) -> dict[str, list[str]]:
    nodes = db.query(JudgmentNode).filter_by(version_id=judgment.current_version_id)\
        .order_by(JudgmentNode.sort_order).all()
    out: dict[str, list[str]] = {}
    current = None
    for n in nodes:
        seg = n.segment_type
        if seg and seg != "analysis":
            current = seg  # heading line: sets the active segment, not compared text
            continue
        # body text belongs to the segment opened by the preceding heading
        grp = current or "body"
        out.setdefault(grp, []).append(n.text or "")
    return out


def _cited_targets(db, judgment_ref: str) -> set[str]:
    """Canonical refs this judgment cites (from the graph)."""
    return {e.target_ref for e in db.query(CitationEdge).filter_by(
        source_kind="judgment_node", source_ref=judgment_ref).all() if e.target_ref}


def compare_cases(db: Session, a_id: str, b_id: str) -> dict:
    a = _load_version(db, a_id)
    b = _load_version(db, b_id)
    if a is None or b is None:
        missing = [x for x, j in ((a_id, a), (b_id, b)) if j is None]
        return {"ok": False, "missing": missing}

    ref_a = a.ecli or a.case_number or f"judgment-{a.canonical_id}"
    ref_b = b.ecli or b.case_number or f"judgment-{b.canonical_id}"
    sa = _segments(db, a)
    sb = _segments(db, b)
    targets_a = _cited_targets(db, f"judgment-{ref_a}")
    targets_b = _cited_targets(db, f"judgment-{ref_b}")

    # STATUTORY: shared cited provisions
    shared_stat = sorted(targets_a & targets_b)
    stat_score = round(len(shared_stat) / max(1, len(targets_a | targets_b)), 3)

    # LEGAL_ISSUE: overlap on holding + legal_analysis segments
    la = _tokens(" ".join(sa.get("holding", []) + sa.get("legal_analysis", [])))
    lb = _tokens(" ".join(sb.get("holding", []) + sb.get("legal_analysis", [])))
    legal_score = _jaccard(la, lb)

    # FACTUAL: overlap on facts segment
    fa = _tokens(" ".join(sa.get("facts", [])))
    fb = _tokens(" ".join(sb.get("facts", [])))
    factual_score = _jaccard(fa, fb)

    # PROCEDURAL: same court + procedural_history overlap
    proc_ta = _tokens(" ".join(sa.get("procedural_history", [])))
    proc_tb = _tokens(" ".join(sb.get("procedural_history", [])))
    same_court = 1.0 if (a.court and b.court and a.court == b.court) else 0.0
    procedural_score = round(0.5 * same_court + 0.5 * _jaccard(proc_ta, proc_tb), 3)

    # REMEDY: overlap of remedy vocabulary in order segments
    def _remedy_hits(segs):
        txt = " ".join(segs.get("order", [])).lower()
        return [t for t in _REMEDY_TERMS if t in txt]
    rem_a, rem_b = _remedy_hits(sa), _remedy_hits(sb)
    shared_rem = set(rem_a) & set(rem_b)
    remedy_score = round(len(shared_rem) / max(1, len(set(rem_a) | set(rem_b))), 3)

    return {
        "ok": True,
        "cases": {"a": a.canonical_id, "ref_a": ref_a, "b": b.canonical_id, "ref_b": ref_b},
        "similarity": [
            {"dimension": "LEGAL_ISSUE_SIMILARITY", "score": legal_score,
             "explanation": "Term overlap in holding/legal-analysis segments."},
            {"dimension": "FACTUAL_SIMILARITY", "score": factual_score,
             "explanation": "Term overlap in the facts segment."},
            {"dimension": "PROCEDURAL_SIMILARITY", "score": procedural_score,
             "explanation": "Same court + procedural-history overlap."},
            {"dimension": "STATUTORY_SIMILARITY", "score": stat_score,
             "explanation": f"Shared cited provisions: {shared_stat or 'none'}."},
            {"dimension": "REMEDY_SIMILARITY", "score": remedy_score,
             "explanation": f"Shared remedy outcomes: {sorted(shared_rem) or 'none'}."},
        ],
    }