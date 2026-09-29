"""Legal graph services (jurisdiction-agnostic).

CITCES / treatment edges, judgment->legislation links, provision cross-references,
and graph expansion. Semantic treatment is evidence-backed and starts
REVIEW_REQUIRED unless validated.
"""
import uuid

from sqlalchemy.orm import Session

from ..models.core import (CaseCitation, JudgmentLegislationLink, ProvisionCrossReference,
                           CaseTreatment, Judgment, LegislationNode)

SEMANTIC_TREATMENTS = {"FOLLOWS", "DISTINGUISHES", "APPROVES", "CRITICISES",
                       "OVERRULES", "DISCUSSES"}


def create_case_citation(db: Session, *, source_case_id=None, source_jurisdiction=None,
                         source_case_key=None, target_case_id=None, target_jurisdiction=None,
                         target_case_key=None, kind: str = "CITES",
                         evidence_paragraph_id=None) -> CaseCitation:
    citation = CaseCitation(source_case_id=source_case_id,
                            source_jurisdiction=source_jurisdiction,
                            source_case_key=source_case_key, target_case_id=target_case_id,
                            target_jurisdiction=target_jurisdiction, target_case_key=target_case_key,
                            kind=kind, evidence_paragraph_id=evidence_paragraph_id)
    db.add(citation)
    db.commit()
    db.refresh(citation)
    return citation


def create_treatment(db: Session, *, source_case_id=None, source_case_key=None,
                     source_jurisdiction=None, target_case_id=None, target_case_key=None,
                     target_jurisdiction=None, treatment: str, evidence_paragraph_id=None,
                     confidence=None, review_status="review_required") -> CaseTreatment:
    if treatment not in SEMANTIC_TREATMENTS:
        treatment = "DISCUSSES"
    rec = CaseTreatment(source_case_id=source_case_id, source_case_key=source_case_key,
                        source_case_jurisdiction=source_jurisdiction, target_case_id=target_case_id,
                        target_case_key=target_case_key, target_case_jurisdiction=target_jurisdiction,
                        treatment=treatment, evidence_paragraph_id=evidence_paragraph_id,
                        confidence=confidence, review_status=review_status)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def create_judgment_legislation_link(db: Session, *, judgment_id=None, judgment_key=None,
                                     judgment_jurisdiction=None, legislation_id=None,
                                     provision_node_id=None, provision_external_key=None,
                                     legislation_jurisdiction=None, relationship="APPLIES",
                                     evidence_paragraph_id=None,
                                     review_status="review_required") -> JudgmentLegislationLink:
    link = JudgmentLegislationLink(judgment_id=judgment_id, judgment_key=judgment_key,
                                   judgment_jurisdiction=judgment_jurisdiction,
                                   legislation_id=legislation_id,
                                   provision_node_id=provision_node_id,
                                   provision_external_key=provision_external_key,
                                   legislation_jurisdiction=legislation_jurisdiction,
                                   relationship=relationship,
                                   evidence_paragraph_id=evidence_paragraph_id,
                                   review_status=review_status)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def create_provision_reference(db: Session, *, source_node_id, target_node_id=None,
                               source_jurisdiction, target_jurisdiction=None,
                               target_external_key=None, source_text=None,
                               source_span_start=None, source_span_end=None,
                               confidence="high", relationship="REFERENCES") -> ProvisionCrossReference:
    ref = ProvisionCrossReference(source_node_id=source_node_id,
                                  jurisdiction=source_jurisdiction,
                                  target_node_id=target_node_id,
                                  target_jurisdiction=target_jurisdiction,
                                  target_external_key=target_external_key,
                                  source_text=source_text,
                                  source_span_start=source_span_start,
                                  source_span_end=source_span_end,
                                  confidence=confidence, relationship=relationship)
    db.add(ref)
    db.commit()
    db.refresh(ref)
    return ref


def _case(out, c, is_source: bool):
    if is_source:
        return {"jurisdiction": c.source_jurisdiction, "case_id": str(c.source_case_id) if c.source_case_id else None,
                "key": c.source_case_key}
    return {"jurisdiction": c.target_jurisdiction, "case_id": str(c.target_case_id) if c.target_case_id else None,
            "key": c.target_case_key}


def expand_case(db: Session, case_id=None, case_key=None) -> dict:
    from sqlalchemy import or_
    clause = []
    if case_id:
        clause.append(CaseCitation.source_case_id == case_id)
    if case_key:
        clause.append(CaseCitation.source_case_key == case_key)
    q = db.query(CaseCitation)
    if clause:
        q = q.filter(or_(*clause))
    cited = q.all()
    citing = db.query(CaseCitation).filter(
        (CaseCitation.target_case_id == case_id) if case_id else (CaseCitation.target_case_key == case_key)).all()
    treatments = db.query(CaseTreatment).filter(
        (CaseTreatment.source_case_id == case_id) if case_id else (CaseTreatment.source_case_key == case_key)).all()
    legislation = db.query(JudgmentLegislationLink).filter(
        (JudgmentLegislationLink.judgment_id == case_id) if case_id
        else (JudgmentLegislationLink.judgment_key == case_key)).all()
    return {
        "cited": [{"kind": c.kind, **(_case(c, c, False))} for c in cited],
        "citing": [{"kind": c.kind, **(_case(c, c, True))} for c in citing],
        "treatments": [{"treatment": t.treatment, "review_status": t.review_status,
                        "evidence_paragraph_id": str(t.evidence_paragraph_id) if t.evidence_paragraph_id else None}
                       for t in treatments],
        "legislation_links": [{"relationship": l.relationship,
                               "provision_external_key": l.provision_external_key,
                               "legislation_jurisdiction": l.legislation_jurisdiction,
                               "provision_node_id": str(l.provision_node_id) if l.provision_node_id else None}
                              for l in legislation],
    }


def expand_provision(db: Session, node_id=None, external_key=None) -> dict:
    q = db.query(ProvisionCrossReference)
    if node_id:
        incoming = db.query(ProvisionCrossReference).filter_by(target_node_id=node_id).all()
        outgoing = db.query(ProvisionCrossReference).filter_by(source_node_id=node_id).all()
    else:
        incoming = db.query(ProvisionCrossReference).filter_by(target_external_key=external_key).all()
        outgoing = db.query(ProvisionCrossReference).filter_by(target_external_key=external_key).all()
        outgoing = []
    links = db.query(JudgmentLegislationLink).filter_by(provision_node_id=node_id).all()
    return {
        "references_out": [{"relationship": r.relationship, "target_node_id": str(r.target_node_id) if r.target_node_id else None,
                            "target_external_key": r.target_external_key, "target_jurisdiction": r.target_jurisdiction,
                            "span": [r.source_span_start, r.source_span_end]}
                           for r in outgoing],
        "referenced_by": [{"relationship": r.relationship, "source_node_id": str(r.source_node_id) if r.source_node_id else None,
                           "source_jurisdiction": r.jurisdiction} for r in incoming],
        "cases": [{"relationship": l.relationship, "judgment_id": str(l.judgment_id) if l.judgment_id else None,
                   "judgment_key": l.judgment_key} for l in links],
    }