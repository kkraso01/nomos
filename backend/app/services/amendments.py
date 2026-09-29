"""Temporal amendments as first-class events.

An amendment is an append-only event (LegislationAmendment + AmendmentOperation)
that yields a NEW legislation version effective on the amendment date; historic
text is never overwritten. as-of resolution (corpus.resolve_version_as_of) returns
the version applicable on a query date.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.core import (Legislation, LegislationVersion, LegislationNode,
                           LegislationNodeVersion, LegislationAmendment)
from ..services.corpus import content_hash, _index_legislation_version

OPERATIONS = {"INSERT", "DELETE", "REPLACE", "RENUMBER", "REPEAL", "COMMENCE"}


class AmendmentError(Exception):
    pass


def apply_amendment(db: Session, *, jurisdiction: str, affected_canonical_id: str,
                    operation: str, effective_date, publication_date=None,
                    node_type: str | None = None, node_number: str | None = None,
                    new_text: str | None = None, amending_canonical_id: str | None = None,
                    source_snapshot_id=None, source_evidence=None,
                    renumber_to: str | None = None) -> dict:
    if operation not in OPERATIONS:
        raise AmendmentError(f"unknown operation {operation}")
    law = db.query(Legislation).filter_by(canonical_id=affected_canonical_id).first()
    if law is None:
        raise AmendmentError(f"legislation {affected_canonical_id} not found")

    prior = db.query(LegislationVersion).filter_by(legislation_id=law.id, status="current").first()
    if prior is None:
        raise AmendmentError("no current version to amend")

    if node_type and not node_number:
        raise AmendmentError("node_number required with node_type")

    node = None
    previous_text = None
    if node_type and node_number:
        node = db.query(LegislationNode).filter_by(
            legislation_id=law.id, node_type=node_type, number=str(node_number)).first()
        if node is None:
            raise AmendmentError(f"{node_type} {node_number} not found")
        pv = db.query(LegislationNodeVersion).filter_by(
            node_id=node.id, legislation_version_id=prior.id).first()
        previous_text = pv.source_text if pv else None

    vnum = (db.query(LegislationVersion).filter_by(legislation_id=law.id).count()) + 1
    version = LegislationVersion(legislation_id=law.id, version_number=vnum,
                                 content_hash=content_hash(f"{operation}:{node_number}:{new_text}"),
                                 effective_from=effective_date, status="current",
                                 supersedes_version_id=prior.id, source_snapshot_id=source_snapshot_id)
    db.add(version)
    db.flush()

    # carry all node wording into the new version (immutable history; no destructive edit)
    carried = 0
    for pv in db.query(LegislationNodeVersion).filter_by(legislation_version_id=prior.id).all():
        text = pv.source_text
        if node is not None and pv.node_id == node.id and operation == "REPLACE":
            text = new_text
        if node is not None and pv.node_id == node.id and operation == "DELETE":
            continue  # deleted: absent from the new version (a tombstone is recorded via amendment)
        db.add(LegislationNodeVersion(node_id=pv.node_id, legislation_version_id=version.id,
                                      source_text=text, normalized_text=text,
                                      language=pv.language, effective_from=pv.effective_from,
                                      effective_to=None, source_locator=pv.source_locator,
                                      content_hash=content_hash(text)))
        carried += 1

    # INSERT: append a brand-new node + wording into the new version
    if operation == "INSERT" and node_type and node_number and new_text:
        nnode = LegislationNode(legislation_id=law.id, node_type=node_type,
                                number=str(node_number), sort_order=999)
        db.add(nnode)
        db.flush()
        db.add(LegislationNodeVersion(node_id=nnode.id, legislation_version_id=version.id,
                                      source_text=new_text, normalized_text=new_text,
                                      effective_from=effective_date,
                                      content_hash=content_hash(new_text)))

    # REPEAL: mark version repealed
    if operation == "REPEAL":
        version.status = "repealed"

    prior.status = "superseded"
    prior.effective_to = effective_date

    db.add(LegislationAmendment(jurisdiction=jurisdiction,
                                amending_legislation_id=None,
                                affected_legislation_id=law.id,
                                affected_node_id=node.id if node else None,
                                operation=operation,
                                previous_text=previous_text,
                                new_text=new_text,
                                publication_date=publication_date,
                                effective_date=effective_date,
                                source_snapshot_id=source_snapshot_id,
                                source_evidence=source_evidence or {}))
    law.current_version_id = version.id
    db.flush()
    _index_legislation_version(db, law, version)
    db.commit()
    db.refresh(law)
    return {"legislation_id": str(law.id), "version_number": vnum,
            "version_id": str(version.id), "operation": operation,
            "previous_text": previous_text, "new_text": new_text,
            "effective_date": effective_date.isoformat() if effective_date else None}


def amendments_between(db: Session, canonical_id: str, version_a_id=None, version_b_id=None) -> list:
    del version_a_id, version_b_id  # list all amendment events for the law
    law = db.query(Legislation).filter_by(canonical_id=canonical_id).first()
    if law is None:
        return []
    rows = db.query(LegislationAmendment).filter_by(affected_legislation_id=law.id)\
        .order_by(LegislationAmendment.effective_date).all()
    return [{"id": str(a.id), "operation": a.operation, "effective_date": a.effective_date and a.effective_date.isoformat(),
             "previous_text": a.previous_text, "new_text": a.new_text,
             "node_id": str(a.affected_node_id) if a.affected_node_id else None}
            for a in rows]


def diff_versions(db: Session, canonical_id: str, vbase_id, vtarget_id) -> dict:
    """Structural text diff between two versions' node wording (simple line-level)."""
    import difflib
    base = {nv.node_id: nv.source_text for nv in db.query(LegislationNodeVersion).filter_by(
        legislation_version_id=vbase_id).all()}
    target = {nv.node_id: nv.source_text for nv in db.query(LegislationNodeVersion).filter_by(
        legislation_version_id=vtarget_id).all()}
    changes = []
    for nid in set(base) | set(target):
        a, b = base.get(nid), target.get(nid)
        if a != b:
            changes.append({"node_id": str(nid), "old": a, "new": b})
    # unified diff of the concatenated texts
    whole_a = "\n".join(base[n] for n in sorted(base))
    whole_b = "\n".join(target[n] for n in sorted(target))
    unified = "".join(difflib.unified_diff(whole_a.splitlines(), whole_b.splitlines(), lineterm=""))
    return {"changed_nodes": len(changes), "changes": changes, "unified_diff": unified}