"""Retrieval evaluation (formal benchmark asset).

Drives eval/queries + eval/expected + eval/fixtures. Metrics: Recall@10, Recall@50,
MRR, nDCG@10, Precision@10. Per-query and segmented (by language / query_type /
jurisdiction / temporal / exact-vs-semantic). No model fine-tuning.
"""
import json
import math
import os

from ..config import settings

EVAL_ROOT = os.path.join(settings.root_dir, "eval")


def metrics(ranked_refs: list[str], relevant: set[str]) -> dict:
    hits = [1 if r in relevant else 0 for r in ranked_refs]
    ranked = ranked_refs or [""]
    r10 = sum(hits[:10]) / max(1, len(relevant))
    r50 = sum(hits[:50]) / max(1, len(relevant))
    first = next((i + 1 for i, h in enumerate(hits) if h), None)
    mrr = 1.0 / first if first else 0.0
    dcg = _dcg(hits[:10])
    idcg = _dcg(sorted([1] * min(10, len(relevant)), reverse=True))
    ndcg = dcg / idcg if idcg else 0.0
    p10 = sum(hits[:10]) / min(10, len(ranked[:10]))
    return {"recall@10": round(r10, 3), "recall@50": round(r50, 3),
            "mrr": round(mrr, 3), "ndcg@10": round(ndcg, 3), "precision@10": round(p10, 3)}


def _dcg(relevants: list[int]) -> float:
    return sum(rel / math.log(i + 2) for i, rel in enumerate(relevants))


def load_queries(path: str | None = None) -> list[dict]:
    p = path or os.path.join(EVAL_ROOT, "queries", "nomos_eval_queries.json")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def load_expected(path: str | None = None) -> dict:
    p = path or os.path.join(EVAL_ROOT, "expected", "nomos_eval_gold.json")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def load_fixtures(path: str | None = None) -> list[dict]:
    p = path or os.path.join(EVAL_ROOT, "fixtures", "nomos_cy_corpus.json")
    with open(p, encoding="utf-8") as fh:
        data = json.load(fh)
    return data["docs"]


def _segment_keys(q: dict) -> list[str]:
    keys = [q.get("language"), q.get("query_type"), q.get("jurisdiction")]
    if q.get("relevant_date"):
        keys.append("temporal")
    else:
        keys.append("non_temporal")
    keys.append("exact" if q.get("query_type") == "exact_reference" else "semantic")
    return [k for k in keys if k]


def evaluate_from(queries: list[dict], expected: dict, retriever) -> dict:
    """queries: query metadata list; expected: {id: {relevant, hard_negative}}.
    retriever(query) -> list of canonical_refs."""
    per_query = {}
    seg = {}
    for q in queries:
        qid = q["id"]
        rel = set(expected.get(qid, {}).get("relevant", []))
        ranked = retriever(q["query"])
        m = metrics(ranked, rel)
        per_query[qid] = {"id": qid, "query": q["query"], "query_type": q.get("query_type"),
                          "language": q.get("language"), "jurisdiction": q.get("jurisdiction"),
                          "relevant_date": q.get("relevant_date"),
                          "relevant": sorted(rel), "hard_negative": expected.get(qid, {}).get("hard_negative", []),
                          "metrics": m, "ranked_top": ranked[:5]}
        for k in _segment_keys(q):
            seg.setdefault(k, []).append(m)
    aggregates = {k: _avg(v) for k, v in seg.items()}
    return {"queries": len(queries), "per_query": per_query, "segments": aggregates}


def _avg(metrics_list: list[dict]) -> dict:
    keys = metrics_list[0].keys()
    out = {}
    for key in keys:
        out[key] = round(sum(m[key] for m in metrics_list) / len(metrics_list), 3)
    return out


def write_report(report: dict, filename: str | None = None):
    import datetime
    ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    p = os.path.join(EVAL_ROOT, "reports", filename or f"report-{ts}.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    return p