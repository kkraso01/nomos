#!/usr/bin/env python
"""Run the NOMOS retrieval benchmark from the versioned eval/ asset.

Ingests eval/fixtures (idempotent), evaluates the hybrid retriever against
eval/queries + eval/expected, prints per-query + segmented metrics, and writes a
timestamped report to eval/reports/. Usage:  python scripts/run_eval.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import SourceRegistry
from app.services.seed import seed_core, seed_sources_from_yaml
from app.services.pipeline import run_pipeline
from app.services.hybrid import hybrid_search
from app.services import eval_metrics as em


def _ensure_source(s):
    seed_core(s)
    seed_sources_from_yaml(s)
    src = s.query(SourceRegistry).filter_by(name="Cyprus National Open Data Portal").first()
    for a in ("commercial_reuse_allowed", "bulk_download_allowed", "adapter_enabled"):
        setattr(src, a, True)
    s.commit()
    return src.id


def _ingest(s, src_id, fixture):
    kind = fixture["kind"]
    if kind == "law":
        run_pipeline(s, source_id=src_id, ingest_key=f"eval-{fixture['canonical_id']}",
                     kind="legislation", jurisdiction=fixture.get("jurisdiction", "CY"),
                     canonical_id=fixture["canonical_id"], title=fixture["title"],
                     raw_payload=fixture["raw_string"])
    else:
        run_pipeline(s, source_id=src_id, ingest_key=f"eval-{fixture['canonical_id']}",
                     kind="judgment", jurisdiction=fixture.get("jurisdiction", "CY"),
                     canonical_id=fixture["canonical_id"], title=fixture["title"],
                     metadata=fixture.get("metadata", {}), raw_payload=fixture["raw_string"])


def main():
    s = SessionLocal()
    src_id = _ensure_source(s)
    fixtures = em.load_fixtures()
    for fx in fixtures:
        _ingest(s, src_id, fx)
    queries = em.load_queries()
    expected = em.load_expected()

    # Scoped-collection evaluation: only judge ranking with the benchmark corpus
    # docs, so the shared dev index does not drown reproducible signal.
    law_prefixes = {f"law-{d['canonical_id']}-" for d in fixtures if d['kind'] == 'law'}
    judgment_refs = {f"judgment-{d['metadata']['case_number']}" for d in fixtures if d['kind'] == 'judgment'}

    def in_scope(ref):
        return any(ref.startswith(p) for p in law_prefixes) or ref in judgment_refs

    def retriever(q):
        ranked = [r["canonical_ref"]
                  for r in hybrid_search(s, q, limit=50, enable_dense=True, enable_rerank=True)["results"]]
        return [r for r in ranked if in_scope(r)]

    report = em.evaluate_from(queries, expected, retriever)
    baseline = os.path.join(em.EVAL_ROOT, "reports", "baseline.json")
    written = em.write_report(report, "baseline.json") if not os.path.exists(baseline) else em.write_report(report)
    print(f"# NOMOS retrieval evaluation — {report['queries']} queries  (report: {written})")
    for qid, res in report["per_query"].items():
        m = res["metrics"]
        rel = res["relevant"] or "(none)"
        print(f"\n[{qid}] {res['query_type']}/{res['language']} :: {res['query']}")
        print(f"   rel={rel} "
              f"R@10={m['recall@10']} R@50={m['recall@50']} MRR={m['mrr']} "
              f"nDCG@10={m['ndcg@10']} P@10={m['precision@10']}")
        print(f"   top={res['ranked_top']}")
    print("\n--- segmented aggregates ---")
    for k, v in sorted(report["segments"].items()):
        print(f"   {k or '?'}: R@10={v['recall@10']} R@50={v['recall@50']} MRR={v['mrr']} "
              f"nDCG@10={v['ndcg@10']} P@10={v['precision@10']}")
    s.close()
    print("\nDone.")


if __name__ == "__main__":
    main()