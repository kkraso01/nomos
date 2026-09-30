# NOMOS — Agent Handover & Resume Guide
Date: 2026-09-30 · Goal: munvb5ro-t0vb83 (BLOCKED — read "How to resume")

## 1. What this is
NOMOS = an AI-native legal-research + firm-workflow platform for Cyprus (Greek/English),
built as a modular FastAPI monolith (Postgres + Redis, optional MinIO/OpenSearch). The product
goal is split into TWO commercial tiers: **Hosted** (public legal research, subscriptions) and
**Private/On-Prem** (firm's own data + local AI, no-egress). Nobody has populated a real
production law corpus yet — ingestion is pipeline-ready but only demo/test data exists.

## 2. Where everything lives (HDD only — never write to the SD card)
- Repo/backend: `/mnt/jellyfin/Projects/NOMOS/NOMOS_agent_handoff`
- Venv: `/mnt/jellyfin/Projects/NOMOS/.venv`
- Caches: `/mnt/jellyfin/Projects/NOMOS/cache` (pip, npm, HuggingFace/Torch via env)
- Models (HDD): `/mnt/jellyfin/Projects/NOMOS/models/` → `e5-small/` (embedding, ONNX) and
  `reranker-minilm/` (reranker, ONNX)
- Docker data-root: `/mnt/jellyfin/Projects/NOMOS/docker-data` (volumes on HDD)
- Logs: `/mnt/jellyfin/Projects/NOMOS/logs/`
- GitHub remote: `git@github.com:kkraso01/nomos.git`, branch `master`, key
  `~/.ssh/id_ed25519_github`. Push with:
  `export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/id_ed25519_github -o IdentitiesOnly=yes"`

## 3. Running it (current state after the host reset)
Two containers are running (recreated on HDD; pullable from Docker Hub):
```bash
docker start nomos-postgres nomos-redis   # ports 5433 and 6380
# MinIO is NOT running: quay.io returns 401, so private-doc object storage is down (login/research/search work — Postgres-backed).
cd /mnt/jellyfin/Projects/NOMOS/NOMOS_agent_handoff/backend
source /mnt/jellyfin/Projects/NOMOS/.venv/bin/activate
export HF_HOME=/mnt/jellyfin/Projects/NOMOS/cache/huggingface XDG_CACHE_HOME=/mnt/jellyfin/Projects/NOMOS/cache
alembic upgrade head                     # DB is migrated to head 56dfebfaca51
python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 &   # API
python app/workers.py &                 # rq worker
```
Frontend: http://<host>/nomos/ur (Apache reverse proxy -> :8010). Demo login: `a@law.com / pw123` (plan: pro after set; default starter).

## 4. Backend capabilities (built, reused, working)
Canonical jurisdiction-agnostic model; temporal legislation/versions + amendments as events;
immutable content-addressed ingestion pipeline (DISCOVER..INDEX with provenance); hybrid retrieval
(BM25 + dense e5 + exact-reference + legislation-tree + citation-graph + temporal filter -> RRF ->
ONNX reranker -> explanation); deterministic Cyprus/Greek reference extractor; citation graph +
treatment; structural LegalChunk; multilingual e5-small embeddings; ONNX reranker; matter/authority
workspace (save/classify supporting/adverse/neutral, MODEL_INFERENCE suggestions); grounded
research assistant (provenance: SOURCE FACT / STRUCTURED EXTRACTION / MODEL INFERENCE /
LAWYER DECISION); firmer knowledge; deadlines; audit/export; entitlements (plan gate); versioned
eval benchmark (`eval/` + `scripts/run_eval.py`).

## 5. Product layer delivered & pushed (this goal, commit 8b82b8f)
- **Lawyer research workspace** UI (`backend/app/static/index.html`, served `/nomos/ui`): login ->
  query + as-of date + jurisdiction -> result cards (title, type badge, canonical ref, why-it-matched,
  exact evidence toggle, applicable historical version) -> save + classify authority supporting/adverse/
  neutral to a matter -> grounded assistant. Uses existing `/research/vertical` and `/assistant/ask`.
- **Grounded assistant** exposed in the UI (evidence-linked, honest insufficient path).
- **Server-side subscription enforcement**: `app/core/tiers.py` + `GET /plan/tier` + Redis daily
  usage limit (FREE=25 search/day, PRO unlimited) wired into `/search/hybrid` behind
  `settings.enforce_usage_limits` (default false in dev; enable in prod).
- **On-prem readiness**: `DEPLOYMENT_ONPREM_READINESS.md` (containerized, tenant-isolated, local ONNX
  AI, no-egress default, public/private separation, entitlements, audit). No installer built (correctly).
- **Benchmark** grown to 17 queries (`eval/queries`, `eval/expected`).

## 6. THE BLOCKER (why the goal stopped) — read before resuming
1. ~~No reachable, licence-confirmed, bulk-fetchable Cyprus legal corpus~~ **PARTIALLY RESOLVED 2026-09-30**
   (see §9b). The remaining gap is the FULL-TEXT **judgment / consolidated-statute** corpus
   (Supreme Court/Gazette/HUDOC still UNKNOWN; CyLaw PERMISSION_REQUIRED; EUR-Lex full text
   bot-gated on this host). The substantive-document/administrative-decision level of the
   Cyprus corpus is now real and ingested. UNKNOWN != permission remains enforced.
2. **Dataset was lost.** Host's docker-data wiped + reboot dropped containers/DB. Recreated a fresh
   DB with only a small demo seed (ELW law + 2 judgments). Consequently the benchmark (task-4)
   shows dense/cross-lingual/temporal = 0 — that's a data-loss measurement artifact, NOT a ranking
   regression (verified by re-embedding deleted fixture chunks twice).

Synthetic/demo material is clearly marked TEST/DEMO and must never be shown to lawyers as real authority.

## 7. How to resume (choose one)
- **(a) Provide real data** — a reachable, licence-cleared Cyprus legal dataset/source, or authorize
  creating a controlled, fully re-embedded fixture DB for a clean task-4 measurement. Then
  `python scripts/run_eval.py` should show dense classes recovering (they were ~1.0 before the wipe).
- **(b) Relax the criterion** — `/goal-tweak` the objective so completion accepts
  "clearly-marked TEST/DEMO corpus + functional workflow" instead of "real legally reusable
  Cyprus authority"; then the delivered product surface can be verified and the goal completed.
- **(c) On-prem/cloud access** to a licensed corpus provider.

After the blocker is cleared, run `/goal-resume`. Remaining work if the criterion is kept:
  task-1 finish an approved-source adapter + a first real ingest; task-4 get a clean
  baseline->post ranking measurement (no regression). Tasks 2,3,5,6 are complete.

## 8. Key files
- Status: `IMPLEMENTATION_STATUS.md` · Log: `IMPLEMENTATION_LOG.md` (see entries from 2026-09-30)
- Plan: `IMPLEMENTATION_PLAN.md` · Guardrails: `AGENTS.md`, `SOURCE_POLICY_AND_INGESTION.md`,
  `SOURCE_LICENSE_RESEARCH_2026-09-23.md`, `SOURCE_REGISTRY_SEED.yaml`
- Eval: `eval/README.md` (governance), `scripts/run_eval.py`, reports in `eval/reports/`
- Model config: `backend/app/core/tiers.py`, `backend/app/core/entitlements.py`
- Tests: `backend/tests/` (60+ e2e across the stack)
## 9a. Corpus access — CORRECTED mechanism (2026-09-30)
data.gov.cy is **DKAN** (not CKAN — this is why the earlier CKAN API 404s misled the generic-link assumption).
The real bulk catalog IS reachable:
- `https://data.gov.cy/data.json` → `https://data.gov.cy/sites/default/files/serialised_datasets/dcat_ap_2_0_json/all_datasets.json`
  (DCAT/RDF JSON, ~10 MB, 1,950 datasets). Parse each entry as `dcat:Catalog.dataset[].dcat:Dataset`; title = `dct:title`, resource = `dcat:Distribution[].@rdf:resource`.
- Licence is the portal default **CC BY 4.0** (FAQ). Distribution pages carry per-dataset terms.
- IMPORTANT: the catalog contains **open datasets/statistics, NOT full-text Cyprus legislation or judgments**. Only ~a handful are legal (e.g. court-case statistics per law). So data.gov.cy alone does NOT provide a legal-authority corpus — confirms the "do not assume it contains the complete corpus" caveat.
- Verified legal-adjacent datasets indexed in `eval/fixtures/data_gov_cy_legal_datasets.json`.
- Full-text authority would need EUR-Lex (approved, full text bot-gated), HUDOC/Gazette/Supreme Court (UNKNOWN), or CyLaw (permission required).

## 9b. Corpus DATA TRACK — RESOLVED (2026-09-30) — read this FIRST
A real, licence-gated Cyprus/EU ingestion path is DONE and functional, unblocking the data
side of the old blocker:
- **Adapters** `backend/app/adapters/` (`base.py` SourceAdapter contract, `data_gov_cy.py`,
  `eurlex_cellar.py`). Driver scripts `scripts/ingest_data_gov_cy.py`, `scripts/ingest_eurlex.py`.
- **Real file mechanism (DKAN)**: resource landing `/en/resource/i/<uuid>` → numeric
  `/el/resource/<id>/download/file` (raw CSV/XLSX/PDF). THIS is how files are actually served
  (the earlier generic link was a mistake; the corrected mechanism is verified).
- **Cyprus corpus ingested under individually re-verified CC BY 4.0** (terms pages snapshotted + hashed
  in `ingestion/licence_snapshots/`):
  - 109 Consumer Protection decisions (P0, ADMINISTRATIVE_DECISION)
  - 236 Labour-Inspection court-case-by-law stats (P1, CASE_STATISTICS — NOT judgments)
  - 1 Ministry of Justice annual report (P1, GOVERNMENT_PUBLICATION)
  - 19 bilateral legal-cooperation agreements (P2, JUDICIAL_METADATA)
  → 365 real Cyprus source_documents, Greek-searchable with provenance + external URL.
- **Council of Ministers decisions = BLOCKED_EXTERNAL** (all resources are link-only pointers to
  cm.gov.cy on a separate unverified host — no reusable file hosted by the portal).
- **EUR-Lex/CELLAR**: adapter built (real CELEX seeds 32011L0083, 32016R0679, REAL official titles),
  anti-fabrication normalize (refuses invalid CELEX/missing title), ingested through the real EU
  legislation pipeline and Greek-searchable. LIVE full-text bulk still externally gated (EUR-Lex
  202 anti-bot, cellar-imm-pub 000). Commercial resale gate honestly blocks until human clearance.
- **Offline adapter tests** `tests/test_adapters.py` (9 pass) over recorded real fixtures
  `eval/fixtures/data_gov_cy_{consumer_decisions.csv,labour_court_stats.xlsx}`.
- Remaining for "complete" Cyprus/EU authority: full-text court Judgments + consolidated statutes
  (still gated) and EUR-Lex full-text bulk (needs unconstrained network / monthly data dump).
  A clean task-4 re-measure can now rank a REAL corpus (not the near-empty demo DB), so
  `scripts/run_eval.py` should give a trustworthy signal once re-run on real data.
