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

### 2026-09-23 — Grounded research assistant (Phase G) functional
- /research/query: grounded retrieval of canonical public law via search pipeline; answer is anchored in retrieved text (never model-memory fabrication).
- /research/validate-citation: authoritative existence check (Article/Law, ECLI, case) -> blocks nonexistent citations.
- "No sufficiently supported authority found" path when relevant retrieval below threshold (token-overlap relevance floor).
- Accepted matter facts can be folded in as evidence (tenant-scoped).
- Search improved: OR-token recall + ts_rank_cd ordering + token-overlap relevance floor for natural-language queries.
- Tests expand to 20 passing.

### 2026-09-23 — Audit export, firm knowledge, drafting (J/H/I) functional
- /audit/export (JSON/CSV), append-only.
- Firm knowledge base: tenant-scoped precedents/templates; internal search labelled internal=true, primary_authority=false; cross-org isolated.
- Drafting: research memo generated only from accepted facts + verified authorities; nonexistent citations rejected; output marked draft + lawyer_review_required with full provenance.
- Tests expand to 23 passing.

### 2026-09-23 — Entitlements (Phase J) functional
- Org `plan` (starter/standard/pro/enterprise); plan-to-feature gate enforced server-side: starter AI_REMOTE denied (403), pro allowed. /plan set/get endpoints.
- Fixed a null-byte corruption in app/models/__init__.py (edit-tool artifact) by stripping null bytes and re-registering _extra imports.
- Tests expand to 25 passing.

### 2026-09-23 — Matter authority workspace + follow notifications (G/I) functional
- MatterAuthority: mark authorities relied_on/adverse/distinguishable/rejected (corpus-validated; nonexistent denied). /matters/{id}/authorities.
- FollowedItem + Notification: follow a ref/topic and receive source-backed update notifications; tenant-scoped.
- Split follow/notify/notifications onto /follow prefix to avoid route collision with /matters/{matter_id}.
- Tests expand to 27 passing.

### 2026-09-23 — Judgment segmentation (Phase E) functional
- L0 deterministic segmentation of judgments into facts / procedural_history / legal_analysis / holding / order / dissent, stored on JudgmentNode.segment_type with para/source spans; GET /corpus/judgment/{id}/segments.
- Tests expand to 28 passing.

### 2026-09-23 — Case comparison with separate similarity dimensions (Phase E) functional
- /similarity/compare reports LEGAL_ISSUE / FACTUAL / PROCEDURAL / STATUTORY / REMEDY similarity separately.
- Deterministic L0: heading-carry-forward segmentation groups body text under facts/legal-analysis/holding/order; jaccard term overlap per dimension + shared cited-province overlap + same-court metadata + remedy-vocabulary overlap.
- Every dimension returns a score and an explanation; missing case -> 404. Tests expand to 29 passing.

### 2026-09-23 — Issue spotting (Phase F) functional
- /matters/{mid}/suggest-issues: deterministic L0 mapping of ACCEPTED facts to candidate legal issues (insolvency, negligence, breach, damages, liability, limitation, jurisdiction, remedy); persisted as proposed for lawyer review.
- Tests expand to 30 passing.

### 2026-09-23 — Source-grounded extractive judgment summary (Phase E) functional
- /corpus/judgment/{id}/summary: verbatim extractive sentences from holding/legal_analysis/order segments with source span; no model-memory generation (source_grounded flag).
- Tests expand to 31 passing.

### 2026-09-23 — Goal: /nomos/ exposure, HDD-only validation, regression
- Apache: `/nomos/` reverse-proxy added to the :80 default vhost (backup saved) and applied via graceful `systemctl reload` — no service stopped. Verified: GET /nomos/ (200 HTML landing), /nomos/health (200 JSON), /nomos/docs (200 Swagger). Company site 200; demiourgo containers Up 5 days; flaresolverr running — untouched.
- HDD-only audit passed: docker data-root + all nomos volumes under /mnt/jellyfin/Projects/NOMOS/docker-data; venv 324M, pip 67M/npm 41M caches, logs, repo all under /mnt/jellyfin/Projects/NOMOS; XDG_CACHE_HOME→HDD; no NOMOS data written to the SD card.
- Final regression: full backend suite 31 passed / 0 failures; migrations at head (b23cab155aed); rq worker + API running; working tree clean and committed.

### 2026-09-23 — Browseable web frontend (Frontend workflows → FUNCTIONAL)
- Added a self-contained web UI at /ui (and /nomos/ui via Apache): login/register, public search with mode select, and citation validation.
- The page's JS targets the same API through the /nomos/ proxy (API base auto-detected) — verified: login→search (200), validate-citation (exists:true), register (200) through Apache.
- Test suite remains 31 passing.

### 2026-09-23 — Source license research + commercial-reuse gate (legal safety)
- Researched source licences from official pages. CONFIRMED: Cyprus National Open Data Portal
  (data.gov.cy) is explicitly **CC BY 4.0** (official FAQ; reuse/commercial permitted with
  attribution + derivative marking) -> registry commercial_reuse_allowed=true.
  NOT confirmed (network bot-gated/unreachable): EUR-Lex full-text (API + pages 202/0B),
  ECHR/HUDOC (JS-rendered body), Gazette, Supreme Court -> remain gated.
  CyLaw remains PERMISSION_REQUIRED (no bulk ingestion).
  Findings in SOURCE_LICENSE_RESEARCH_2026-09-23.md.
- Added commercial-service gate: in commercial_service_mode (paid service), bulk ingestion
  requires `commercial_reuse_allowed=True` on the source (audited human clearance step via
  `PUT /sources/registry/{id}/clearance`). Verified at runtime: data.gov.cy ingests; EUR-Lex
  (approved-open but not commercially cleared) blocked 403; CyLaw blocked.
- Tests updated; suite still 31 passing.
