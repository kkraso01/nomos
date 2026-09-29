"""Research vertical (task-3): research query -> ranked authorities enriched with
exact evidence spans + authority detail, ready to save/classify into a matter.

Wraps hybrid_search and adds, per result:
- evidence: exact supporting judgment paragraphs (with char spans) or the exact
  provision text/span for legislation (resolved to the applicable version);
- detail: court/date/jurisdiction/version/cited-citing-treatment where available.
Avoids opaque similarity percentages: explanation always states WHY it matched.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models.core import (Legislation, LegislationNode, LegislationNodeVersion,
                           Judgment, JudgmentSection, JudgmentParagraph)
from ..services.hybrid import hybrid_search
from ..services.corpus import resolve_version_as_of
from ..services.citation import expand_case


def _artifact_key(canonical_ref: str) -> tuple[str, str]:
    """Return (kind, key) from a canonical_ref."""
    if canonical_ref.startswith("law-"):
        return "legislation", canonical_ref[4:].split("-art-")[0]
    if canonical_ref.startswith("judgment-"):
        return "judgment", canonical_ref[len("judgment-"):]
    return "other", canonical_ref


def _evidence(db: Session, kind: str, key: str, article: str | None, query_date) -> list[dict]:
    if kind == "judgment":
        j = db.query(Judgment).filter_by(case_number=key).first() or \
            db.query(Judgment).filter_by(canonical_id=key).first()
        if j is None or j.current_version_id is None:
            return []
        out = []
        for sec in db.query(JudgmentSection).filter_by(version_id=j.current_version_id)\
                .order_by(JudgmentSection.sort_order).all():
            for p in db.query(JudgmentParagraph).filter_by(section_id=sec.id)\
                    .order_by(JudgmentParagraph.sort_order).all():
                out.append({"type": "judgment_paragraph", "section": sec.section_type,
                            "para_number": p.para_number, "text": p.text,
                            "char_start": p.char_start, "char_end": p.char_end})
        return out
    if kind == "legislation" and article:
        law = db.query(Legislation).filter_by(canonical_id=key).first()
        if law is None:
            return []
        version = resolve_version_as_of(db, key,
                                        datetime(query_date.year, query_date.month, query_date.day,
                                                 tzinfo=timezone.utc)
                                        if query_date else None)
        vid = version.id if version else law.current_version_id
        node = db.query(LegislationNode).filter_by(legislation_id=law.id,
                                                   node_type="ARTICLE", number=str(article)).first()
        if node:
            nv = db.query(LegislationNodeVersion).filter_by(
                node_id=node.id, legislation_version_id=vid).first()
            if nv:
                loc = nv.source_locator or {}
                return [{"type": "provision", "article": article,
                         "text": nv.source_text, "span": loc.get("span"),
                         "language": nv.language}]
    return []


def _detail(db: Session, kind: str, key: str) -> dict:
    if kind == "legislation":
        law = db.query(Legislation).filter_by(canonical_id=key).first()
        return {"authority_type": "legislation",
                "name": law.title if law else key,
                "jurisdiction": law.jurisdiction if law else None}
    if kind == "judgment":
        j = db.query(Judgment).filter_by(case_number=key).first() or \
            db.query(Judgment).filter_by(canonical_id=key).first()
        base = {"authority_type": "judgment"}
        if j:
            base.update({"name": j.title, "jurisdiction": j.jurisdiction, "court": j.court,
                         "case_number": j.case_number, "ecli": j.ecli,
                         "judgment_date": j.judgment_date.isoformat() if j.judgment_date else None,
                         "judges": j.judges})
        try:
            exp = expand_case(db, case_key=key if j is None else (j.case_number or j.canonical_id))
            base["cited"] = exp["cited"]
            base["citing"] = exp["citing"]
            base["treatments"] = exp["treatments"]
            base["legislation_links"] = exp["legislation_links"]
        except Exception:  # noqa: BLE001
            base["cited"] = []
            base["citing"] = []
        return base
    return {"authority_type": "other"}


def research(db: Session, query: str, *, as_of=None, limit: int = 20,
             relevance_hint: str | None = None) -> dict:
    out = hybrid_search(db, query, as_of=as_of, limit=limit)
    # normalise as_of to a date (hybrid_search returns an ISO string)
    asof = out.get("as_of")
    if isinstance(asof, str):
        try:
            asof = datetime.fromisoformat(asof).date()
        except ValueError:
            asof = None
    results = []
    for r in out["results"]:
        kind, key = _artifact_key(r["canonical_ref"])
        article = None
        if kind == "legislation":
            parts = r["canonical_ref"].split("-art-")
            article = parts[1] if len(parts) == 2 else None
        evidence = _evidence(db, kind, key, article, asof)
        detail = _detail(db, kind, key)
        results.append({
            "canonical_ref": r["canonical_ref"], "kind": r["kind"],
            "title": r["title"], "text": r["text"], "language": r["language"],
            "why": r.get("explanation", []), "temporal": r.get("temporal"),
            "exact": r.get("exact", False),
            "evidence": evidence, "detail": detail,
        })
    return {"query": query, "as_of": out.get("as_of"), "count": len(results),
            "results": results}