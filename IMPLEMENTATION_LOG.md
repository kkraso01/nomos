# NOMOS Implementation Log

Use this file for meaningful implementation events only.

## Deferred Production Validation

The following are not blockers to functional feature development and should only be performed when explicitly prioritized:

- sustained load/stress/concurrency testing;
- long soak testing;
- production penetration/security testing;
- chaos testing;
- cloud/Pi parity benchmarking;
- sustained Raspberry Pi thermal/OCR throughput benchmarks;
- production deployment/cutover.

## Entries

### 2026-09-23 — Phase A platform foundation functional
- Infrastructure on HDD only (docker-data, venv, pip/npm cache all under /mnt/jellyfin/Projects/NOMOS).
- NOMOS Docker Compose on distinct ports (pg 5433, redis 6380, minio 9011/9012) to avoid the running demiourgo stack; containers reused from already-pulled images.
- Backend: FastAPI app (app/main.py), routers for auth/matters/documents/sources/jobs, schemas, core (security/tenancy/audit/idempotency), storage (MinIO), AI router capability abstraction.
- Alembic migration `507295a30f2f` (initial full schema); upgrade verified in dev postgres.
- Switched bcrypt to direct library (passlib incompatible with bcrypt>=4.1). rq requires binary redis conns (decode_responses=False).
- Functional acceptance verified and codified in tests/test_platform_e2e.py (3 tests pass):
  tenancy isolation (cross-org 403/404), MinIO document write/read, durable rq job result persistence, migration, source UNKNOWN/PERMISSION_REQUIRED bulk-ingest block, approved source ingest with dedupe + version-on-change, AI capability routing abstraction.
- Seed registry idempotent (SOURCE_REGISTRY_SEED.yaml). CyLaw remains PERMISSION_REQUIRED (no bulk ingestion).


<!-- Add phase start/completion, migrations, architecture decisions, source permission status changes, major model/retrieval decisions, important bugs/blockers, and deliberate deviations here. -->

### 2026-09-23 — Phase B/C corpus + search functional
- Versioned Legislation/Judgment models (Legislation/LegislationVersion/LegislationNode, Judgment/JudgmentVersion/JudgmentNode) with immutable version-on-change semantics.
- Deterministic L0 normalizer (EN Article/EL Άρθρο + paragraph nodes); immutable raw→canonical already from Phase A.
- Temporal version resolution: `as-of` returns correct historical provision; current/historical not conflated (test passes).
- L0 legal-reference parser: Article-of-Law, ECLI, case numbers.
- Search: PostgreSQL ts_vector + unaccent (IMMUTABLE f_unaccent wrapper + GIN index) lexical index in `search_entries`. Exact-reference bypass returns deterministic match at score 100 before fuzzy. Every result carries provenance + reason_for_match.
- Greek and English representative queries return lexical results (tests expand to 11 passing).
- Semantic embeddings/reranking NOT configured (no local model on Pi); semantic mode falls back to lexical with explicit note. OpenSearch usable as alternate SearchProvider.

### 2026-09-23 — Matter workspace (Phase F) functional
- MatterDocument ingestion (private MinIO, text parse), MatterFact/MatterEvent/MatterIssue models, all org-scoped.
- L0 deterministic extractor: dates→chronology events, amounts/obligations/parties→proposed facts, all with char span + confidence (AI enrichment can refine downstream).
- Lawyer accept/reject persists; chronology sorted; cross-organisation access to a matter's docs/facts/chronology returns 404.
- Tests expand to 13 passing.

### 2026-09-23 — Citation graph (Phase D) functional
- CitationEdge model (CITES / REFERENCES / semantic FOLLOWS/DISTINGUISHES/APPROVES/CRITICISES/OVERRULES) with evidence + review_status.
- Creation validates both endpoints exist in the corpus (nonexistent citation blocked). Semantic treatment requires supporting quote evidence; marked review_required.
- Traversal returns cited + citing authorities; search-test-only refs preserved across autogenerations via include_object.
- Tests expand to 15 passing.

### 2026-09-23 — Procedural rules / deadlines (Phase I) functional
- Versioned ProceduralRule; deterministic deadline calculator: calendar_days, business_days (weekends + holiday framework), day_of_month, last_day_month; direction/limit-type.
- Ambiguous rules and unsupported modes return REVIEW_REQUIRED with no guessed date.
- API /procedure/rules and /procedure/deadline; tested (17 passing). Audit logged per computation.
