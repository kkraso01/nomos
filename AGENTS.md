# AGENTS.md — NOMOS Repository Operating Contract

Read this file and `PRD.md`, `SOURCE_POLICY_AND_INGESTION.md`, `ARCHITECTURE_AND_RETRIEVAL.md`, and `IMPLEMENTATION_PLAN.md` completely before changing code.

## Mission

Build NOMOS as a source-grounded Cyprus legal intelligence platform, not a generic RAG chatbot. Implement the full dependency-aware plan with real functional workflows.

## Mandatory product principles

1. **No source, no authoritative legal claim.**
2. **Never invent judgments, citations, case numbers, provisions, quotations, holdings or deadlines.**
3. **Search before reasoning.**
4. **Exact keyword/reference retrieval remains first-class. Embeddings do not replace BM25/legal-reference parsing.**
5. **Historical law matters.** Resolve applicable legislation version by effective date.
6. **Legislation structure matters.** Preserve Law→Part→Chapter→Article→SubArticle→Paragraph.
7. **Authority and relevance are different.** Do not create opaque scores pretending to determine legal force.
8. **Public corpus and firm-private knowledge remain separate.**
9. **AI assists; lawyer decides.**
10. **Raw source material is immutable.**

## Source/legal-access safety

Public accessibility is NOT permission for commercial bulk ingestion.

Every live source must be registered with reuse/licence state and acquisition permissions.

The ingestion service MUST block bulk/systematic ingestion when reuse status is UNKNOWN, PERMISSION_REQUIRED, RESTRICTED or DISABLED.

Specific hard rule: **Do not bulk scrape, externally index, or systematically download CyLaw without prior written permission.** Keep CyLaw as link/reference/quality cross-check unless permission is recorded.

Prefer official primary/open sources and official APIs/bulk mechanisms where available.

Never bypass access controls, CAPTCHAs, robots restrictions, or rate limits.

## AI hierarchy

Use lowest reliable level:

- L0 deterministic rules/parsers/search/date/version logic
- L1 local ML for OCR/embeddings/reranking/classification
- L2 local open-source LLM for extraction/comparison/summaries
- L3 remote provider fallback for difficult reasoning/drafting when policy permits

Business modules request capabilities from the AI Router and never provider/model names directly.

## Remote AI privacy

Do not send private client/firm data to remote AI unless organisation policy is `PRIVATE_ALLOWED` and provider terms/configuration are compatible.

Policies:

```text
REMOTE_AI_DISABLED
PUBLIC_ONLY
PRIVATE_ALLOWED
```

Never print, log or commit API secrets.

## Search architecture

Default research is hybrid:

```text
BM25 + exact references + dense semantic + legislation-tree + citation-graph
→ deduplicate
→ RRF/fusion
→ rerank
→ temporal/metadata explanation
```

Do not use vector-only retrieval.

## Evidence

Every important extraction/inference should link to evidence locators (document/page/paragraph/span/provision/judgment paragraph). Generated legal citations must be validated against canonical data before display.

Quotations must be exact source spans, not model memory.

## Multi-tenancy

Deny by default.

Every private tenant-owned row is organisation-scoped. Matter-sensitive resources are matter-scoped as well. Authorization is server-side, never UI-only.

Never leak private content into global indexes, logs, fixtures or another tenant's search.

## Data/storage

PostgreSQL is source of truth. OpenSearch is a rebuildable projection. MinIO/S3 stores immutable source/private objects. Redis is not durable legal truth.

Version important source/legal/matter artifacts; do not overwrite accepted/history-bearing records.

## Money/billing

Subscription/usage accounting may use Decimal/NUMERIC. Do not use floating point for authoritative monetary values.

## Functional correctness priority

Docker Compose, PostgreSQL, OpenSearch, Redis and MinIO may be started/used for functional verification when they are part of this repository's stack.

Current priority is **feature correctness**, not sustained performance testing.

Allowed:
- migrations;
- integration checks;
- small representative E2E workflows;
- small OCR/search/model tests;
- background-job checks.

Deferred unless explicitly requested:
- load/stress/concurrency benchmarks;
- chaos testing;
- long soak tests;
- production penetration testing;
- sustained Pi thermal/OCR benchmarks;
- cloud/Pi parity performance tests;
- production deployment.

Do fix resource/safety defects that affect correctness (runaway memory, infinite loop, uncontrolled disk growth, deadlocks, unbounded jobs).

## Testing policy

Use resource-aware testing:

- focused unit tests while editing;
- targeted integration tests for changed subsystem;
- migration tests for schema changes;
- tenant/auth tests for security changes;
- representative small legal fixtures;
- phase-level regression at phase boundaries.

Do not repeatedly run expensive full corpora/model benchmarks.
Do not delete/weaken valid tests merely because they are slow; classify them.

## Existing code policy

Prefer:

```text
KEEP → REFACTOR → EXTEND → REPLACE only when necessary
```

Do not rewrite functioning architecture merely for style.

## Background jobs

Jobs must be idempotent, observable, bounded, retryable where safe, and backed by durable state. No infinite retries or uncontrolled worker spawning.

## Failure behavior

Provider/source failure must not corrupt canonical state. Preserve raw/deterministic work. Use FAILED/DEGRADED/REVIEW_REQUIRED/BLOCKED states. Never invent missing legal data.

## Human approval

AI auto-accept never means lawyer approval. Lawyer decision is required before adopted legal conclusions/work product.

## Implementation log

Maintain `IMPLEMENTATION_LOG.md` with meaningful phase completions, migrations, architecture/model/source decisions, source permission blockers, major regressions, and deliberate deviations. Avoid line-by-line noise.

## Cache / storage location (HARD REQUIREMENT)

The SD card is small and must not be used for caches or downloaded artifacts.

All caches and downloads for this project MUST live on the hard drive under `/mnt/jellyfin/Projects/NOMOS/`:

- Docker data-root: `/mnt/jellyfin/Projects/NOMOS/docker-data` (set in `/etc/docker/daemon.json`)
- npm cache: `/mnt/jellyfin/Projects/NOMOS/cache/npm`
- pip cache: `/mnt/jellyfin/Projects/NOMOS/cache/pip`
- HuggingFace / torch / model caches: `/mnt/jellyfin/Projects/NOMOS/cache/...` (`HF_HOME`, `TORCH_HOME`, `XDG_CACHE_HOME`)

Do NOT write caches, model weights, pip/npm downloads, or Docker images to the SD card (`/`, `/var/lib/docker`, `~/.npm`, `~/.cache`). If a tool defaults to the SD card, redirect it to the HDD paths above.

## Git safety

Do not force-push, rewrite history, delete branches, commit secrets or delete user data. Keep checkpoints reviewable.

## Autonomous continuation

Complete Phase A through J sequentially. Do not stop after each phase to ask whether to continue.

A production/performance validation item is not a blocker to continuing feature implementation.

Stop only for a genuine human-required blocker, such as:
- missing credentials not already configured;
- source permission/licensing decision;
- destructive/irreversible action;
- material product ambiguity that cannot be safely inferred;
- external service/account approval with no safe fixture/mock substitute.

When blocked on one item, finish all other safe work first.
# ECONOMICAL MODEL-USAGE POLICY

The development agent is operating under a strict low-cost budget.

Primary objective:
maximize useful implementation per token/API call.

Rules:

1. Do not repeatedly summarize the entire repository.
2. Do not re-read large files unless needed for the current task.
3. Read only the relevant sections/files for the current subsystem.
4. Use grep/ripgrep/file inspection before asking the model to reason about large areas.
5. Prefer deterministic shell/code inspection over LLM analysis.
6. Keep responses concise and action-oriented.
7. Avoid verbose explanations while coding.
8. Do not generate large planning documents repeatedly.
9. IMPLEMENTATION_PLAN.md and AGENTS.md are source of truth; do not restate them every turn.
10. Update IMPLEMENTATION_LOG.md briefly with only meaningful changes.
11. Run targeted tests only.
12. Do not run full test suites unless a phase boundary or regression requires it.
13. Do not repeatedly inspect unchanged files.
14. Reuse prior repository state instead of regenerating analysis.
15. Work in small vertical slices and commit/checkpoint after each meaningful unit.
16. If one command can inspect the required state, do not use multiple LLM calls.
17. Prefer local tools for:
    - search
    - grep
    - diffs
    - formatting
    - syntax checks
    - test discovery
    - schema inspection
18. Do not ask the model to explain obvious compiler/test output unless diagnosis is needed.
19. Keep prompts and generated comments concise.
20. Do not generate speculative future architecture unless required by the current implementation step.

When reading long specification files:
- first locate the relevant heading,
- read only that section plus necessary dependencies,
- do not reload the whole file.

When implementing:
inspect → change → targeted test → fix → log → continue.

Do not spend tokens narrating the process.

# AUTONOMOUS EXECUTION DISCIPLINE

The coding agent must behave conservatively, economically, and sequentially.

## Source of truth

Priority order:

1. AGENTS.md
2. CURRENT_TASK.md
3. IMPLEMENTATION_PLAN.md
4. PRD.md
5. ARCHITECTURE_AND_RETRIEVAL.md
6. SOURCE_POLICY_AND_INGESTION.md
7. IMPLEMENTATION_STATUS.md
8. IMPLEMENTATION_LOG.md
9. Existing repository code

If instructions conflict, stop only when the conflict is material and cannot be safely resolved.

## Work sequencing

Always:

inspect
→ understand
→ make smallest coherent change
→ targeted test
→ fix failure
→ update status
→ continue

Never jump randomly between unrelated modules.

Do not implement future-phase work unless it is required by the current feature.

## Functional completion rule

Do not mark something complete because:

- schema exists
- model exists
- endpoint exists
- class exists
- placeholder exists
- mock test passes
- UI page renders
- TODO was removed

A feature is complete only when the intended workflow works end-to-end with representative data.

## Implementation states

Every requirement must be one of:

NOT_STARTED
SCAFFOLDED
PARTIAL
FUNCTIONAL
BLOCKED_EXTERNAL
DEFERRED_PRODUCTION

Use IMPLEMENTATION_STATUS.md as the canonical implementation-status record.

Only FUNCTIONAL means implemented.

## Cost discipline

Model/API usage must be minimized.

Do not:

- reread the entire repository repeatedly
- reread PRD.md unless needed
- regenerate architecture explanations
- produce long narrative progress reports
- repeatedly summarize unchanged files
- use the model for grep/search/diff/test discovery
- make speculative changes outside the active task

Prefer shell/tools for:

- rg
- grep
- find
- git diff
- git status
- test discovery
- formatting
- schema inspection
- file counts
- dependency inspection

Read only the relevant file sections required for the current task.

## Response discipline

While coding, responses should be concise.

Do not narrate every action.

Use short progress summaries such as:

Implemented:
- X
- Y

Verified:
- targeted test Z

Next:
- W

## Test discipline

Functional correctness is the current priority.

Allowed:

- targeted unit tests
- targeted integration tests
- PostgreSQL functional checks
- Redis functional checks
- MinIO functional checks
- OpenSearch functional checks
- API functional checks
- frontend workflow checks
- small representative OCR/search/legal fixtures

Deferred:

- load testing
- stress testing
- soak testing
- thermal testing
- performance benchmarking
- production chaos testing
- large-scale evaluation
- production deployment

Do not treat deferred performance work as a blocker.

## Docker policy

Docker Compose may be used for functional verification.

The agent may start NOMOS-owned containers.

Do not:

- stop unrelated containers
- prune Docker globally
- delete volumes
- run docker compose down -v
- alter unrelated services

## Git discipline

Before a substantial change:

- inspect git status

After a coherent feature:

- inspect git diff
- ensure unrelated files were not modified
- run targeted tests
- update IMPLEMENTATION_STATUS.md
- update IMPLEMENTATION_LOG.md briefly

Never:

- force push
- rewrite history
- delete branches
- reset --hard without explicit approval
- delete unfamiliar files

## Failure discipline

If a test fails:

1. determine whether failure was introduced by current change
2. fix current regression
3. rerun only the relevant test
4. do not start broad unrelated refactors

If provider/model call fails:

- retry at most once
- do not loop
- preserve current state
- continue with deterministic/local work if possible

## Legal-source discipline

Do not bulk ingest any legal source whose SourceRegistry reuse status is:

UNKNOWN
PERMISSION_REQUIRED
RESTRICTED
DISABLED

Public visibility does not equal reuse permission.

CyLaw must not be bulk crawled without written permission.

Prefer official/open/approved primary s                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      