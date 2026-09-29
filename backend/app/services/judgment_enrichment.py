"""Deterministic judgment enrichment: link paragraphs (as evidence) to
legislation provisions and to cited cases, from in-text legal references.

Produced links are bibliographic/reference-based (CITES / APPLIES / INTERPRETS)
and start REVIEW_REQUIRED; semantic treatment classification requires separate
validation (never invented here).
"""
from sqlalchemy.orm import Session

from ..models.core import (Judgment, JudgmentSection, JudgmentParagraph, Legislation,
                           LegislationNode, CaseCitation, JudgmentLegislationLink)
from ..services.references import extract_references


def enrich_judgment(db: Session, canonical_id: str, applicable_law_canonical_id: str | None = None) -> dict:
    judgment = db.query(Judgment).filter_by(canonical_id=canonical_id).first()
    if judgment is None:
        return {"errors": ["judgment not found"]}
    if judgment.current_version_id is None:
        return {"errors": ["no version"]}

    law_node_by_article = {}
    if applicable_law_canonical_id:
        law = db.query(Legislation).filter_by(canonical_id=applicable_law_canonical_id).first()
        if law:
            for n in db.query(LegislationNode).filter_by(legislation_id=law.id,
                                                         node_type="ARTICLE").all():
                law_node_by_article[n.number] = (law.id, n.id)

    legislation_links = 0
    citations = 0
    for sec in db.query(JudgmentSection).filter_by(version_id=judgment.current_version_id)\
            .order_by(JudgmentSection.sort_order).all():
        for p in db.query(JudgmentParagraph).filter_by(section_id=sec.id)\
                .order_by(JudgmentParagraph.sort_order).all():
            refs = extract_references(p.text or "")
            for ref in refs:
                if ref["kind"] == "article" and ref["article"] in law_node_by_article:
                    law_id, node_id = law_node_by_article[ref["article"]]
                    exists = db.query(JudgmentLegislationLink).filter_by(
                        judgment_id=judgment.id, provision_node_id=node_id,
                        evidence_paragraph_id=p.id).first()
                    if exists is None:
                        db.add(JudgmentLegislationLink(
                            judgment_id=judgment.id, judgment_key=judgment.canonical_id,
                            judgment_jurisdiction=judgment.jurisdiction,
                            legislation_id=law_id, provision_node_id=node_id,
                            legislation_jurisdiction=judgment.jurisdiction,
                            relationship="APPLIES", evidence_paragraph_id=p.id,
                            review_status="review_required"))
                        legislation_links += 1
                elif ref["kind"] == "judgment_ecli":
                    exists = db.query(CaseCitation).filter_by(
                        source_case_id=judgment.id, target_case_key=ref["ecli"],
                        evidence_paragraph_id=p.id).first()
                    if exists is None:
                        db.add(CaseCitation(source_case_id=judgment.id,
                                            source_case_key=judgment.canonical_id,
                                            source_jurisdiction=judgment.jurisdiction,
                                            target_case_key=ref["ecli"],
                                            target_jurisdiction=ref["ecli"].split(":")[1] if ":" in ref["ecli"] else None,
                                            kind="CITES", evidence_paragraph_id=p.id,
                                            review_status="review_required"))
                        citations += 1
    db.commit()
    return {"canonical_id": canonical_id, "legislation_links_created": legislation_links,
            "case_citations_created": citations}