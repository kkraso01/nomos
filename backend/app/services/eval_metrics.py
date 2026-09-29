"""Retrieval evaluation (task-8): early Cyprus lawyer-style benchmark + metrics.

Small labelled eval set (English, Greek, cross-lingual, hard negatives). Metrics:
Recall@10, Recall@50, MRR, nDCG@10, Precision@10. No model fine-tuning.
"""
import math

# Each item: (query, [relevant canonical_refs], note)
EVAL_QUERIES = [
    ("company wound up in the event of insolvency", ["law-ELW-art-5"], "EN, direct"),
    ("εκκαθάριση εταιρείας λόγω αφερεγγυότητας", ["law-ELW-art-5"], "EL, cross-lingual"),
    ("winding up on insolvency 2021", ["law-ELW-art-5"], "temporal year in query"),
    ("the seller failed to deliver goods under the contract", ["judgment-GRD-1"], "EN judgments"),
    ("appointment of a liquidator after insolvency", ["law-ELW-art-5"], "EN phrasing"),
    ("limitation period professional negligence", [], "hard negative: not in corpus"),
    ("quantum teleportation liability", [], "hard negative: out-of-scope"),
]


def _dcg(relevants: list[int]) -> float:
    return sum(rel / math.log(i + 2) for i, rel in enumerate(relevants))


def metrics(ranked_refs: list[str], relevant: set[str]) -> dict:
    rset = relevant
    hits = [1 if r in rset else 0 for r in ranked_refs]
    ranked = ranked_refs or [""]
    recall10 = sum(hits[:10]) / max(1, len(rset))
    recall50 = sum(hits[:50]) / max(1, len(rset))
    first_rel = next((i + 1 for i, h in enumerate(hits) if h), None)
    mrr = 1.0 / first_rel if first_rel else 0.0
    dcg = _dcg(hits[:10])
    idcg = _dcg(sorted([1] * min(10, len(rset)), reverse=True))
    ndcg = dcg / idcg if idcg else 0.0
    prec10 = sum(hits[:10]) / min(10, len(ranked[:10]))
    return {"recall@10": round(recall10, 3), "recall@50": round(recall50, 3),
            "mrr": round(mrr, 3), "ndcg@10": round(ndcg, 3), "precision@10": round(prec10, 3)}


def evaluate(retriever) -> dict:
    """retriever(query) -> list of canonical_refs."""
    results = {}
    for query, relevant, note in EVAL_QUERIES:
        ranked = retriever(query)
        results[query] = {"relevant": relevant, "note": note,
                          "metrics": metrics(ranked, set(relevant)),
                          "ranked_top": ranked[:5]}
    return {"queries": len(EVAL_QUERIES), "results": results}