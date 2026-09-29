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

### 2026-09-23 — PDF matter-document parsing
- Added deterministic PDF text extraction (PyMuPDF) to private matter documents; PDFs now feed the fact/event/chronology pipeline (previously text-only). No OCR/ML.
- Tests expand to 32 passing.

### 2026-09-29 — Small on-device reranker (Reranking → FUNCTIONAL)
- Installed a lightweight reranker (no torch/CUDA): ONNX Runtime + `cross-encoder/ms-marco-MiniLM-L-6-v2`
  qint8 ARM64 ONNX (22.6 MB) downloaded to HDD `models/reranker-minilm`.
- Wired via the `RERANK_SEARCH` capability (POST /ai/capability returns per-doc scores) and as an
  opt-in cross-encoder rerank step on `GET /search?rerank=true` (graceful fallback to lexical if model absent).
- Verified on this ARM64 host: relevant doc scored high (+8) vs irrelevant (~-11); first load ~1.8 s.
- Tests expand to 34 passing (2 new rerank e2e, guarded on model presence).
- Semantic *embeddings* (dense retrieval) remain intentionally unconfigured on this device.

### 2026-09-29 — GOAL DECISION: clean refactor, no compatibility/backfill
The user directed a from-scratch refactor of the legal-knowledge core onto the
jurisdiction-agnostic design. Per explicit instruction, we are NOT keeping backward
compatibility and NOT backfilling legacy schema/data. Old service/API shapes and tests
will be rewritten to the new canonical model. No production data exists yet, so there is
nothing valuable to migrate; this is a green-field rebuild of the model + retrieval core.

### 2026-09-29 — Jurisdiction-agnostic canonical model (task-1) complete
- Green-field refactor (no backfill) onto app/models/core.py:
  Jurisdiction, Court, LegalSource, Legislation/Version/Node (permanent identity)/NodeVersion (versioned text),
  LegislationAmendment + AmendmentOperation, ProvisionCrossReference,
  Judgment/Version/Section/Paragraph, CaseCitation, JudgmentLegislationLink, CaseTreatment, LegalChunk.
- Legislative node = stable identity; wording lives in LegislationNodeVersion per legislation version (as-of resolves correct version). Node terminology per jurisdiction (JurisdictionConfig). Cross-jurisdiction links supported (CY case CITES ECHR ECLI target_key).
- Dropped legacy CitationEdge; rewrote citation/graph + similarity + corpus services/APIs onto the new model; rewrote migration chain to a single clean baseline (5097d44a2bc1) + add_case_treatment_target_key.
- Seeded jurisdictions (CY/EU/ECHR/GR/UK) + representative CY court hierarchy; fixed search indexing to materialize raw node values and rebuild idempotently on dedupe (Greek + English + exact-reference verified).
- Full suite 34 passed.

### 2026-09-29 — Licence-aware source acquisition + metadata (task-2) complete
- Confirmed SourceRegistry carries all required metadata (jurisdiction, official/primary, the 7 reuse statuses,
  licence+url+terms hash, commercial_reuse_allowed, automated_access/bulk/api, attribution_required,
  terms_checked_at/by). Exposed licence/terms/official/commercial fields via the API response.
- Enforcement: UNKNOWN is not permission; PERMISSION_REQUIRED/RESTRICTED/DISABLED blocked; approved sources still
  need recorded commercial clearance in paid mode (audited PUT /sources/registry/{id}/clearance).
- data.gov.cy remains the CONFIRMED CC BY 4.0 commercial source (seed + evidence). CC BY 4.0 permit commercial use with attribution.
- Added tests (tests/test_licence_registry_e2e.py); full suite 37 passing.

### 2026-09-29 — Immutable, restartable ingestion pipeline (task-3) complete
- Added IngestionRun + RunArtifact (provenance to RAW snapshot + parser/normalizer/embedding versions + model_run_id).
- Pipeline stages DISCOVER→FETCH→RAW→PARSE→NORMALIZE→LINK→ENRICH→CHUNK→EMBED→INDEX, each idempotent and recorded per-run; run is content-addressed (source+ingest_key+sha256) so same-hash is a no-op and changed content is a NEW snapshot (never overwrites).
- Failure at any stage is recorded; retry resumes from cached RAW (snapshot id reused) without re-fetching.
- CHUNK stage writes structural LegalChunk rows (idempotent, deterministic chunk ids tied to canonical unit).
- ENDPOINT /pipeline/run + /pipeline/{id}; tests expand to 41 passing (test_pipeline_e2e.py).
- EMBED stage currently records embedding_version=None (replaceable provider wired in task-7).

### 2026-09-29 — Temporal legislation + amendments as events (task-4) complete
- apply_amendment creates a NEW legislation version effective on the amendment date (never overwrites history),
  carries all node wording forward, and applies the operation to the affected node; records LegislationAmendment
  (insert/delete/replace/renumber/repeal/commence + previous/new text + publication/effective dates + source evidence).
- /amendments record, list, diff; as-of resolves the version applicable on a date (tests: 2022 amendment -> 2021 vs 2023 text).
- Tests expand to 42 passing.

### 2026-09-29 — Deterministic provision cross-references (task-5) complete
- Extended L0 extractor to all Cyprus/Greek forms with exact spans (άρθρο 15(2)(α), ΚΕΦ.6, Κεφ.148, Ν.123(I)/2020, ΕΛLI, case numbers, Article 15).
- scan_legislation creates ProvisionCrossReference(source_node->target_node, span, high confidence) within a legislation version; /citation/scan-provision-refs.
- Tests expand to 44 passing.

### 2026-09-29 — Judgment enrichment + citations/treatment + graph (task-6) complete
- enrich_judgment deterministically links a judgment's paragraphs (as exact evidence_paragraph_id) to legislation provisions (APPLIES) and cited cases (CITES) via in-text refs; /citation/enrich-judgment.
- Expanded graph expansion returns cited/citing/treatments/legislation_links; semantic treatment starts REVIEW_REQUIRED (evidence-backed, never invented).
- Tests expand to 45 passing.
