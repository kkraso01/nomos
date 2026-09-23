"""Research memo drafting.

Generates a deterministic draft from ACCEPTED matter facts/issues and VERIFIED
authorities. An authority is only included if it resolves to a real corpus node
(no fabricated citations). Output is always marked draft + lawyer review required
and carries the provenance of every cited source.
"""
from datetime import date

from sqlalchemy.orm import Session

from ..models.search import SearchEntry
from ..services import extract
from ..services.references import parse_reference


def _resolve_authority(db, cite: str) -> dict | None:
    """Return a verified authority record, or None if it does not exist."""
    ref = parse_reference(cite)
    if ref.kind == "legislation_article":
        hits = db.query(SearchEntry).filter_by(ref_law=ref.law_number,
                                               ref_article=ref.article_number).all()
    elif ref.kind == "judgment" and (ref.ecli or ref.case_number):
        fc = {"ecli": ref.ecli} if ref.ecli else {"case_number": ref.case_number}
        hits = db.query(SearchEntry).filter_by(**fc).all()
    elif ref.kind == "legislation":
        hits = db.query(SearchEntry).filter_by(ref_law=ref.law_number).all()
    else:
        hits = []
    if not hits:
        return None
    top = hits[0]
    return {"cite": cite, "canonical_ref": top.canonical_ref, "title": top.title,
            "text": (top.body or "")[:300]}


def draft_memo(db: Session, *, facts: list[str], issues: list[str],
               citations: list[str], template: str | None = None) -> dict:
    verified = []
    rejected = []
    for cite in citations:
        rec = _resolve_authority(db, cite)
        if rec:
            verified.append(rec)
        else:
            rejected.append(cite)  # nonexistent citation never enters the memo

    body_lines = []
    body_lines.append("FACTS (accepted matter facts):")
    body_lines += [f"  • {f}" for f in (facts or [])] or ["  (none)"]
    body_lines.append("")
    body_lines.append("ISSUES:")
    body_lines += [f"  • {i}" for i in (issues or [])] or ["  (none)"]
    body_lines.append("")
    body_lines.append("SUPPORTING AUTHORITIES (verified against corpus):")
    if verified:
        for v in verified:
            body_lines.append(f"  • {v['cite']} — {v['title']} [{v['canonical_ref']}]")
            body_lines.append(f"      {v['text']}")
    else:
        body_lines.append("  • No verified authority could be cited for this matter.")
    body_lines.append("")

    header = template or "NOMOS RESEARCH MEMO (draft)"
    memo = "\n".join([header, "=" * len(header), ""] + body_lines)

    return {
        "draft": memo,
        "status": "draft",
        "lawyer_review_required": True,
        "verified_citations": verified,
        "nonexistent_citations_rejected": rejected,
        "generated_at": date.today().isoformat(),
    }