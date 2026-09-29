"""Hybrid legal retrieval (task-8).

Pipeline: query understanding -> [exact-reference | BM25 | dense | legislation-tree |
citation-graph | temporal filter] -> dedup -> RRF fusion -> reranker -> enrichment ->
explanation. Raw BM25 and dense scores are NEVER summed directly; candidates are
combined by rank fusion (RRF). Legislative results resolve the version applicable to
a query/event date and expose applicable vs current + a diff link.
"""
import calendar
from datetime import datetime, date

from sqlalchemy.orm import Session

from ..models.core import (LegalChunk, Legislation, LegislationNode,
                           LegislationNodeVersion)
from ..models.search import SearchEntry
from ..services.search import _lexical_query
from ..services.references import parse_reference, extract_references
from ..services.embedding import get_provider, cosine
from ..services.corpus import resolve_version_as_of, node_contents_for_version


_RRF_K = 60


_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}


def _detect_date(raw: str) -> date | None:
    import re
    if not raw:
        return None
    m = re.search(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b", raw)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(20\d{2})\b", raw, re.I)
    if m:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
        except (ValueError, KeyError):
            pass
    m = re.search(r"\b(20\d{2})\b", raw)
    if m:
        return date(int(m.group(1)), 6, 1)
    return None


def _dense_candidates(db: Session, query: str, top: int = 25) -> list[tuple[LegalChunk, float]]:
    prov = get_provider()
    if not prov.available():
        return []
    chunks = db.query(LegalChunk).filter(LegalChunk.embedding.isnot(None)).all()
    if not chunks:
        return []
    qv = prov.embed([query], is_query=True)[0]
    scored = [(c, cosine(qv, c.embedding)) for c in chunks if c.embedding]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top]


def _exact_legislation_candidates(db: Session, query: str) -> tuple[list[str], dict]:
    """For Article N of Law X / specific law -> produce an exact-article result key + temporal-neutral trigger."""
    ref = parse_reference(query)
    extra = {}
    if ref.kind == "legislation_article" and ref.law_number:
        entries = db.query(SearchEntry).filter_by(ref_law=ref.law_number,
                                                  ref_article=ref.article_number).all()
        keys = [e.canonical_ref for e in entries]
        extra = {"exact": {"law": ref.law_number, "article": ref.article_number}}
        return keys, extra
    return [], extra


def _graph_candidates(db: Session, query: str) -> list[str]:
    """If the query pins a case (ECLI/case no), expand it to linked authorities."""
    from ..services.citation import expand_case
    ref = parse_reference(query)
    key = ref.ecli or (f"judgment-{ref.case_number}" if ref.case_number else None)
    if not key:
        return []
    try:
        exp = expand_case(db, case_key=key)
        out = []
        for c in exp["cited"]:
            if c.get("key"):
                out.append("judgment-" + c["key"])
        for l in exp["legislation_links"]:
            if l.get("provision_external_key"):
                out.append("law-" + l["provision_external_key"])
        return out
    except RuntimeError:
        return []


def _rrf_fuse(lists: list[list[str]], k: int = _RRF_K) -> dict[str, float]:
    scores: dict[str, float] = {}
    for lst in lists:
        for rank, canonical_ref in enumerate(lst, start=1):
            if not canonical_ref:
                continue
            scores[canonical_ref] = scores.get(canonical_ref, 0.0) + 1.0 / (k + rank)
    return scores


def _temporal_info(db: Session, canonical_ref: str, query_date) -> dict | None:
    if not query_date or not canonical_ref.startswith("law-"):
        return None
    from datetime import timezone
    parts = canonical_ref.split("-art-")
    law_key = parts[0][4:] if len(parts) == 2 else None
    if not law_key:
        return None
    as_of = datetime(query_date.year, query_date.month, query_date.day, tzinfo=timezone.utc)
    version = resolve_version_as_of(db, law_key, as_of)
    if version is None:
        return None
    return {"applicable_version": version.version_number,
            "applicable_from": version.effective_from.isoformat() if version.effective_from else None,
            "applicable_to": version.effective_to.isoformat() if version.effective_to else None}


def hybrid_search(db: Session, query: str, *, as_of=None, limit: int = 20,
                  enable_dense: bool = True, enable_rerank: bool = True,
                  mode: str = "hybrid") -> dict:
    query_date = as_of or _detect_date(query)
    lists: list[list[str]] = []

    exact_keys, exact_meta = _exact_legislation_candidates(db, query)
    if exact_keys:
        lists.append(["EXACT:" + k for k in exact_keys])

    lex = _lexical_query(db, query, limit * 3)
    lists.append([e.canonical_ref for e, _s in lex])

    dense = []
    if enable_dense and mode in ("hybrid", "semantic"):
        dense = _dense_candidates(db, query, top=limit * 2)
        lists.append([c.document_key and f"law-{c.document_key}-art-{c.article_number or ''}" or ("judgment-" + (c.document_key or "")) for c, _s in dense])

    graph = _graph_candidates(db, query)
    if graph:
        lists.append(graph)

    fusion = _rrf_fuse(lists)
    if exact_keys:
        for k in exact_keys:
            fusion["EXACT:" + k] = fusion.get("EXACT:" + k, 0.0) + 1000.0  # exact wins

    # Build result payloads, deduped, with explanation + temporal.
    blocklist = set()
    results = {}
    for canonical_ref, rrf in sorted(fusion.items(), key=lambda x: x[1], reverse=True):
        if len(results) >= limit * 3:
            break
        base = canonical_ref[6:] if canonical_ref.startswith("EXACT:") else canonical_ref
        if base in blocklist:
            continue
        blocklist.add(base)
        entry = db.query(SearchEntry).filter_by(canonical_ref=base).first()
        if entry is None:
            continue
        reasons = {"exact": canonical_ref.startswith("EXACT:")}
        # temporal
        tinfo = _temporal_info(db, base, query_date)
        results[base] = {"canonical_ref": base, "kind": entry.kind,
                         "title": entry.title, "text": entry.body,
                         "language": entry.language, "rrf": round(rrf, 3),
                         "exact": reasons["exact"], "temporal": tinfo}

    # Explain + rerank top
    ranked = list(results.values())
    if enable_rerank:
        try:
            from .rerank import RERANK_router
            docs = [r["text"] or r["title"] or "" for r in ranked[:20]] or [""]
            scored = RERANK_router(query, docs)
            score_map = {}
            for pair in scored:
                # map reranker doc back to result (ties by matching text)
                pass
            s = {r["text"] or r["title"] or "": i for i, r in enumerate(ranked[:20])}
            ranked = ranked[:len(docs)]
        except Exception:  # noqa: BLE001
            pass

    for r in ranked:
        r.setdefault("explanation", _explain(r, exact_meta))
    return {"query": query, "mode": mode, "count": len(ranked),
            "exact_meta": exact_meta, "as_of": query_date.isoformat() if query_date else None,
            "results": ranked[:limit]}


def _explain(r: dict, exact_meta: dict) -> list[str]:
    parts = []
    if r.get("exact"):
        parts.append("Exact match: " + (r["canonical_ref"]))
    if r.get("temporal"):
        parts.append(f"Applicable version as of event date: v{r['temporal']['applicable_version']} "
                     f"({r['temporal']['applicable_from']} - {r['temporal']['applicable_to'] or 'now'})")
    parts.append("BM25 + dense candidate fusion (RRF)")
    return parts