# NOMOS Private / On-Prem — Architecture Readiness

Status: **architecture-ready note** (no installer built yet, per product goal ordering).
The hosted codebase is already shaped to deploy as a private, isolated instance. This
document records what is required for a future on-prem product and what is already true.

## What is already satisfied by the current architecture
- **Containerized monolith**: FastAPI + Postgres + Redis (+ MinIO when available) run via
  docker-compose. A private install uses the same compose with its own HDD volumes and ports.
- **Tenant / private matter isolation**: every matter/doc/fact/authority is `org_id`+`matter_id`
  scoped and `deny-by-default` (cross-org 404 verified). A private instance's own DB is its data.
- **Local AI**: on-device multilingual embeddings (multilingual-e5-small ONNX) and reranker
  (MiniLM ONNX) run locally with no cloud dependency; the embedding/rerank providers are
  replaceable behind a capability interface.
- **Optional local LLM / no-egress**: the AI router gates remote (L3) calls behind the org
  `remote_ai_policy`. For on-prem privacy, set the instance policy to `REMOTE_AI_DISABLED`
  (or `PUBLIC_ONLY`) so no firm data is sent externally; L0/L1 (rules, embeddings, reranker)
  are fully local.
- **Public vs private distinguishable**: canonical public-law results carry `source_scope=public`;
  firm/precedent/material is labelled `internal` / `primary_authority=false`. LegalChunk carries
  `source_scope` so a search can keep public + private strictly separate.
- **License / entitlement mechanism**: `Org.plan` + `core.entitlements.FEATURES` gates features
  server-side (e.g. AI_REMOTE, SEMANTIC_SEARCH, FIRM_KNOWLEDGE, DRAFTING). A private instance
  validates a license key -> plan -> entitlements.
- **Audit / export**: append-only `audit_events` + JSON/CSV export give the firm an auditable,
  no-egress record.

## What is required for the on-prem product (future)
- An **installer**: `docker-compose` + a setup script that generates local secrets (JWT, DB),
  creates volumes, runs `alembic upgrade head`, seeds jurisdictions/sources, and prints a local
  "instance ready" screen and admin bootstrap creds.
- **License key** validation at install + periodic local check (no network dependency for core;
  no exfiltration of firm data).
- **Local/private LLM** hook: when a local model is available, route L3 capabilities to it;
  otherwise gate to local-only. Provide a switch: `PUBLIC_ONLY` / `REMOTE_AI_DISABLED` (default
  for private = disabled) / `PRIVATE_ALLOWED` (only if user accepts egress risk).
- **Firm-private corpus intake**: reuse the existing ingestion pipeline (immutable RAW -> canonical
  entities -> chunk -> embed -> index) for the firm's own documents (docx/PDF/txt) and matter data.
- **Backup / restore**: `pg_dump` + MinIO volume tar (documented in README); on-prem needs a
  scheduled backup/update tool.

## Explicit no-egress guarantee (engineering)
- Default `remote_ai_policy = REMOTE_AI_DISABLED` for on-prem.
- The platform must make **no external network call carrying firm data**: no telemetry, no remote
  embedding/rerank (local ONNX), no remote LLM unless explicitly enabled by the firm.
- Every remote-capability call is audit-logged (`model_run_logs`, `audit_events`) so egress is
  provable-or-absent.