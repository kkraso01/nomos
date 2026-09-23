"""Citation graph services: validated creation + traversal."""
import uuid

from sqlalchemy.orm import Session

from ..models.search import SearchEntry
from ..models.citation import CitationEdge


class CitationValidationError(Exception):
    pass


def resolve_node(db: Session, kind: str, ref: str) -> SearchEntry | None:
    return db.query(SearchEntry).filter_by(kind=kind, canonical_ref=ref).first()


def create_edge(db: Session, *, source_kind: str, source_ref: str,
                target_kind: str, target_ref: str, treatment: str = "CITES",
                evidence: dict | None = None, review_status: str | None = None,
                org_id=None, note: str | None = None) -> CitationEdge:
    # Every citation must point at something that actually exists in the corpus.
    src = resolve_node(db, source_kind, source_ref)
    tgt = resolve_node(db, target_kind, target_ref)
    if src is None or tgt is None:
        missing = "source" if src is None else ""
        missing = (missing + "+target" if src is not None else "target")
        raise CitationValidationError(f"Nonexistent citation: {missing} node not found in corpus")

    if treatment in CitationEdge.SEMANTIC:
        # Semantic treatment requires supporting source evidence.
        if not evidence or not evidence.get("quote"):
            raise CitationValidationError("Semantic treatment requires supporting evidence (quote)")
        if review_status not in ("verified", "review_required"):
            review_status = "review_required"
    else:
        review_status = review_status or "verified"

    edge = CitationEdge(source_kind=source_kind, source_ref=source_ref,
                        target_kind=target_kind, target_ref=target_ref,
                        treatment=treatment, evidence=evidence,
                        review_status=review_status, org_id=org_id, note=note)
    return edge


def cited_authorities(db: Session, kind: str, ref: str) -> list[CitationEdge]:
    """All edges originating from the given node (what it cites)."""
    return db.query(CitationEdge).filter_by(source_kind=kind, source_ref=ref).all()


def citing_authorities(db: Session, kind: str, ref: str) -> list[CitationEdge]:
    """All edges pointing at the given node (what cites it)."""
    return db.query(CitationEdge).filter_by(target_kind=kind, target_ref=ref).all()