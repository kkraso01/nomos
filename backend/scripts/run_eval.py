#!/usr/bin/env python
"""Run the early NOMOS retrieval evaluation over an ingested corpus.

Sets up a deterministic CY corpus (a winding-up law + a sale-of-goods judgment),
ingests + embeds it through the pipeline, then evaluates the hybrid retriever and
prints Recall@10/50, MRR, nDCG@10, Precision@10 per eval query.
Usage:  python scripts/run_eval.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.models import SourceRegistry
from app.services.seed import seed_core, seed_sources_from_yaml
from app.services.pipeline import run_pipeline
from app.services.hybrid import hybrid_search
from app.services.eval_metrics import evaluate


def _ensure_source(s):
    seed_core(s)
    seed_sources_from_yaml(s)
    src = s.query(SourceRegistry).filter_by(name="Cyprus National Open Data Portal").first()
    for a in ("commercial_reuse_allowed", "bulk_download_allowed", "adapter_enabled"):
        setattr(src, a, True)
    s.commit()
    return src.id


def _ingest(s, src_id):
    run_pipeline(s, source_id=src_id, ingest_key="eval-elw", kind="legislation",
                 jurisdiction="CY", canonical_id="ELW", title="Winding up Law",
                 effective_from="2020-01-01T00:00:00Z",
                 raw_payload="Article 5. Winding up.\n(1) A company may be wound up by the court in the event of insolvency.\n(2) The court may appoint a liquidator.")
    run_pipeline(s, source_id=src_id, ingest_key="eval-jud", kind="judgment",
                 jurisdiction="CY", canonical_id="GRD-1", title="Alpha v Beta",
                 metadata={"court": "Supreme Court", "case_number": "1/2018"},
                 raw_payload="Facts\nThe seller failed to deliver goods under the contract.\nHolding\nDamages awarded.")


def main():
    s = SessionLocal()
    src_id = _ensure_source(s)
    _ingest(s, src_id)

    def retriever(q):
        return [r["canonical_ref"]
                for r in hybrid_search(s, q, limit=50, enable_dense=True, enable_rerank=True)["results"]]

    report = evaluate(retriever)
    print(f"# NOMOS retrieval evaluation — {report['queries']} queries")
    for query, res in report["results"].items():
        m = res["metrics"]
        print(f"\nQ: {query}  [{res['note']}]")
        print(f"   recall@10={m['recall@10']} recall@50={m['recall@50']} mrr={m['mrr']} "
              f"ndcg@10={m['ndcg@10']} precision@10={m['precision@10']}")
        print(f"   relevant={res['relevant'] or '(hard negative)'} top={res['ranked_top']}")
    s.close()
    print("\nDone.")


if __name__ == "__main__":
    main()