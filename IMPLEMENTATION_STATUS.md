# NOMOS Implementation Status

Allowed states:

- NOT_STARTED
- SCAFFOLDED
- PARTIAL
- FUNCTIONAL
- BLOCKED_EXTERNAL
- DEFERRED_PRODUCTION

Do not use FUNCTIONAL unless the workflow has been tested end-to-end with representative data.

| Area | Status | Evidence / Notes |
|---|---|---|
| Platform foundation | FUNCTIONAL | FastAPI modular app, PostgreSQL(alembic) on HDD, Redis+rq durable jobs, MinIO storage; tests/test_platform_e2e.py (3 pass) |
| Authentication / tenancy | FUNCTIONAL | register org+owner, login, JWT; cross-org blocked (403/404) verified |
| Source registry | FUNCTIONAL | seeded from SOURCE_REGISTRY_SEED.yaml; CRUD + disable adapter endpoint |
| Source reuse enforcement | FUNCTIONAL | UNKNOWN/PERMISSION_REQUIRED blocked from bulk ingest; audit recorded |
| Raw source ingestion | FUNCTIONAL | immutable raw→canonical, dedupe, changed→new version, provenance |
| Legislation model | FUNCTIONAL | versioned Legislation/LegislationVersion/LegislationNode; deterministic normalizer |
| Temporal legislation | FUNCTIONAL | as-of date resolves correct version; tests/test_corpus_e2e.py |
| Judgment model | FUNCTIONAL | Judgment/JudgmentVersion/JudgmentNode versioned ingest |
| Citation graph | FUNCTIONAL | validated edges (must exist), semantic evidence requirement, traversal; tests/test_citation_e2e.py |
| Legal reference parser | FUNCTIONAL | Cyprus/EU Article/Law, ECLI, case-number; L0 exact bias |
| BM25 search | FUNCTIONAL | Postgres ts_vector/unaccent lexical (EN+EL); OpenSearch provider pluggable |
| Semantic search | NOT_STARTED | no local embed model on Pi; semantic mode falls back to lexical |
| Hybrid retrieval | PARTIAL | exact-reference + lexical fused; semantic punch-out deferred |
| Reranking | NOT_STARTED | |
| Search explanations | FUNCTIONAL | reason_for_match on every result; provenance |
| Greek / English retrieval | FUNCTIONAL | tests/test_search_e2e.py; unaccent tsvector handles both |
| Matter workspace | FUNCTIONAL | create matter, upload doc, extract, chronology, fact accept/reject; tenancy isolation; tests/test_matter_ws_e2e.py |
| Matter document ingestion | FUNCTIONAL | private upload to MinIO + text extraction |
| Fact extraction | PARTIAL | L0 deterministic extraction with source spans, proposed→review; no LLM |
| Chronology | FUNCTIONAL | dated events sorted by date |
| Issue spotting | PARTIAL | issue create/review scaffold; no LLM issue detection |
| Authority workspace | NOT_STARTED | |
| Legal research assistant | FUNCTIONAL | grounded retrieval + citation validation + unsupported path; tests/test_research_e2e.py |
| Citation validation | FUNCTIONAL | generated citations checked against corpus via /research/validate-citation |
| Procedural rules / deadlines | FUNCTIONAL | versioned rules; business/calendar days, holidays, ambiguity->REVIEW_REQUIRED; tests/test_procedure_e2e.py |
| Firm knowledge base | FUNCTIONAL | tenant-scoped precedents/templates, internal-labelled search, never primary authority; tests/test_gov_firm_draft_e2e.py |
| Drafting | FUNCTIONAL | verified-authority memo, nonexistent citations rejected, draft/review flag |
| Audit / evidence | FUNCTIONAL | append-only audit_events working; JSON/CSV export; Evidence model exists |
| Frontend workflows | NOT_STARTED | |
| Entitlements / usage metering | FUNCTIONAL | plan-based server-side feature denial; tests/test_plan_e2e.py |
| Production deployment | DEFERRED_PRODUCTION | Not part of current goal |
| Performance/load testing | DEFERRED_PRODUCTION | Not part of current goal |
