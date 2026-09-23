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
| Legislation model | NOT_STARTED | |
| Temporal legislation | NOT_STARTED | |
| Judgment model | NOT_STARTED | |
| Citation graph | NOT_STARTED | |
| Legal reference parser | NOT_STARTED | |
| BM25 search | NOT_STARTED | |
| Semantic search | NOT_STARTED | |
| Hybrid retrieval | NOT_STARTED | |
| Reranking | NOT_STARTED | |
| Search explanations | NOT_STARTED | |
| Greek / English retrieval | NOT_STARTED | |
| Matter workspace | PARTIAL | Matter CRUD + private doc upload/download with tenancy isolation |
| Matter document ingestion | NOT_STARTED | |
| Fact extraction | NOT_STARTED | |
| Chronology | NOT_STARTED | |
| Issue spotting | NOT_STARTED | |
| Authority workspace | NOT_STARTED | |
| Legal research assistant | NOT_STARTED | |
| Citation validation | NOT_STARTED | |
| Firm knowledge base | NOT_STARTED | |
| Drafting | NOT_STARTED | |
| Procedural rules / deadlines | NOT_STARTED | |
| Audit / evidence | PARTIAL | append-only audit_events working; Evidence model exists |
| Frontend workflows | NOT_STARTED | |
| Production deployment | DEFERRED_PRODUCTION | Not part of current goal |
| Performance/load testing | DEFERRED_PRODUCTION | Not part of current goal |

