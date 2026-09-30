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
| Jurisdiction-agnostic canonical model | FUNCTIONAL | green-field refactor: Jurisdiction/Court/LegalSource; LegislationNode (permanent identity)+LegislationNodeVersion; AmendmentOperation; ProvisionCrossReference; JudgmentSection/Paragraph; CaseCitation/JudgmentLegislationLink/CaseTreatment; LegalChunk; node terms per jurisdiction; CY seed; 34 tests |
|---|---|---|
| Platform foundation | FUNCTIONAL | FastAPI modular app, PostgreSQL(alembic) on HDD, Redis+rq durable jobs, MinIO storage; tests/test_platform_e2e.py (3 pass) |
| Authentication / tenancy | FUNCTIONAL | register org+owner, login, JWT; cross-org blocked (403/404) verified |
| Licence-aware source registry | FUNCTIONAL | full metadata (jurisdiction, 7 statuses, licence+url+hash, commercial clearance, terms audit) exposed via API; UNKNOWN!=permission; commercial gate enforced; data.gov.cy CC BY 4.0 confirmed; tests/test_licence_registry_e2e.py |
| Source registry | FUNCTIONAL | seeded from SOURCE_REGISTRY_SEED.yaml; CRUD + disable adapter endpoint |
| Source reuse enforcement | FUNCTIONAL | UNKNOWN/PERMISSION_REQUIRED blocked from bulk ingest; audit recorded |
| Immutable ingestion pipeline | FUNCTIONAL | 10-stage (DISCOVER..INDEX), content-addressed (SHA256), restartable-from-cached-RAW, provenance (snapshot+parser/normalizer/embedding_versions+model_run_id), structural LegalChunks; tests/test_pipeline_e2e.py |
| Raw source ingestion | FUNCTIONAL | immutable raw→canonical, dedupe, changed→new version, provenance |
| Legislation model | FUNCTIONAL | versioned Legislation/LegislationVersion/LegislationNode; deterministic normalizer |
| Temporal legislation + amendments | FUNCTIONAL | amendments as append-only events (INSERT/REPLACE/DELETE/RENUMBER/REPEAL/COMMENCE) with prev/new text + effective/pub dates + evidence; new version on amend; as-of resolves applicable vs current; diff API; tests/test_amendments_e2e.py |
| Temporal legislation | FUNCTIONAL | as-of date resolves correct version; tests/test_corpus_e2e.py |
| Judgment enrichment + citations/treatment | FUNCTIONAL | sections+paragraphs with segment types; deterministic enrich links paragraphs (evidence_paragraph_id) to provisions (APPLIES) + case citations (CITES); semantic treatment REVIEW_REQUIRED; graph expansion exposes cited/citing/treatments/legislation_links; /citation/enrich-judgment; tests/test_judgment_enrichment_e2e.py |
| Judgment model | FUNCTIONAL | versioned ingest + L0 segmentation (facts/procedural/holding/order); tests/test_corpus_e2e.py |
| Provision cross-references | FUNCTIONAL | deterministic L0 extractor (άρθρο 15(2)(α), ΚΕΦ.6, Κεφ.148, Ν.123(I)/2020, ECLI, case no) + scan creates ProvisionCrossReference with exact spans; /citation/scan-provision-refs; tests/test_provision_refs_e2e.py |
| Citation graph | FUNCTIONAL | validated edges (must exist), semantic evidence requirement, traversal; tests/test_citation_e2e.py |
| Judgment enrichment / summary | FUNCTIONAL | source-grounded extractive summary from holding/analysis/order; tests/test_corpus_e2e.py |
| Case comparison | FUNCTIONAL | separate legal/factual/procedural/statutory/remedy dimensions with explanations; tests/test_similarity_e2e.py |
| Legal reference parser | FUNCTIONAL | Cyprus/EU Article/Law, ECLI, case-number; L0 exact bias |
| BM25 search | FUNCTIONAL | Postgres ts_vector/unaccent lexical (EN+EL); OpenSearch provider pluggable |
| Semantic search | NOT_STARTED | no local embed model on Pi; semantic mode falls back to lexical |
| Hybrid retrieval | PARTIAL | exact-reference + lexical fused; semantic punch-out deferred |
| Embeddings (replaceable) | FUNCTIONAL | multilingual-e5-small ONNX on HDD (384-dim, GR+EN) behind replaceable provider interface + EMBED_TEXT endpoint; pipeline EMBED persists vectors+meta+model_run_id on LegalChunk; tests/test_embedding_e2e.py |
| Reranking | FUNCTIONAL | ONNX MiniLM cross-encoder (qint8 arm64, no torch) via RERANK_SEARCH + /search?rerank=true; tests/test_rerank_e2e.py |
| Search explanations | FUNCTIONAL | reason_for_match on every result; provenance |
| Greek / English retrieval | FUNCTIONAL | tests/test_search_e2e.py; unaccent tsvector handles both |
| Matter workspace | FUNCTIONAL | create matter, upload doc, extract, chronology, fact accept/reject; tenancy isolation; tests/test_matter_ws_e2e.py |
| Matter document ingestion | FUNCTIONAL | private upload to MinIO; text + PDF parsing (PyMuPDF); tests/test_matter_ws_e2e.py |
| Fact extraction | PARTIAL | L0 deterministic extraction with source spans, proposed→review; no LLM |
| Chronology | FUNCTIONAL | dated events sorted by date |
| Issue spotting | FUNCTIONAL | L0 proposed issues from accepted facts for lawyer review; tests/test_matter_ws_e2e.py |
| Authority workspace | FUNCTIONAL | mark relied_on/adverse/distinguishable/rejected; corpus-validated; tests/test_authority_e2e.py |
| Legal research assistant | FUNCTIONAL | grounded retrieval + citation validation + unsupported path; tests/test_research_e2e.py |
| Citation validation | FUNCTIONAL | generated citations checked against corpus via /research/validate-citation |
| Procedural rules / deadlines | FUNCTIONAL | versioned rules; business/calendar days, holidays, ambiguity->REVIEW_REQUIRED; tests/test_procedure_e2e.py |
| Firm knowledge base | FUNCTIONAL | tenant-scoped precedents/templates, internal-labelled search, never primary authority; tests/test_gov_firm_draft_e2e.py |
| Drafting | FUNCTIONAL | verified-authority memo, nonexistent citations rejected, draft/review flag |
| Audit / evidence | FUNCTIONAL | append-only audit_events working; JSON/CSV export; Evidence model exists |
| Lawyer research workspace | FUNCTIONAL | login -> research workspace -> query+date -> result cards (why/evidence/temporal) -> save+classify authority supporting/adverse/neutral -> grounded assistant; /nomos/ui; TEST/DEMO corpus (real-authority corpus blocked externally) |
| Grounded assistant in workflow | FUNCTIONAL | exposed via /nomos/ui; provenance SOURCE FACT; honest insufficient-evidence path |
| Frontend workflows | FUNCTIONAL | browseable web UI at /ui (and /nomos/ui): login/register, search, validate-citation; real API via Apache proxy |
| Entitlements / usage metering | FUNCTIONAL | plan-based server-side feature denial; tests/test_plan_e2e.py |
| On-prem readiness | DOCUMENTED | DEPLOYMENT_ONPREM_READINESS.md: containerized, tenant-isolated, local AI no-egress, entitlements, public/private separable; installer deferred |
| Subscription tiers | FUNCTIONAL | FREE/DEMO vs PRO enforced server-side (Redis usage limits); check_usage + /plan/tier; lower tiers never get worse law; enable via enforce_usage_limits | core/tiers.py + /plan/tier (FREE/DEMO vs PRO; productivity-only limits); pricing captured as config, no pricing UI until core works |
| Production deployment | DEFERRED_PRODUCTION | Not part of current goal |
| Performance/load testing | DEFERRED_PRODUCTION | Not part of current goal |
| Real license-confirmed Cyprus corpus (adapter + gate) | FUNCTIONAL (P0) | app/adapters/data_gov_cy.py (SourceAdapter contract): real data.gov.cy Consumer Protection decisions (109 records) ingested under verified CC BY 4.0 (terms page snapshot consumer_dataset_terms_page_2026-09-23.html, sha256 2dfcf628…, licence_url creativecommons.org/licenses/by/4.0) through the immutable pipeline (SourceSnapshot raw + SourceDocument + LegalChunk + SearchEntry). Greek lexical search over the real decisions verified end-to-end. Council of Ministers P0 = BLOCKED_EXTERNAL (its data.gov.cy resources are link-only pointers to cm.gov.cy on a separate unverified host — no reusable file hosted by the portal). P1 (Labour court stats, Justice reports) + P2 + EUR-Lex/CELLAR pending. |
