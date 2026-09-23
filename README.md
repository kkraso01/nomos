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
