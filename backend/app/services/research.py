"""Grounded legal research assistant.

Retrieves canonical public law via the search pipeline, validates any citation
embedded in the question against the corpus, and returns source-grounded
passages. It NEVER generates a statute/case from model memory: if no supporting
authority is found it returns supported=False with an explicit message.
"""
from sqlalchemy.orm import Session

from ..models.search import SearchEntry
from ..services.search import search
from ..services.references import parse_reference
from ..services.citation import resolve_node


def validate_citation(db: Session, text: str) -> dict:
    """Parse a citation string and report whether it exists in the corpus."""
    ref = parse_reference(text)
    if ref.kind == "unknown":
        return {"parsed": False, "kind": "unknown", "exists": None, "note": "Not a recognized legal reference"}
    if ref.kind == "legislation_article":
        hits = db.query(SearchEntry).filter_by(ref_law=ref.law_number,
                                               ref_article=ref.article_number).all()
        return {"parsed": True, "kind": ref.kind, "law": ref.law_number,
                "article": ref.article_number, "exists": len(hits) > 0,
                "matches": len(hits)}
    if ref.kind == "judgment":
        fc = {"ecli": ref.ecli} if ref.ecli else {"case_number": ref.case_number}
        hits = db.query(SearchEntry).filter_by(**fc).all()
        return {"parsed": True, "kind": ref.kind, "case_number": ref.case_number,
                "ecli": ref.ecli, "exists": len(hits) > 0, "matches": len(hits)}
    if ref.kind == "legislation":
        hits = db.query(SearchEntry).filter_by(ref_law=ref.law_number).all()
        return {"parsed": True, "kind": ref.kind, "law": ref.law_number,
                "exists": len(hits) > 0, "matches": len(hits)}
    return {"parsed": False, "kind": ref.kind, "exists": None}


def grounded_research(db: Session, query: str, limit: int = 10,
                      accepted_facts: list[str] | None = None) -> dict:
    citations = validate_citation(db, query)

    authorities = []
    results = search(db, query, mode="hybrid", limit=limit)
    for r in results:
        authorities.append({
            "canonical_ref": r.canonical_ref, "kind": r.kind, "title": r.title,
            "text": r.body, "language": r.language, "score": round(r.score, 3),
            "reason_for_match": r.reason,
            "source_url": r.metadata.get("source_url"), "provenance": r.metadata,
        })

    evidence = []
    for f in (accepted_facts or []):
        # only include matter evidence a lawyer explicitly accepted
        evidence.append({"type": "accepted_matter_fact", "text": f})

    supported = bool(authorities)
    if supported:
        top = authorities[0]
        answer = (f"Based on the retrieved authority '{top['title']}' "
                  f"({top['canonical_ref']}), the supporting text states: "
                  f"{top['text'][:400]}")
    else:
        answer = ("No sufficiently supported authority was found for this "
                  "question in the curated public corpus.")

    return {
        "query": query,
        "supported": supported,
        "answer": answer,
        "citation_check": citations,
        "authorities": authorities,
        "matter_evidence": evidence,
        "disclaimer": "Grounded only; not legal advice.",
    }