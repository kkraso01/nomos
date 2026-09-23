"""Public corpus services: normalization, temporal version resolution, ingestion."""
import hashlib
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..models.corpus import (Legislation, LegislationVersion, LegislationNode,
                             Judgment, JudgmentVersion, JudgmentNode)
from .search import upsert_search_entry


def content_hash(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


# ---- Normalization: raw legislation text -> hierarchical nodes ----
_ARTICLE_RE = re.compile(r"^\s*(?:Article|Άρθρο)\s+([0-9IVXLC]+(?:[A-Z])?)\b", re.IGNORECASE)
_PARAGRAPH_RE = re.compile(r"^\s*\(([0-9]+[a-z]?)\)\b", re.IGNORECASE)
_SUB_RE = re.compile(r"^\s*\(([a-z])\)\b", re.IGNORECASE)


def normalize_legislation_text(raw_text: str) -> list[dict]:
    """Parse a representative legislation text into node dicts.

    This is an L0 deterministic parser (not a model). It recognizes:
      'Article N.' headings -> ARTICLE nodes
      '(n)' -> PARAGRAPH children
      plain body lines under an Article -> part of the article text
    Returns a flat list of {node_type, number, source_text}.
    """
    nodes = []
    lines = [ln.rstrip("\n") for ln in raw_text.splitlines()]
    current = None
    current_buf = []
    current_para = None

    def flush():
        if current is not None:
            nodes.append({"node_type": "ARTICLE", "number": current,
                          "source_text": "\n".join(current_buf).strip()})

    for ln in lines:
        m = _ARTICLE_RE.match(ln)
        if m:
            flush()
            current = m.group(1)
            current_buf = []
            current_para = None
            continue
        # paragraph detector works even without a preceding Article heading
        mp = _PARAGRAPH_RE.match(ln)
        if mp:
            if current is None:
                nodes.append({"node_type": "PARAGRAPH", "number": mp.group(1),
                              "source_text": ln.strip()})
                continue
            nodes.append({"node_type": "PARAGRAPH", "number": mp.group(1),
                          "source_text": ln.strip()})
            continue
        if current is None:
            continue  # leading title text, skipped for node model
        current_buf.append(ln)
    flush()
    return nodes


def ingest_legislation(db: Session, *, canonical_id: str, title: str,
                       jurisdiction: str, raw_text: str, language: str | None = None,
                       source_id=None, effective_from: datetime | None = None,
                       source_snapshot_id=None) -> tuple[Legislation, LegislationVersion, bool]:
    """Idempotent legislation ingest. Same content_hash -> return existing version.

    Different text with the same canonical identity becomes a NEW version
    (never a destructive overwrite). Returns (law, version, is_new_version).
    """
    h = content_hash(raw_text)
    law = db.query(Legislation).filter_by(canonical_id=canonical_id).first()
    if law is None:
        law = Legislation(canonical_id=canonical_id, title=title, jurisdiction=jurisdiction,
                          language=language, source_id=source_id)
        db.add(law)
        db.flush()
        new_law = True
    else:
        new_law = False

    existing = db.query(LegislationVersion).filter_by(
        legislation_id=law.id, content_hash=h).first()
    if existing is not None:
        db.commit()
        return law, existing, False

    version_number = (db.query(LegislationVersion)
                      .filter_by(legislation_id=law.id).count()) + 1
    # supersede prior current version
    prior = db.query(LegislationVersion).filter_by(
        legislation_id=law.id, status="current").first()
    effective_from = effective_from or (prior.effective_to if prior else datetime.now(timezone.utc))

    version = LegislationVersion(
        legislation_id=law.id, version_number=version_number, content_hash=h,
        effective_from=effective_from, status="current",
        supersedes_version_id=prior.id if prior else None,
        source_snapshot_id=source_snapshot_id,
    )
    db.add(version)
    db.flush()

    if prior:
        prior.status = "superseded"
        prior.effective_to = effective_from

    nodes = normalize_legislation_text(raw_text)
    for i, nd in enumerate(nodes):
        # find parent paragraph? flat ARTICLE + PARAGRAPH; PARAGRAPH under last ARTICLE
        parent = None
        if nd["node_type"] == "PARAGRAPH":
            parent = (db.query(LegislationNode).filter_by(
                version_id=version.id, node_type="ARTICLE").order_by(
                    LegislationNode.sort_order.desc()).first())
        db.add(LegislationNode(
            version_id=version.id, parent_id=parent.id if parent else None,
            node_type=nd["node_type"], number=nd.get("number"), source_text=nd["source_text"],
            normalized_text=nd["source_text"], language=language, sort_order=i,
            effective_from=effective_from,
        ))

    law.current_version_id = version.id
    db.commit()
    db.refresh(law)
    # rebuild search projection for this version's nodes
    nodes_q = db.query(LegislationNode).filter_by(version_id=version.id).all()
    for nd in nodes_q:
        upsert_search_entry(
            db, kind="legislation_node",
            canonical_ref=f"law-{canonical_id}-art-{nd.number or ''}",
            canonical_id=canonical_id, title=title,
            body=nd.source_text or nd.normalized_text or "", language=language or "en",
            ref_law=str(canonical_id), ref_article=nd.number, jurisdiction=jurisdiction,
            source_id=source_id)
    db.commit()
    db.refresh(law)
    return law, version, True


def resolve_version_as_of(db: Session, canonical_id: str,
                          as_of: datetime | None = None) -> LegislationVersion | None:
    """Resolve the legislation version effective as of `as_of` (or latest)."""
    law = db.query(Legislation).filter_by(canonical_id=canonical_id).first()
    if law is None:
        return None
    as_of = as_of or datetime.now(timezone.utc)
    versions = (db.query(LegislationVersion)
                .filter_by(legislation_id=law.id)
                .order_by(LegislationVersion.effective_from).all())
    applicable = None
    for v in versions:
        start = v.effective_from
        end = v.effective_to
        if start is not None and start <= as_of and (end is None or as_of < end):
            applicable = v
    return applicable or versions[-1] if versions else None


def ingest_judgment(db: Session, *, canonical_id: str, title: str, court: str | None,
                    case_number: str | None, judgment_date, raw_text: str,
                    source_id=None, source_snapshot_id=None, ecli: str | None = None) -> tuple[Judgment, JudgmentVersion, bool]:
    h = content_hash(raw_text)
    judgment = db.query(Judgment).filter_by(canonical_id=canonical_id).first()
    if judgment is None:
        judgment = Judgment(canonical_id=canonical_id, title=title, court=court,
                            case_number=case_number, judgment_date=judgment_date,
                            source_id=source_id, ecli=ecli)
        db.add(judgment)
        db.flush()
    existing = db.query(JudgmentVersion).filter_by(
        judgment_id=judgment.id, content_hash=h).first()
    if existing is not None:
        db.commit()
        return judgment, existing, False

    vnum = (db.query(JudgmentVersion).filter_by(judgment_id=judgment.id).count()) + 1
    version = JudgmentVersion(judgment_id=judgment.id, version_number=vnum, content_hash=h,
                              source_snapshot_id=source_snapshot_id,
                              published_at=judgment_date)
    db.add(version)
    db.flush()

    paras = [p for p in (line.strip() for line in raw_text.splitlines()) if p]
    for i, para in enumerate(paras):
        db.add(JudgmentNode(version_id=version.id, para_number=str(i + 1), text=para,
                            sort_order=i))
    judgment.current_version_id = version.id
    db.commit()
    db.refresh(judgment)
    ref = ecli if ecli else (case_number or canonical_id)
    paras = db.query(JudgmentNode).filter_by(version_id=version.id).all()
    body = "\n".join(p.text for p in paras)
    upsert_search_entry(
        db, kind="judgment_node", canonical_ref=f"judgment-{ref}", canonical_id=canonical_id,
        title=title, body=body, language="en",
        ecli=ecli, case_number=case_number, court=court, jurisdiction="CY",
        source_id=source_id)
    db.commit()
    db.refresh(judgment)
    return judgment, version, True