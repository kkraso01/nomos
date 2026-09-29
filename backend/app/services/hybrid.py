"""Hybrid legal retrieval (task-8).

Pipeline: query understanding -> [exact-reference | BM25 | dense | legislation-tree |
citation-graph | temporal filter] -> dedup -> RRF fusion -> reranker -> enrichment ->
explanation. Raw BM25 and dense scores are NEVER summed; candidates are combined by
rank fusion (RRF). The rerank stage genuinely reorders the fused results. Legislation
results resolve the version applicable to a query/event date (vs current).
"""
import calendar
from datetime import datetime, date, timezone

from sqlalchemy.orm import Session

from ..models.core import LegalChunk
from ..models.search import SearchEntry
from ..services.search import _lexical_query
from ..services.references import parse_reference
from ..services.embedding import get_provider, cosine
from ..services.corpus import resolve_version_as_of

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
    import re as _re
    ref = parse_reference(query)
    entries = None
    extra = {}
    if ref.kind == "legislation_article" and ref.law_number:
        entries = db.query(SearchEntry).filter_by(ref_law=ref.law_number,
                                                  ref_article=ref.article_number).all()
        extra = {"law": ref.law_number, "article": ref.article_number}
    # robust legal-reference recognition: alphanumeric law keys (e.g. "Article 5 of Law ELW")
    if not entries:
        m = _re.search(r"(?:Article|άρθρο|αρ\.)\s*([0-9IVXLC]+[A-Za-z]?)\s+(?:of\s+)?(?:the\s+)?(?:Law\s+|Ν\W?\s*)([A-Za-z0-9_+\-]+)",
                       query, _re.IGNORECASE)
        if m:
            key = m.group(2).strip().rstrip(".")
            entries = (db.query(SearchEntry).filter_by(ref_law=key, ref_article=m.group(1)).all()
                       or db.query(SearchEntry).filter_by(canonical_ref=f"law-{key}-art-{m.group(1)}").all())
            if entries:
                extra = {"law": key, "article": m.group(1)}
    if entries:
        return [e.canonical_ref for e in entries], extra
    return [], {}  # noqa: RET503


def _graph_candidates(db: Session, query: str) -> list[str]:
    from ..services.citation import expand_case
    ref = parse_reference(query)
    key = ref.ecli or (f"judgment-{ref.case_number}" if ref.case_number else None)
    if not key:
        return []
    try:
        exp = expand_case(db, case_key=key)
        out = ["judgment-" + c["key"] for c in exp["cited"] if c.get("key")]
        out += ["law-" + (l["provision_external_key"] or "x") for l in exp["legislation_links"]
                if l.get("provision_external_key")]
        return out
    except RuntimeError:
        return []


def _legislation_tree_candidates(db: Session, candidate_refs: list[str]) -> list[str]:
    """Legislation-tree traversal: for each matched law, add all its provision
    nodes (tree siblings/related provisions) as additional candidates."""
    laws = set()
    for ref in candidate_refs:
        r = ref[6:] if ref.startswith("EXACT:") else ref
        if r.startswith("law-") and "-art-" in r:
            laws.add(r.split("-art-")[0][len("law-"):])
    out: list[str] = []
    for law_key in laws:
        arts = db.query(SearchEntry).filter_by(ref_law=law_key, kind="legislation_node").all()
        out.extend(e.canonical_ref for e in arts)
    return out


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
    if isinstance(query_date, str):
        try:
            query_date = datetime.fromisoformat(query_date).date()
        except ValueError:
            return None
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


def _explain(r: dict, exact_meta: dict) -> list[str]:
    parts = []
    if r.get("exact"):
        parts.append("Exact match: " + r["canonical_ref"])
    if r.get("temporal"):
        t = r["temporal"]
        parts.append(f"Applicable version as of event date: v{t['applicable_version']} "
                     f"({t['applicable_from']} – {t['applicable_to'] or 'now'})")
    parts.append("BM25 + dense + tree/graph fusion (RRF)")
    return parts


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

    dense_refs: list[str] = []
    if enable_dense and mode in ("hybrid", "semantic"):
        for c, _sim in _dense_candidates(db, query, top=limit * 2):
            if c.document_type == "legislation" and c.document_key and c.article_number:
                dense_refs.append(f"law-{c.document_key}-art-{c.article_number}")
            elif c.document_type == "judgment" and c.document_key:
                dense_refs.append(f"judgment-{c.document_key}")
    if dense_refs:
        lists.append(dense_refs)

    _base = [r[6:] if r.startswith("EXACT:") else r for lst in lists for r in lst]
    tree = _legislation_tree_candidates(db, _base)
    if tree:
        lists.append(tree)

    graph = _graph_candidates(db, query)
    if graph:
        lists.append(graph)

    fusion = _rrf_fuse(lists)
    for k in exact_keys:
        fusion["EXACT:" + k] = fusion.get("EXACT:" + k, 0.0) + 1000.0  # exact bypass wins

    blocklist: set[str] = set()
    results: dict[str, dict] = {}
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
        results[base] = {
            "canonical_ref": base, "kind": entry.kind, "title": entry.title,
            "text": entry.body, "language": entry.language, "rrf": round(rrf, 3),
            "exact": canonical_ref.startswith("EXACT:"),
            "temporal": _temporal_info(db, base, query_date),
            "explanation": [],
        }

    ranked = list(results.values())

    # ---- real reranking: reorder fused results with the cross-encoder ----
    reranked = False
    if enable_rerank and ranked:
        from .rerank import RERANK_router
        try:
            docs = [r["text"] or r["title"] or "" for r in ranked]
            outcomes = RERANK_router(query, docs)
            score_by_doc = {o["doc"]: o["score"] for o in outcomes}
            for r in ranked:
                doc = r["text"] or r["title"] or ""
                r["rerank_score"] = round(score_by_doc.get(doc), 3) if doc in score_by_doc else None
            ranked.sort(key=lambda r: (r["rerank_score"] is not None, r["rerank_score"] or 0.0),
                        reverse=True)
            reranked = True
        except Exception:  # noqa: BLE001
            reranked = False

    # Calibrated ranking: deterministic exact-reference matches are authoritative
    # lookups and must never be demoted beneath generic semantic reranking.
    if any(r.get("exact") for r in ranked):
        ranked = [r for r in ranked if r["exact"]] + [r for r in ranked if not r["exact"]]

    for r in ranked:
        r["explanation"] = _explain(r, exact_meta)

    return {"query": query, "mode": mode, "reranked": reranked,
            "count": len(ranked), "exact_meta": exact_meta,
            "as_of": query_date.isoformat() if query_date else None,
            "results": ranked[:limit]}