"""Grounded research assistant with first-class provenance (task-4).

The assistant answers ONLY from retrieved, verified authorities. The narrative is
EXTRACTIVE — built from exact source/evidence spans — so it cannot fabricate cases,
ECLI, statutes, provisions, quotations, holdings, dates, or deadlines. Every material
proposition carries a provenance kind:
  SOURCE FACT           (verbatim from a canonical source / evidence span)
  STRUCTURED EXTRACTION (from the structured segmentation, e.g. section type)
  MODEL INFERENCE       (assistant-composed phrasing/relations — never legal fact)
  LAWYER DECISION       (lawyer-controlled classification, from the matter)
Model prose is always labelled MODEL_INFERENCE and never becomes canonical legal data.
"""
import re
import uuid

from ..services.research_vertical import research


def _query_tokens(q: str):
    return {t for t in re.findall(r"[a-z\u0370-\u03ff]{3,}", (q or "").lower()) if t}


def _evidence_overlap(evidence: list, qtoks: set) -> int:
    texts = " ".join((e.get("text") or "") for e in (evidence or [])).lower()
    return sum(1 for t in qtoks if t in texts)


def grounded_answer(db, *, query, as_of=None, limit: int = 6,
                    matter_id=None, org_id=None, firm_private_ok: bool = True) -> dict:
    if matter_id:
        matter_id = uuid.UUID(str(matter_id))
    out = research(db, query, as_of=as_of, limit=limit)
    results = [r for r in out["results"]]

    if not results:
        return _insufficient([])

    qtoks = _query_tokens(query)
    # Grounding gate: only answer when a retrieved authority actually overlaps the
    # query substantively; otherwise the evidence is insufficient.
    qualifying = [r for r in results if _evidence_overlap(r.get("evidence"), qtoks) >= 2]
    # Adverse/contrary surfacing is independent of whether the answer qualifies.
    adverse = _adverse_from_matter(db, org_id, matter_id) if org_id and matter_id else []
    if not qualifying:
        adverse += _adverse_from_treatments(db, results)
        return _insufficient(adverse)

    # Distinguish source types (legislation / judgment / firm-private material).
    authorities = []
    propositions = []
    used = set()
    for r in qualifying:
        atype = r.get("detail", {}).get("authority_type") or r["kind"]
        scope = "public"  # legal-corpus results are public canonical authorities
        authorities.append({
            "canonical_ref": r["canonical_ref"], "type": atype,
            "source_scope": scope, "name": r.get("detail", {}).get("name") or r.get("title"),
            "jurisdiction": r.get("detail", {}).get("jurisdiction"),
            "temporal": r.get("temporal"), "evidence": r.get("evidence", []),
            "why": r.get("why", []),
        })
        for e in r.get("evidence", []) or []:
            text = (e.get("text") or "").strip()
            if not text or text in used:
                continue
            used.add(text)
            propositions.append({
                "text": text,
                "authority": r["canonical_ref"],
                "span": {"para_number": e.get("para_number"), "char_start": e.get("char_start"),
                         "char_end": e.get("char_end"), "article": e.get("article")},
                "kind": "SOURCE FACT",
            })

    # Model-inference overlay is clearly labelled; it never asserts legal facts.
    model_inference = {
        "kind": "MODEL_INFERENCE",
        "text": "The assistant composed this overview from the verified authorities below; "
                "any legal conclusion requires the lawyer's independent review.",
    }

    # Select the most on-point evidence (extractive narrative) from the top authority.
    top_evidence = authorities[0].get("evidence") or []
    narrative = " ".join((e.get("text") or "").strip() for e in top_evidence).strip()
    answer = narrative if narrative else "(No verbatim content available from the top authority.)"

    # Adverse/contrary: add treatment edges on the qualifying authorities to the
    # already-collected matter-level adverse (from the early computation).
    adverse = adverse + _adverse_from_treatments(db, qualifying)

    return {
        "supported": True,
        "message": None,
        "answer": answer,
        "propositions": propositions[:12],
        "authorities": authorities,
        "adverse": adverse,
        "model_inference": model_inference,
        "provenance_legend": {
            "SOURCE FACT": "verbatim from a canonical source / evidence span",
            "STRUCTURED EXTRACTION": "from structured segmentation (e.g., section type)",
            "MODEL INFERENCE": "assistant-composed phrasing — never legal fact",
            "LAWYER DECISION": "lawyer-controlled classification on the matter"},
    }


def _adverse_from_matter(db, org_id, matter_id):
    from ..models.authority import MatterAuthority
    rows = db.query(MatterAuthority).filter_by(org_id=org_id, matter_id=matter_id,
                                               classification="adverse").all()
    return [{"canonical_ref": a.canonical_ref, "basis": a.matter_issue,
             "provenance": "LAWYER DECISION"} for a in rows]


def _adverse_from_treatments(db, results):
    from ..models.core import CaseTreatment
    adversarial = {"DISTINGUISHES", "OVERRULES", "CRITICISES"}
    out = []
    for r in results:
        det = r.get("detail", {})
        for t in det.get("treatments", []):
            if t.get("treatment") in adversarial:
                out.append({"canonical_ref": r["canonical_ref"],
                            "treatment": t["treatment"],
                            "provenance": "STRUCTURED_EXTRACTION",
                            "review_status": t.get("review_status", "review_required")})
    return out

def _insufficient(adverse: list | None = None) -> dict:
    return {
        "supported": False,
        "message": "No sufficiently supported authority was found for this question in the "
                   "curated/verified corpus. No case, statute, or holding is asserted.",
        "answer": None, "propositions": [], "authorities": [],
        "adverse": adverse or [],
        "model_inference": {"kind": "MODEL_INFERENCE",
                            "text": "The assistant did not compose an answer because the "
                                    "verified evidence did not substantively support the question."},
        "provenance_legend": _LEGEND,
    }


_LEGEND = {
    "SOURCE FACT": "verbatim from a canonical source / evidence span",
    "STRUCTURED EXTRACTION": "from structured segmentation (e.g., section type)",
    "MODEL INFERENCE": "assistant-composed phrasing — never legal fact",
    "LAWYER DECISION": "lawyer-controlled classification on the matter",
}
