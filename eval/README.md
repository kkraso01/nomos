# NOMOS Retrieval Evaluation Asset

Versioned, reviewable benchmark for the lawyer research vertical.

```
eval/
  README.md
  queries/     query definitions (metadata-rich)
  fixtures/    corpus documents to ingest for reproducible runs
  expected/    gold relevance (relevant / hard negatives) keyed by query id
  reports/     baseline + post-change metric reports (timestamped)
```

## Query metadata
Each query carries: `id`, `language`, `jurisdiction`, `query`, `query_type`,
`relevant_date` (nullable), `legal_issue` tags, `notes`, `provenance`,
`review_status`.

Query types (see `queries/`):
`exact_reference`, `ordinary_research`, `factual_similarity`,
`legal_issue_similarity`, `procedural_similarity`, `temporal_legislation`,
`case_citation_lookup`, `cited_by_related`, `ambiguous`, `hard_negative`,
`adverse_contrary`, plus language labels `greek`, `english`,
`cross_lingual_gr_en`, `cross_lingual_en_gr`.

## Provenance rules (legal safety)
- Fixtures are legally-reusable **or** clearly synthetic/test-only.
- Never manufacture an authority that could be plausibly mistaken for a real,
  citable authority. Synthetic corpus documents are prefixed (e.g. canonical ids
  `ELW`, `GRD`) and labelled `synthetic-test-only` in `provenance`.
- Hard negatives must genuinely resemble relevant material yet be legally or
  factually inappropriate.

## Workflow
`bash backend/scripts/run_eval.py` (from repo root) loads `fixtures/` + `queries/`
+ `expected/`, ingests the fixtures through the ingestion pipeline (idempotent),
runs the hybrid retriever, writes a timestamped report to `reports/`, and prints
per-query + aggregate metrics segmented by language / query_type / jurisdiction /
temporal / exact-vs-semantic.

## Metric + ranking-change protocol
Metrics: Recall@10, Recall@50, MRR, nDCG@10, Precision@10. No single “NOMOS score”.
Record a **baseline** report before any ranking change and a **post-change** report
after it; do not knowingly regress important query classes.