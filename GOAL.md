# NOMOS — PRODUCT GOAL
Read this file, then continue/start the work. Operational details are in `HANDOVER.md`.
Goal id (pi): `munvb5ro-t0vb83`. Status: BLOCKED (see section 9) — resume after the data track is unblocked.

## 1. Objective
Build the functional NOMOS lawyer research product on the EXISTING foundation (reuse, never duplicate:
canonical legal model, temporal/versioning, ingestion pipeline, hybrid/exact/tree retrieval, citation
graph, reranker, search explanations, benchmark/eval, matter/authority, grounded assistant,
entitlements, containerized deployment). Order: (1) a real, licence-confirmed Cyprus public-law corpus
through finished adapters; (2) the complete lawyer-facing research workspace; (3) expose/refine the
grounded assistant inside it; (4) improve ranking only where the benchmark shows real gaps; (5) add the
subscription/pricing surface only after the core workflow is FUNCTIONAL; (6) keep on-prem architecture-ready
without an elaborate installer. NEVER bulk-ingest legally uncertain sources and NEVER pass synthetic/demo
material off as real authority.

## 2. Ordered tasks
- **task-1 corpus**: determine which Cyprus sources are legally reusable AND actually available; for each
  verify licence/reuse + automated/bulk access, record `SourceRegistry` evidence, prefer APIs/bulk;
  `UNKNOWN != permission`; no CyLaw bulk without confirmed permission. Finish/extend adapters through the
  existing immutable pipeline: discover→fetch→RAW→parse→normalize→canonical entities→references/versioning→
  chunk→embed→index. Ingest representative real reusable data; synthetic only clearly marked TEST/DEMO.
- **task-2 workspace**: turn the thin UI into the primary NOMOS research surface:
  login → workspace → query → filters (date/jurisdiction) → hybrid search → legislation+judgments →
  applicable historical version → why matched → exact evidence paragraph/span → citations/cited-by/treatment
  (where verified) → open authority → save to matter → classify supporting/adverse/neutral → grounded
  assistant. Must feel like a legal research system, not a chatbot or a search box.
- **task-3 assistant**: expose the existing grounded capability in the workflow; every proposition links to
  authority/evidence; distinguish `SOURCE FACT / STRUCTURED EXTRACTION / MODEL INFERENCE / LAWYER DECISION`;
  never fabricate authorities/citations/provisions/quotes/ECLI/case numbers/dates/deadlines; say when evidence
  is insufficient.
- **task-4 ranking**: keep growing the lawyer-style eval benchmark while building corpus/UI; no new retrieval
  subsystem; no fine-tuning; measure real lawyer queries (incl. Greek/English/cross-lingual/temporal) and
  improve top-rank precision with the existing system; record baseline→post-change; no regression on important
  query classes.
- **task-5 subscription**: keep existing entitlements; implement the commercially useful tiers (FREE/DEMO vs
  PRO/HOSTED) only once the core workflow is FUNCTIONAL. Never make a lower tier return worse/incorrect law —
  restrict productivity/capacity only. (Pricing config captured; no pricing page yet.)
- **task-6 on-prem ready**: ensure hosted architecture permits a later on-prem tier (firm-private corpus,
  tenant/private isolation, local embeddings/reranker, optional local LLM, no-egress mode, public/private
  distinguishable, license/entitlement, docker-compose, backup/update path) WITHOUT building an installer this
  goal.

## 3. Completion criteria (all must be FUNCTIONAL, with real legally reusable Cyprus authority, EN + GR)
A lawyer can: (1) search real Cyprus authority, (2) use Greek or English, (3) filter/refine, (4) see
legislation + judgments, (5) resolve legislation as-of a date, (6) see why each matched, (7) inspect exact
source evidence, (8) follow cross-references/citations, (9) save an authority to a matter, (10) classify
supporting/adverse/neutral, (11) ask a grounded question, (12) get an evidence-linked answer, (13) inspect
every source used. Benchmark measured, no regressions on important classes. Only then is pricing/subscription
UX the next priority. No broad drafting; no fine-tuning; no bulk-ingest of uncertain sources; no fake/demo
substitutes for a real production corpus.

## 4. Constraints / guardrails
- HDD-only storage; no SD writes; don't touch other services/containers.
- Only ingest confirmed-reuse sources; `UNKNOWN != permission`; CyLaw requires written consent.
- Synthetic/demo content must be clearly marked TEST/DEMO and never shown as real authority.
- Reuse existing code — do not create duplicate models/services/subsystems.

## 5. If blocked
Attempt concrete steps first. A genuine external blocker (licensing/access or unavailable data) that recurs
should be documented and the goal set BLOCKED with a clear reason + suggested action, rather than marked complete.

## 6. Commercial model (context; not built-as-pricing yet)
- Hosted NOMOS Pro ≈ EUR89/user/month (EUR890/yr); Firm ≈ EUR399/month incl 5 users +EUR59 extra.
- NOMOS Private/On-Prem ≈ EUR6k implementation + ~EUR12k/yr (10 users; +EUR300–500/user/yr).
- Do NOT charge by tokens; give an effectively-unlimited usage allowance under normal professional use.
- Lower tiers restrict productivity/capacity, never legal correctness.

## 7. How to start (current env)
Read `HANDOVER.md` for run commands, container state, DB/migrations, frontend at `/nomos/ui`,
and demo creds (`a@law.com / pw123`). Push model: `git@github.com:kkraso01/nomos.git` (key
`~/.ssh/id_ed25519_github`).

## 8. Product layer ALREADY DONE (do not redo) — commit 8b82b8f
Research workspace UI (search/evidence/save+classify/grounded assistant); grounded assistant in workflow;
server-side subscription tier enforcement (`core/tiers.py`, `/plan/tier`, `enforce_usage_limits`);
on-prem readiness doc; eval benchmark 17 queries. See `IMPLEMENTATION_STATUS.md` / `IMPLEMENTATION_LOG.md`.

## 9. The current blocker (why the goal stopped)
(1) No reachable, licence-confirmed, bulk-fetchable Cyprus legal source from this host: data.gov.cy
CC BY 4.0 confirmed but CKAN/site APIs 404/gated; EUR-Lex/HUDOC/Supreme Court bot-gated or JS; Gazette
UNKNOWN; CyLaw PERMISSION_REQUIRED; no production deployment allowed. → the "real legally reusable Cyprus
authority" criterion (task-1 + section 3) cannot be met here.
(2) The host's docker-data wipe destroyed the DB; only a tiny demo seed remains, so the benchmark
(task-4) shows dense/cross-lingual/temporal = 0 — a data-loss measurement artifact, not a ranking regression
(verified by forced re-embedding twice).

**To unblock (choose one):**
- (a) Provide a reachable, licence-cleared Cyprus dataset/source, or authorize a controlled, fully
  re-embedded fixture DB for a clean task-4 measurement → then `scripts/run_eval.py` dense classes should
  recover; or
- (b) `/goal-tweak` to relax the "real legally reusable Cyprus authority" criterion to
  "clearly-marked TEST/DEMO corpus + functional workflow" → the delivered product surface can then complete; or
- (c) grant on-prem/cloud access to a licensed corpus provider.

After unblocking, run `/goal-resume`. Remaining work: task-1 finish an approved-source adapter + a first
real ingest; task-4 get a clean baseline→post measurement (no regression). All else (tasks 2,3,5,6) is complete.