"""Deterministic provision cross-reference scanning (task-5).

Scans a legislation version's node wording with the L0 reference extractor and
creates ProvisionCrossReference(source_node -> target_node, span, high confidence).
Only deterministic, span-exact links — no LLM.
"""
import re

from sqlalchemy.orm import Session

from ..models.core import (Legislation, LegislationVersion, LegislationNode,
                           LegislationNodeVersion, ProvisionCrossReference)
from ..services.references import extract_references


def scan_legislation(db: Session, canonical_id: str, version_id=None) -> dict:
    law = db.query(Legislation).filter_by(canonical_id=canonical_id).first()
    if law is None:
        return {"created": 0, "errors": ["legislation not found"]}
    if version_id is None:
        version = db.query(LegislationVersion).filter_by(legislation_id=law.id, status="current").first()
        if version is None and law.current_version_id:
            version = db.get(LegislationVersion, law.current_version_id)
        version_id = version.id

    nodes = db.query(LegislationNode, LegislationNodeVersion).join(
        LegislationNodeVersion, LegislationNodeVersion.node_id == LegislationNode.id).filter(
        LegislationNodeVersion.legislation_version_id == version_id).all()

    created = 0
    for node, nv in nodes:
        src = nv.source_text or ""
        for ref in extract_references(src):
            if ref["kind"] != "article":
                continue  # chapter/law/judgment links folded through other paths/graph
            target = db.query(LegislationNode).filter_by(
                legislation_id=law.id, node_type="ARTICLE", number=str(ref["article"])).first()
            if target is None or target.id == node.id:
                continue
            span_s, span_e = ref["start"], ref["end"]
            existing = db.query(ProvisionCrossReference).filter_by(
                jurisdiction=law.jurisdiction, source_node_id=node.id,
                target_node_id=target.id, source_span_start=span_s,
                source_span_end=span_e).first()
            if existing is not None:
                continue
            db.add(ProvisionCrossReference(
                jurisdiction=law.jurisdiction, source_node_id=node.id,
                target_node_id=target.id, relationship="REFERENCES",
                source_text=ref["text"], source_span_start=span_s,
                source_span_end=span_e, confidence="high"))
            created += 1
    db.commit()
    return {"created": created}


def extract_provision_refs(db, text: str) -> list:
    return extract_references(text)