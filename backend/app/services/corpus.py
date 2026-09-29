"""Canonical corpus services (jurisdiction-agnostic core).

Legislation: permanent provision identity (LegislationNode) is separate from its
versioned wording (LegislationNodeVersion). Ingest is appended-into-a-version and
hash-deduped; an amendment of the same law creates a new version, never overwrites.
Judgments: structured into JudgmentSection + JudgmentParagraph under a version.
"""
import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .search import upsert_search_entry
from ..models.core import (
    Legislation, LegislationVersion, LegislationNode, LegislationNodeVersion,
    Judgment, JudgmentVersion, JudgmentSection, JudgmentParagraph,
)


def content_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ---- L0 structural normalizer (jurisdiction-configurable node terms) ----
_ARTICLE_RE = re.compile(r"^\s*(?:Article|Άρθρο)\s+([0-9IVXLC]+(?:[A-Z]|\(\d+\))*)(?:\.|\b)", re.IGNORECASE)
_PARAGRAPH_RE = re.compile(r"^\s*\(([0-9]+[a-z]?)\)\b", re.IGNORECASE)


def normalize_legislation_text(raw_text: str) -> list[dict]:
    """Determine structural heads: ARTICLE + PARAGRAPH nodes (flat list)."""
    nodes = []
    lines = [ln.rstrip("\n") for ln in raw_text.splitlines()]
    current = None
    buf: list[str] = []

    def flush():
        if current is not None:
            body = "\n".join(buf).strip()
            nodes.append({"node_type": "ARTICLE", "number": current, "source_text": body})
            buf.clear()

    for ln in lines:
        m = _ARTICLE_RE.match(ln)
        if m:
            flush()
            current = m.group(1)
            buf = []
            continue
        mp = _PARAGRAPH_RE.match(ln)
        if mp:
            # a paragraph under the previous article
            nodes.append({"node_type": "PARAGRAPH", "number": mp.group(1),
                          "source_text": ln.strip(), "parent_article": current})
            continue
        if current is None:
            continue
        buf.append(ln)
    flush()
    return nodes


def _node_number(n: dict) -> str:
    nnum = n.get("number")
    if n.get("node_type") == "PARAGRAPH" and nnum:
        return nnum
    return nnum or ""


def ingest_legislation(db: Session, *, canonical_id: str, title: str, jurisdiction: str,
                       raw_text: str, language: str | None = None, source_id=None,
                       effective_from: datetime | None = None,
                       source_snapshot_id=None) -> tuple[Legislation, LegislationVersion, bool]:
    h = content_hash(raw_text)
    law = db.query(Legislation).filter_by(canonical_id=canonical_id).first()
    if law is None:
        law = Legislation(canonical_id=canonical_id, title=title, jurisdiction=jurisdiction,
                          language=language, source_id=source_id)
        db.add(law)
        db.flush()

    existing = db.query(LegislationVersion).filter_by(
        legislation_id=law.id, content_hash=h).first()
    if existing is not None:
        # projection is rebuildable: keep the lexical index idempotently in sync
        _index_legislation_version(db, law, existing)
        db.commit()
        return law, existing, False

    vnum = (db.query(LegislationVersion).filter_by(legislation_id=law.id).count()) + 1
    prior = db.query(LegislationVersion).filter_by(legislation_id=law.id, status="current").first()
    eff = effective_from or (prior.effective_to if prior else datetime.now(timezone.utc))

    version = LegislationVersion(legislation_id=law.id, version_number=vnum, content_hash=h,
                                 effective_from=eff, status="current",
                                 supersedes_version_id=prior.id if prior else None,
                                 source_snapshot_id=source_snapshot_id)
    db.add(version)
    db.flush()
    if prior:
        prior.status = "superseded"
        prior.effective_to = eff

    # Build permanent node identities + versioned wording.
    for i, nd in enumerate(normalize_legislation_text(raw_text)):
        number = _node_number(nd)
        node_type = nd["node_type"]
        parent = None
        if node_type == "PARAGRAPH":
            art = nd.get("parent_article")
            if art:
                parent = db.query(LegislationNode).filter_by(
                    legislation_id=law.id, node_type="ARTICLE", number=art).first()
        node = db.query(LegislationNode).filter_by(
            legislation_id=law.id, node_type=node_type, number=number).first()
        if node is None:
            node = LegislationNode(legislation_id=law.id, node_type=node_type,
                                   number=number, parent_id=parent.id if parent else None,
                                   sort_order=i)
            db.add(node)
            db.flush()
        elif parent is not None:
            node.parent_id = parent.id
        db.add(LegislationNodeVersion(
            node_id=node.id, legislation_version_id=version.id,
            source_text=nd["source_text"], normalized_text=nd["source_text"],
            language=language, effective_from=eff,
            source_locator={"canonical_id": canonical_id, "node_type": node_type,
                            "number": number, "article": nd.get("parent_article")},
            content_hash=content_hash(nd["source_text"])))

    # Repopulate the lexical search projection from this version's wording.
    _index_legislation_version(db, law, version)
    law.current_version_id = version.id
    db.commit()
    db.refresh(law)
    return law, version, True


def _index_legislation_version(db, law, version):
    """Index this version's wording into the lexical projection.

    Materialize raw column values (safe across the per-row commits inside
    upsert_search_entry) and index every node, adding article context to
    paragraph chunks so the real legal text is searchable.
    """
    from sqlalchemy import select
    stmt = (
        select(LegislationNode.id, LegislationNode.node_type, LegislationNode.number,
               LegislationNode.parent_id, LegislationNodeVersion.source_text,
               LegislationNodeVersion.language)
        .join(LegislationNodeVersion, LegislationNodeVersion.node_id == LegislationNode.id)
        .where(LegislationNodeVersion.legislation_version_id == version.id)
        .order_by(LegislationNode.sort_order)
    )
    rows = db.execute(stmt).mappings().all()
    by_id = {r["id"]: r for r in rows}
    for r in rows:
        node_type, number = r["node_type"], r["number"] or ""
        if node_type == "PARAGRAPH" and r["parent_id"]:
            parent = by_id.get(r["parent_id"])
            article_no = parent["number"] if parent else None
            ref = f"law-{law.canonical_id}-art-{article_no or ''}-p{number}" if number else None
            ref_article = article_no
        else:
            ref = f"law-{law.canonical_id}-art-{number}" if number else None
            ref_article = number
        if not ref or not r["source_text"]:
            continue
        upsert_search_entry(
            db, kind="legislation_node", canonical_ref=ref,
            canonical_id=law.canonical_id, title=law.title,
            body=r["source_text"], language=r["language"] or law.language or "en",
            ref_law=str(law.canonical_id), ref_article=ref_article,
            jurisdiction=law.jurisdiction, source_id=law.source_id)
    db.flush()


def resolve_version_as_of(db: Session, canonical_id: str,
                          as_of: datetime | None = None) -> LegislationVersion | None:
    law = db.query(Legislation).filter_by(canonical_id=canonical_id).first()
    if law is None:
        return None
    as_of = as_of or datetime.now(timezone.utc)
    versions = (db.query(LegislationVersion)
                .filter_by(legislation_id=law.id)
                .order_by(LegislationVersion.effective_from).all())
    applicable = None
    for v in versions:
        start, end = v.effective_from, v.effective_to
        if start is not None and start <= as_of and (end is None or as_of < end):
            applicable = v
    return applicable or (versions[-1] if versions else None)


def node_contents_for_version(db: Session, version_id) -> list[dict]:
    rows = db.query(LegislationNode, LegislationNodeVersion).join(
        LegislationNodeVersion, LegislationNodeVersion.node_id == LegislationNode.id).filter(
        LegislationNodeVersion.legislation_version_id == version_id)\
        .order_by(LegislationNode.sort_order).all()
    return [{"id": str(n.id), "node_type": n.node_type, "number": n.number,
             "parent_id": str(n.parent_id) if n.parent_id else None,
             "text": nv.source_text} for n, nv in rows]


# ---- Judgments: sections + paragraphs ----
_SEG_HEADINGS = {
    "facts": "facts", "the facts": "facts",
    "procedural history": "procedural_history",
    "issue": "issue", "issues": "issue", "the issue": "issue", "the issues": "issue",
    "party argument": "party_argument", "arguments": "party_argument",
    "legal analysis": "legal_analysis", "the law": "legal_analysis", "reasoning": "legal_analysis",
    "holding": "holding", "decision": "holding", "conclusion": "holding",
    "order": "order", "costs": "order",
    "separate opinion": "separate_opinion", "dissent": "separate_opinion",
}


def segment_judgment_text(raw_text: str) -> list[dict]:
    """Return [{section_type, title, paragraphs:[str]}] from headings + body lines."""
    sections: list[dict] = []
    current = None
    for ln in raw_text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        key = ln.lower().rstrip(":.")
        seg = _SEG_HEADINGS.get(key)
        if seg:
            current = seg
            sections.append({"section_type": seg, "title": ln, "paragraphs": []})
            continue
        if sections:
            sections[-1]["paragraphs"].append(ln)
        else:
            sections.append({"section_type": "body", "title": None, "paragraphs": [ln]})
    return sections


def ingest_judgment(db: Session, *, canonical_id: str, title: str, jurisdiction: str = "CY",
                    court: str | None = None, court_id=None, case_number: str | None = None,
                    ecli: str | None = None, judgment_date=None, judges=None,
                    language: str | None = None, raw_text: str, source_id=None,
                    source_snapshot_id=None) -> tuple[Judgment, JudgmentVersion, bool]:
    h = content_hash(raw_text)
    judgment = db.query(Judgment).filter_by(canonical_id=canonical_id).first()
    if judgment is None:
        judgment = Judgment(canonical_id=canonical_id, title=title, jurisdiction=jurisdiction,
                            court=court, court_id=court_id, case_number=case_number, ecli=ecli,
                            judgment_date=judgment_date, judges=judges,
                            language=language, source_id=source_id)
        db.add(judgment)
        db.flush()
    existing = db.query(JudgmentVersion).filter_by(
        judgment_id=judgment.id, content_hash=h).first()
    if existing is not None:
        db.commit()
        return judgment, existing, False

    vnum = (db.query(JudgmentVersion).filter_by(judgment_id=judgment.id).count()) + 1
    version = JudgmentVersion(judgment_id=judgment.id, version_number=vnum, content_hash=h,
                              source_snapshot_id=source_snapshot_id, published_at=judgment_date)
    db.add(version)
    db.flush()

    para_no = 0
    for sec in segment_judgment_text(raw_text):
        sect = JudgmentSection(version_id=version.id, section_type=sec["section_type"],
                               title=sec["title"], sort_order=para_no)
        db.add(sect)
        db.flush()
        for p in sec["paragraphs"]:
            para_no += 1
            db.add(JudgmentParagraph(version_id=version.id, section_id=sect.id,
                                     para_number=str(para_no), text=p, sort_order=para_no,
                                     language=language))
    judgment.current_version_id = version.id
    db.commit()
    db.refresh(judgment)
    ref = ecli or case_number or f"judgment-{canonical_id}"
    body = "\n".join(p.text for p in db.query(JudgmentParagraph).filter_by(
        version_id=version.id).all())
    upsert_search_entry(db, kind="judgment_node", canonical_ref=f"judgment-{ref}",
                        canonical_id=canonical_id, title=title, body=body, language=language or "en",
                        ecli=ecli, case_number=case_number, court=court, jurisdiction=jurisdiction,
                        source_id=source_id)
    db.commit()
    db.refresh(judgment)
    return judgment, version, True


def resolve_judgment_segments(db: Session, canonical_id: str) -> list[dict] | None:
    judgment = db.query(Judgment).filter_by(canonical_id=canonical_id).first()
    if judgment is None or judgment.current_version_id is None:
        return None
    version_id = judgment.current_version_id
    out = []
    sections = db.query(JudgmentSection).filter_by(version_id=version_id)\
        .order_by(JudgmentSection.sort_order).all()
    for s in sections:
        paras = db.query(JudgmentParagraph).filter_by(section_id=s.id)\
            .order_by(JudgmentParagraph.sort_order).all()
        out.append({"section_type": s.section_type, "title": s.title,
                    "paragraphs": [{"para_number": p.para_number, "text": p.text,
                                    "char_start": p.char_start, "char_end": p.char_end}
                                   for p in paras]})
    return out


def summarize_judgment(db: Session, canonical_id: str) -> dict:
    """Extractive, source-grounded summary from holding/legal_analysis/order paragraphs."""
    judgment = db.query(Judgment).filter_by(canonical_id=canonical_id).first()
    if judgment is None:
        return {"ok": False}
    version_id = judgment.current_version_id
    preferred = ["holding", "legal_analysis", "order"]
    summary = []
    for seg_type in preferred:
        sect = db.query(JudgmentSection).filter_by(version_id=version_id,
                                                   section_type=seg_type).first()
        if sect is None:
            continue
        for p in db.query(JudgmentParagraph).filter_by(section_id=sect.id)\
                .order_by(JudgmentParagraph.sort_order).all():
            if len((p.text or "").split()) >= 3:
                summary.append({"text": p.text, "section": seg_type,
                                "para_number": p.para_number})
            if len(summary) >= 3:
                break
        if len(summary) >= 3:
            break
    return {"ok": True, "canonical_id": canonical_id, "mode": "extractive",
            "source_grounded": True,
            "summary": summary or [{"text": "(no extractive holding text available)",
                                    "section": "holding"}]}