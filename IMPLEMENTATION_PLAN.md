# NOMOS — Dependency-Aware Implementation Plan

This plan is for full product implementation, not a toy MVP. Build sequentially but continue automatically through later phases when functional acceptance is met. Production deployment/performance gates are separate from feature-completion gates.

## Phase A — Platform Foundation

Deliver:
- FastAPI app/application service structure;
- PostgreSQL + Alembic conventions;
- organisation/user/membership/RBAC;
- matter-aware authorization primitives;
- Redis/background jobs;
- MinIO/S3 abstraction;
- append-only audit events;
- Evidence model;
- AI Router/provider abstraction;
- source registry/reuse enforcement;
- Next.js shell with auth/organisation navigation;
- idempotency support for retry-sensitive writes.

Functional acceptance:
- organisation isolation verified server-side;
- document object can be written/read through storage abstraction;
- background job can persist durable result/progress;
- migration up/down or forward migration path verified in development PostgreSQL;
- source marked `UNKNOWN` cannot bulk ingest;
- AI business module can request a capability without knowing provider/model.

## Phase B — Public Legal Corpus

Deliver:
- `LegalSource`, `SourceSnapshot`, `SourceDocument`;
- immutable RAW → NORMALIZED pipeline;
- Judgment/JudgmentVersion;
- Legislation/LegislationVersion/LegislationNode;
- source adapters with discover/fetch/normalize contract;
- approved open source adapter(s), beginning with safe/official mechanisms;
- gated adapter scaffolds for Gazette/Supreme Court/HUDOC where reuse not yet verified;
- CyLaw link/reference support only, no bulk ingestion without permission;
- provenance/hash/versioning.

Functional acceptance:
- approved sample source ingests to immutable raw + canonical record;
- repeated ingest is idempotent/deduplicated;
- changed source creates a new version rather than destructive overwrite;
- source provenance is visible through API/UI;
- restricted/unknown source bulk acquisition is blocked.

## Phase C — Search & Retrieval

Deliver:
- OpenSearch projections;
- lexical/BM25 search;
- exact-reference parser for Cyprus forms;
- semantic embedding index;
- hybrid retrieval/RRF;
- multilingual reranker;
- filters;
- result explanation;
- research UI with Hybrid/Exact/Semantic/Advanced modes;
- initial labelled retrieval fixtures.

Functional acceptance:
- Greek and English representative queries return lexical + semantic results;
- exact Article/case lookup bypasses fuzzy ambiguity when deterministically matched;
- candidate fusion and reranking execute;
- filters work;
- every result has canonical source link/provenance and a reason-for-match explanation.

## Phase D — Temporal Legislation & Legal Graph

Deliver:
- effective-date version resolution;
- amendment records/operations;
- provision cross-references;
- case citations;
- judgment↔provision links;
- graph expansion APIs;
- legislation tree UI;
- historical version comparison.

Functional acceptance:
- query with date resolves correct historical provision version;
- current and historical text are not conflated;
- Article view shows hierarchy and relevant linked cases where data exists;
- citation traversal can show cited/citing authorities;
- every semantic treatment edge contains evidence/review status.

## Phase E — Legal Intelligence Enrichment

Deliver:
- judgment segmentation;
- extracted facts/issues/procedural history/holding/reasoning;
- legal-reference extraction;
- case similarity dimensions;
- case comparison;
- source-grounded summary;
- adverse/supporting/distinguishable search support;
- enrichment review states.

Functional acceptance:
- structured output points to exact source spans;
- no authoritative quote is generated from model memory;
- generated citation is validated against canonical record;
- case comparison separately reports legal/factual/procedural/statutory similarity;
- unsupported output becomes REVIEW_REQUIRED or omitted.

## Phase F — Matter Workspace

Deliver:
- Matter/MatterMember/Party;
- private document ingestion;
- parsing/OCR pipeline;
- private indexing;
- MatterFact/MatterIssue/MatterEvent/MatterEvidence;
- chronology UI;
- issue review;
- matter authority workspace;
- strict private/public index separation.

Functional acceptance:
- lawyer can create matter, upload representative document, parse/OCR it, and see source-linked proposed facts/events;
- accepting/rejecting items persists lawyer decision;
- another organisation cannot retrieve the matter/document via API or search;
- accepted issues can launch related legal research.

## Phase G — Research Assistant & Arguments

Deliver:
- grounded matter Q&A;
- public + private retrieval orchestration;
- source validation before generation;
- contrary authority search;
- matter authority states;
- argument graph with positions/propositions/authority/evidence;
- research memo generation.

Functional acceptance:
- matter question retrieves and cites canonical public law and permitted matter evidence;
- nonexistent citation is blocked;
- "no sufficiently supported authority found" path exists;
- lawyer can mark authority relied-on/adverse/distinguishable/rejected;
- draft memo cites verified sources and remains marked draft/lawyer review required.

## Phase H — Firm Knowledge

Deliver:
- FirmPrecedent/FirmTemplate;
- private prior-matter/work-product indexing;
- permission-aware internal search;
- public-vs-internal source labelling;
- feedback capture for relevance (open/save/reject/adverse/cited).

Functional acceptance:
- lawyer can find similar internal work only when authorized;
- internal memo is never presented as primary legal authority;
- tenant boundaries hold in search and generation;
- user feedback is stored but not automatically used to retrain uncurated models.

## Phase I — Procedure, Deadlines, Drafting & Monitoring

Deliver:
- versioned ProceduralRule;
- deterministic deadline calculator;
- holiday/business-day framework;
- uncertainty/review handling;
- drafting workflows based on accepted facts/issues/authorities/templates;
- followed laws/articles/cases/issues;
- change/new-authority notifications.

Functional acceptance:
- supported rule + trigger date produces deterministic deadline with source;
- ambiguous trigger/rule returns REVIEW_REQUIRED rather than guessed date;
- generated draft uses selected verified inputs;
- followed item can produce a source-backed update notification when new ingested data creates a relevant change.

## Phase J — SaaS Hardening

Deliver:
- entitlements/usage metering;
- plan-ready architecture;
- invitation/password reset/session revocation/MFA-ready fields;
- backups/restore documentation;
- privacy controls and remote-AI policy UI;
- operational health/readiness;
- source terms re-verification process;
- export/audit capabilities;
- on-prem/private deployment architecture documentation.

Functional acceptance for local development:
- entitlements deny disallowed feature access server-side;
- remote-AI policy is enforced;
- audit export works;
- backup/restore mechanism exists and is documented;
- source registry can disable an adapter immediately;
- no production deployment is required to call feature implementation complete.

## Deferred production/readiness validation

Track separately, do not use as a reason to stop feature development:

- sustained load/stress tests;
- high-concurrency benchmarking;
- production penetration test;
- chaos testing;
- long soak tests;
- cloud/Pi parity benchmarking;
- sustained Raspberry Pi thermal benchmarking;
- production deployment/cutover.

## Definition of phase complete

A phase is complete when:
- required domain behavior exists;
- real local functional workflow passes using representative data;
- migrations exist and are coherent;
- security/tenancy tests relevant to changes pass;
- source/evidence provenance works;
- targeted tests pass;
- no introduced correctness regression remains;
- external permission/deployment items are documented separately rather than misclassified as missing feature code.
