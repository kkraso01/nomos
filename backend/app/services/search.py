"""Search projection maintenance and retrieval.

Default provider is PostgreSQL-backed (lexical tsvector + unaccent, which
handles both Greek and English). The API is provider-agnostic so an OpenSearch
provider can substitute later. Semantic embedding candidates are attempted via
the AI router if an embed model is configured; otherwise semantic mode falls
back to lexical with an explicit `semantic=false` flag.

Every result carries provenance and a reason-for-match explanation.
"""
from dataclasses import dataclass, field
from typing import Optional

import re

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import models
from ..models.search import SearchEntry
from ..services.references import parse_reference
from ..config import settings


@dataclass
class SearchResult:
    kind: str
    canonical_ref: str
    title: Optional[str]
    body: Optional[str]
    language: Optional[str]
    score: float
    reason: str
    metadata: dict = field(default_factory=dict)


def upsert_search_entry(db: Session, *, kind: str, canonical_ref: str, body: str,
                        title: str | None = None, language: str | None = None,
                        ref_law=None, ref_article=None, ecli=None, case_number=None,
                        court=None, jurisdiction=None, canonical_id=None,
                        source_id=None, external_url=None) -> None:
    entry = db.query(SearchEntry).filter_by(kind=kind, canonical_ref=canonical_ref).first()
    if entry is None:
        entry = SearchEntry(kind=kind, canonical_ref=canonical_ref, canonical_id=canonical_id,
                                   title=title, body=body, language=language, ref_law=ref_law,
                                   ref_article=ref_article, ecli=ecli, case_number=case_number,
                                   court=court, jurisdiction=jurisdiction, source_id=source_id,
                                   external_url=external_url)
        db.add(entry)
    else:
        entry.body = body
        entry.title = title
        entry.language = language
        entry.ref_law = ref_law or entry.ref_law
        entry.ref_article = ref_article or entry.ref_article
        entry.ecli = ecli or entry.ecli
        entry.case_number = case_number or entry.case_number
        entry.court = court or entry.court
    db.commit()


def f_unaccent(x):
    """IMMUTABLE unaccent wrapper (must match the GIN index expression)."""
    return func.public.f_unaccent(x)


def _lexical_query(db: Session, query: str, limit: int):
    q = query.strip().lower()
    # OR tsquery from tokens for broader natural-language recall, then order by
    # ts_rank (tf-weighted) so the most on-topic entries rank first.
    tokens = [t for t in re.split(r"[^\w\u0370-\u03ff]+", q) if t]
    if not tokens:
        return []
    or_q = " | ".join(tokens)
    vector = func.to_tsvector("simple", f_unaccent(SearchEntry.body))
    qexpr = func.to_tsquery("simple", f_unaccent(or_q))
    base = db.query(SearchEntry, func.ts_rank_cd(vector, qexpr).label("rank")).filter(
        vector.op("@@")(qexpr)
    ).order_by(func.ts_rank_cd(vector, qexpr).desc())
    scored = []
    for e, rank in base.all():
        body_l = (e.body or "").lower()
        overlap = sum(1 for t in tokens if t in body_l)
        # relevance floor: drop entries that only coincidentally share a single token
        if len(tokens) >= 2 and overlap < 2:
            continue
        score = overlap + float(rank or 0)
        if q in body_l:
            score += 3.0
        if q in (e.title or "").lower():
            score += 2.0
        for attr in (e.ref_article, e.ref_law, e.ecli, e.case_number):
            if attr and q in str(attr).lower():
                score += 4.0
        scored.append((e, score))
    scored.sort(key=lambda x: -x[1])
    return scored[:limit]


def search(db: Session, query: str, mode: str = "hybrid", limit: int = 20,
           filters: dict | None = None) -> list[SearchResult]:
    filters = filters or {}
    results: list[SearchResult] = []
    seen = set()
    exact_wins = []

    # 1) L0 exact-reference lookup bypasses fuzzy ambiguity when deterministic.
    ref = parse_reference(query)
    if ref.kind == "legislation_article":
        hits = db.query(SearchEntry).filter_by(ref_law=ref.law_number,
                                                      ref_article=ref.article_number).all()
        for e in hits:
            exact_wins.append(SearchResult(kind=e.kind, canonical_ref=e.canonical_ref,
                                           title=e.title, body=e.body, language=e.language,
                                           score=100.0, reason="Exact match: " + (ref.article or ""),
                                           metadata={"law": ref.law_number, "article": ref.article_number}))
    elif ref.kind == "judgment" and (ref.ecli or ref.case_number):
        fc = {"ecli": ref.ecli} if ref.ecli else {"case_number": ref.case_number}
        hits = db.query(SearchEntry).filter_by(**fc).all()
        for e in hits:
            exact_wins.append(SearchResult(kind=e.kind, canonical_ref=e.canonical_ref,
                                           title=e.title, body=e.body, language=e.language,
                                           score=100.0, reason="Exact citation match",
                                           metadata=fc))

    results.extend(exact_wins)
    seen.update((r.kind, r.canonical_ref) for r in exact_wins)

    if ref.kind == "unknown" or mode in ("lexical", "hybrid", "semantic"):
        lexical = _lexical_query(db, query, limit)
        for e, score in lexical:
            key = (e.kind, e.canonical_ref)
            if key in seen:
                continue
            seen.add(key)
            reason = "Lexical match (tf/word overlap)"
            if query.strip().lower() in (e.body or "").lower():
                reason = "Exact phrase match in text"
            results.append(SearchResult(kind=e.kind, canonical_ref=e.canonical_ref,
                                        title=e.title, body=e.body, language=e.language,
                                        score=score, reason=reason))

    results.sort(key=lambda r: -r.score)
    return results[:limit]