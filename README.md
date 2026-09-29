# NOMOS Agent Handoff Bundle

This bundle is the implementation handoff for **NOMOS**, an AI-native Cyprus legal intelligence, research, litigation-support, and private law-firm knowledge platform.

Start here:
1. Read `PRD.md` completely.
2. Read `SOURCE_POLICY_AND_INGESTION.md` before writing any source crawler or adapter.
3. Read `ARCHITECTURE_AND_RETRIEVAL.md`.
4. Read `IMPLEMENTATION_PLAN.md`.
5. Treat `AGENTS.md` as mandatory repository-level operating instructions.
6. Use `AGENT_START_PROMPT.txt` as the initial autonomous coding-agent prompt.

The package deliberately distinguishes **functional implementation** from **production performance/readiness validation**. During feature development, Docker/PostgreSQL/OpenSearch/Redis/MinIO may be used to prove that real workflows work. Sustained load, stress, chaos, thermal, cloud-parity, and production deployment work is deferred unless explicitly requested.

## Product in one sentence

NOMOS turns public Cyprus/EU legal sources plus each firm's private knowledge into an evidence-first legal research and matter-intelligence system with hybrid keyword + semantic retrieval, temporal legislation, citation graphs, case similarity, chronology, argument support, procedural rules, and source-grounded drafting.

## Critical source rule

**Publicly accessible is not the same as legally approved for bulk ingestion.** Every source must be registered with explicit reuse status, terms/licence evidence, and an activation gate before bulk harvesting.

Current source position is summarized in `SOURCE_POLICY_AND_INGESTION.md` and must be re-checked before enabling any production ingestion adapter.

## Development status (2026-09-23)

A working modular FastAPI backend (`backend/`) against PostgreSQL + Redis + MinIO on the local
host is implemented and covered by **27 passing end-to-end tests** (`backend/tests/`). See
`IMPLEMENTATION_STATUS.md` for the live per-area status.

### How to run locally

```bash
# 1) infra (data stays on the HDD; pg 5433 / redis 6380 / minio 9011-9012 to avoid clashes)
docker compose up -d

# 2) backend (Python venv on the HDD)
cd backend
../.venv/bin/pip install -e ".[dev]"
../.venv/bin/alembic upgrade head
../.venv/bin/python -m uvicorn app.main:app --port 8010   # API docs at /docs
../.venv/bin/python app/workers.py                        # durable rq jobs

# 3) tests
../.venv/bin/python -m pytest tests/ -q
```

### Implemented workflows (functional with representative data)

- Org/user auth + JWT tenancy isolation (cross-org reads denied).
- Source registry seeding + reuse gate (UNKNOWN/PERMISSION_REQUIRED blocked from bulk ingestion).
- Immutable raw → canonical ingestion with dedupe and version-on-change (+ provenance).
- Versioned legislation/judgment models, temporal (as-of) version resolution.
- L0 legal-reference parser (Article/Law, ECLI, case number) with exact-search bypass.
- Lexical search (PostgreSQL tsvector + unaccent; Greek + English) with reason-for-match, plus
  exact-reference bypass. Semantic/reranker providers are pluggable but not configured (no local
  embedding model on this device).
- Citation graph (validated edges; semantic treatment requires evidence).
- Matter workspace: private document upload, L0 fact/event extraction, chronology, fact review,
  issue recording, authority marking (relied-on/adverse/distinguishable/rejected).
- Grounded research assistant: retrieval anchored in corpus, citation validation, and an explicit
  "no sufficiently supported authority found" path — never fabricates.
- Firm knowledge base (tenant-scoped, internal labelled, never primary authority).
- Deterministic procedural deadline calculator (business/calendar days, holidays,
  ambiguity -> REVIEW_REQUIRED).
- Drafting: research memo from accepted facts + verified authorities; nonexistent citations
  rejected; marked draft/lawyer-review-required.
- Followed-item update notifications; append-only audit with JSON/CSV export; plan-based
  entitlements gate.

### Backup / restore (Phase J)

The canonical store is PostgreSQL; search entries and the search GIN index are rebuildable from
the corpus. MinIO holds raw/private objects (named volume `nomos_nomos-minio`).

```bash
# backup
./.venv/bin/python -m pip show psycopg >/dev/null
docker exec nomos-postgres pg_dump -U nomos -Fc nomos > backups/nomos.dump
docker run --rm --volumes-from nomos-minio -v "$PWD/backups":/b \
  alpine tar czf /b/minio.tgz -C /data .

# restore PostgreSQL
docker exec -i nomos-postgres pg_restore -U nomos -d nomos --clean < backups/nomos.dump
```

### Apache exposure

NOMOS is reachable at `http://<host>/nomos/` through the existing Apache server
(reverse proxy to the local FastAPI backend on `127.0.0.1:8010`). A backup of the
stock vhost lives at `/etc/apache2/sites-enabled/000-default.conf.nomos-bak`.

- `GET /nomos/` → browsable landing page
- `GET /nomos/health` → JSON health
- `GET /nomos/docs` → Swagger UI

The proxy block was appended to the `:80` default vhost (same pattern as the
pre-existing demiourgo preview) and reloaded with a graceful `systemctl reload
apache2` — no other service was stopped or altered.

To re-apply after a fresh config: in `/etc/apache2/sites-enabled/000-default.conf`
inside the `<VirtualHost *:80>` add
```apache
ProxyPreserveHost On
ProxyPass        /nomos/ http://127.0.0.1:8010/
ProxyPassReverse /nomos/ http://127.0.0.1:8010/
```
then `sudo apachectl configtest && sudo systemctl reload apache2`.

- `GET /nomos/ui` (or `/nomos/frontend`) → minimal **web UI** (login/register, public search,
  citation validation) whose JavaScript calls the same API through the same `/nomos/` proxy.

### Semantic reranking (on-device, no GPU)
A small efficient reranker runs on the Pi: `cross-encoder/ms-marco-MiniLM-L-6-v2`
exported as **qint8 ARM64 ONNX** (22.6 MB, HDD `models/reranker-minilm`), served by
ONNX Runtime (no torch/CUDA).

- `POST /ai/capability {capability:"RERANK_SEARCH", prompt, documents:[...]}` → per-doc scores.
- `GET /search?q=...&rerank=true` → lexical/exact candidates reranked by the cross-encoder
  (graceful fallback to lexical order if the model is unavailable).

Semantic *embeddings* (dense retrieval) remain intentionally unconfigured on this device.
Model download: `huggingface_hub` → `cross-encoder/ms-marco-MiniLM-L-6-v2`, file
`onnx/model_qint8_arm64.onnx` (+ tokenizer/config) into `models/reranker-minilm`.
