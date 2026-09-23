# NOMOS — Architecture and Retrieval Specification

## 1. Architectural shape

Start as a **modular monolith with background workers**, not microservices.

```text
Next.js Web
   |
FastAPI API
   |
Application Services + Policy Layer
   |
PostgreSQL  <----> OpenSearch projection
   |                 |
Redis            hybrid legal search
   |
Background Workers
   |
MinIO/S3 raw/private documents
   |
AI Router
 L0 rules/parsers → L1 local ML → L2 local OSS LLM → L3 remote fallback
```

PostgreSQL is canonical source of truth. OpenSearch is a rebuildable search projection.

## 2. Bounded contexts

1. Identity & Tenancy
2. Public Legal Corpus
3. Legislation & Temporal Versions
4. Case Law & Citation Graph
5. Search & Retrieval
6. Evidence & AI Governance
7. Matter Workspace
8. Firm Knowledge
9. Procedure & Deadlines
10. Argument & Drafting
11. Monitoring/Updates
12. Entitlements/Audit

## 3. Hybrid search pipeline

```text
RAW QUERY
  ↓
language detection
  ↓
L0 exact-reference parser
  ↓
query understanding
  ↓
parallel candidate generation
  ├─ BM25 / exact phrase
  ├─ dense semantic
  ├─ exact case/statute lookup
  ├─ legislation-tree expansion
  └─ citation-graph expansion
  ↓
deduplication
  ↓
rank fusion (RRF initially)
  ↓
multilingual reranker
  ↓
metadata/temporal explanation layer
  ↓
results + WHY THIS RESULT
```

Do not sum incomparable BM25/vector scores directly unless calibrated and validated.

## 4. Search modes

- **Hybrid** — default.
- **Exact** — lexical/citation/legal-reference focused.
- **Semantic** — natural-language conceptual/factual similarity.
- **Advanced** — hybrid plus explicit filters.

## 5. Lexical retrieval

OpenSearch BM25 should support:

- exact phrase;
- AND/OR/NOT;
- fielded queries;
- proximity;
- Greek normalization;
- case number/ECLI;
- legislation/article number;
- judge/court/date.

Legal retrieval must never remove lexical search in favor of embeddings.

## 6. Semantic retrieval

Baseline candidate: `Qwen3-Embedding-0.6B` behind capability `EMBED_TEXT`.

Benchmark against multilingual alternatives such as BGE-M3/e5-style models using a Cyprus-law evaluation set.

Requirements:

- Greek↔Greek;
- English↔English;
- Greek query→English authority;
- English query→Greek authority;
- legally meaningful chunks, not arbitrary fixed token windows.

## 7. Reranking

Baseline candidate: `Qwen3-Reranker-0.6B` behind `RERANK_SEARCH`.

Reranker scores relevance, while deterministic metadata supplies context such as:

- exact same provision;
- applicable legislation version;
- same court/court level;
- same procedural posture;
- citation relationship;
- date constraints.

Do not create an opaque "authority score" that pretends to determine legal force.

## 8. Legislation tree

Canonical hierarchy:

```text
LAW
└─ PART
   └─ CHAPTER
      └─ ARTICLE
         └─ SUBARTICLE
            └─ PARAGRAPH
```

Each node maintains source text, normalized text, language, parent, sort order, version, effective dates, and source locator.

Graph/tree retrieval can expand a target provision to:

- parent Part/Chapter;
- definitions;
- referenced provisions;
- provisions referencing target;
- amendment acts;
- historic applicable version;
- subsidiary legislation;
- cases linked to the provision.

## 9. Temporal legislation

Never overwrite legislation text.

Represent effective intervals and supersession.

Queries containing a relevant event/matter date must resolve the applicable version before answering authoritative questions.

## 10. Citation graph

Deterministic/strongly evidenced edges:

```text
CASE CITES CASE
CASE REFERENCES PROVISION
PROVISION REFERENCES PROVISION
```

Reviewable semantic treatment edges:

```text
FOLLOWS
DISTINGUISHES
APPROVES
CRITICISES
OVERRULES
```

Every treatment relationship needs supporting source evidence.

## 11. Similarity dimensions

Keep separate:

```text
LEGAL_ISSUE_SIMILARITY
FACTUAL_SIMILARITY
PROCEDURAL_SIMILARITY
STATUTORY_SIMILARITY
REMEDY_SIMILARITY
```

Show explanations, not just percentages.

## 12. Chunking

### Legislation

Chunk by canonical legal hierarchy while retaining context path.

### Judgments

Keep paragraph chunks plus larger semantic sections such as facts, procedural history, issue, party argument, legal analysis, holding, order, separate opinion.

### Private documents

Prefer document structure (heading, paragraph, clause, table, email message) and preserve page/paragraph/character spans.

## 13. Evidence model

Reusable Evidence locator supports:

```text
source_document_id
source_version_id
page
paragraph
bbox
char_start
char_end
legislation_node_id
judgment_paragraph_id
matter_document_id
text_hash
```

AI/extraction outputs must be able to drive **Show evidence**.

## 14. AI hierarchy

- L0 deterministic: references, graph traversal, dates, legislation version resolution, BM25, filters, citation existence checks.
- L1 local ML: OCR, embeddings, reranking, classifiers/NER.
- L2 local OSS LLM: judgment structure, facts/issues, summaries, comparison explanation.
- L3 remote model: difficult multi-document reasoning/drafting when permitted.

Use lowest reliable level.

## 15. AI Router

Business code requests capabilities, never provider/model names.

Core capabilities:

```text
OCR_DOCUMENT
EMBED_TEXT
RERANK_SEARCH
CLASSIFY_DOCUMENT
EXTRACT_JUDGMENT_STRUCTURE
EXTRACT_FACTS
EXTRACT_ISSUES
EXTRACT_CITATIONS
COMPARE_FACTS
COMPARE_CASES
SUMMARIZE_JUDGMENT
ANALYZE_ARGUMENTS
IDENTIFY_ADVERSE_AUTHORITY
DRAFT_RESEARCH_MEMO
DRAFT_ARGUMENT
```

## 16. Model run logging

Persist capability/provider/model/version/prompt version/input hash/latency/tokens/cost/success/output hash without casually logging confidential raw prompts.

## 17. Suggested stack

- Backend: Python, FastAPI, Pydantic, SQLAlchemy, Alembic
- DB: PostgreSQL
- Search: OpenSearch
- Object storage: MinIO locally, S3-compatible interface
- Queue/cache: Redis + Celery/equivalent durable jobs
- Frontend: Next.js + TypeScript + React
- Parsing: Docling + PyMuPDF
- OCR: PP-OCRv5 Greek/English, Tesseract fallback
- Embeddings: Qwen3-Embedding-0.6B baseline
- Reranking: Qwen3-Reranker-0.6B baseline
- LLM: provider abstraction; local OSS where practical, remote fallback where permitted

Models are replaceable. Data structures, workflows, evaluation sets, lawyer feedback, source provenance, and private firm knowledge are the moat.
