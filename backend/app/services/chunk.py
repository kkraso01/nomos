"""Structural legal chunking (PARAGRAPH + SECTION units, hierarchy context)."""
import hashlib
import uuid

from sqlalchemy.orm import Session

from ..models.core import (Legislation, LegislationNode, LegislationNodeVersion,
                           Judgment, JudgmentSection, JudgmentParagraph, LegalChunk)


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _leg_context(law, node) -> str:
    parts = [f"Law: {law.title}", f"Jurisdiction: {law.jurisdiction}"]
    if node.node_type in ("ARTICLE", "PARAGRAPH"):
        parts.append(f"Article {node.number}")
    return "\n".join(parts)


def _emit(db: Session, *, jurisdiction, document_type, document_id, document_key,
          version_id, chunk_type, text, hierarchy_context, paragraph_number=None,
          parent_node_id=None, section_id=None, law_id=None, article_number=None,
          effective_from=None, effective_to=None, source_locator=None,
          language=None, seed_prefix=""):
    seed = uuid.uuid5(uuid.NAMESPACE_URL, f"nomos-{seed_prefix}{document_id}:{version_id}:{chunk_type}:{(paragraph_number or 'sec')}:{section_id or ''}")
    if db.get(LegalChunk, seed) is not None:
        return  # idempotent: chunk already present for this canonical unit
    db.add(LegalChunk(
        id=seed, jurisdiction=jurisdiction, document_type=document_type,
        document_id=document_id, document_key=document_key, version_id=version_id,
        chunk_type=chunk_type, text=text, hierarchy_context=hierarchy_context,
        normalized_text=text, language=language, parent_node_id=parent_node_id,
        section_id=section_id, paragraph_number=paragraph_number, law_id=law_id,
        article_number=article_number, effective_from=effective_from, effective_to=effective_to,
        source_locator=source_locator, content_hash=_hash(text)))


def chunk_legislation(db: Session, law: Legislation, version_id, parser_version: str | None = None) -> int:
    rows = db.query(LegislationNode, LegislationNodeVersion).join(
        LegislationNodeVersion, LegislationNodeVersion.node_id == LegislationNode.id).filter(
        LegislationNodeVersion.legislation_version_id == version_id)\
        .order_by(LegislationNode.sort_order).all()
    created = 0
    for node, nv in rows:
        src = nv.source_text or ""
        if not src:
            continue
        ctx = _leg_context(law, node)
        law_no = node.number if node.node_type in ("ARTICLE", "PARAGRAPH") else None
        _emit(db, jurisdiction=law.jurisdiction, document_type="legislation", document_id=law.id,
              document_key=law.canonical_id, version_id=version_id, chunk_type="paragraph",
              text=src, hierarchy_context=ctx, paragraph_number=node.number,
              parent_node_id=node.id, law_id=law.id, article_number=law_no,
              effective_from=nv.effective_from, effective_to=nv.effective_to,
              source_locator=nv.source_locator, language=nv.language or law.language,
              seed_prefix="L")
        created += 1
    db.flush()
    return created


def chunk_judgment(db: Session, judgment: Judgment, version_id, parser_version: str | None = None) -> int:
    created = 0
    for s in db.query(JudgmentSection).filter_by(version_id=version_id)\
            .order_by(JudgmentSection.sort_order).all():
        paras = db.query(JudgmentParagraph).filter_by(section_id=s.id)\
            .order_by(JudgmentParagraph.sort_order).all()
        sec_text = "\n".join(p.text for p in paras)
        cctx = f"{judgment.title or ''}\nSection: {s.section_type}"
        if sec_text:
            _emit(db, jurisdiction=judgment.jurisdiction, document_type="judgment",
                  document_id=judgment.id, document_key=judgment.canonical_id,
                  version_id=version_id, chunk_type="section", text=sec_text,
                  hierarchy_context=cctx, section_id=s.id,
                  source_locator={"section": s.section_type}, seed_prefix="J")
            created += 1
        for p in paras:
            _emit(db, jurisdiction=judgment.jurisdiction, document_type="judgment",
                  document_id=judgment.id, document_key=judgment.canonical_id,
                  version_id=version_id, chunk_type="paragraph", text=p.text,
                  hierarchy_context=cctx, section_id=s.id, paragraph_number=p.para_number,
                  source_locator={"section": s.section_type, "para": p.para_number}, seed_prefix="J")
            created += 1
    db.flush()
    return created