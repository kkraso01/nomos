# NOMOS — Product Requirements Document

## 1. Product identity

**Working name:** NOMOS

**Product category:** AI-native legal intelligence, research, litigation-support and law-firm knowledge platform

**Initial jurisdiction:** Republic of Cyprus

**Initial languages:** Greek and English

**Primary customers:** Cyprus law firms and practising lawyers

**Secondary customers:** in-house legal teams, legal researchers, compliance teams, litigation departments

**Long-term direction:** Cyprus first, then EU/ECHR and additional jurisdictions through jurisdiction-specific source/rule modules.

NOMOS is not a generic legal chatbot.

The platform should give lawyers an information and preparation advantage by connecting:

```
```

```
Legislation
+
Case law
+
Procedural rules
+
Citation relationships
+
Historical legislation versions
+
Semantic similarity
+
Exact keyword search
+
Matter evidence
+
Firm-private precedents
+
Legal drafting
```

into one structured legal intelligence system.

---

# 2. Product thesis

Current legal research usually requires lawyers to separately search legislation, cases, older judgments, procedural rules, internal files, pleadings and previous firm work.

NOMOS should make those sources understand each other.

The core concept is:

```
```

```
CLIENT FACT
    ↓
LEGAL ISSUE
    ↓
APPLICABLE LEGISLATION
    ↓
RELEVANT PROVISIONS
    ↓
CASES INTERPRETING THEM
    ↓
FACTUALLY SIMILAR CASES
    ↓
CITATION / TREATMENT GRAPH
    ↓
MATTER EVIDENCE
    ↓
ARGUMENTS
    ↓
DRAFT
```

The real moat should become:

**structured Cyprus legal data + temporal legislation + legal citation graph + high-quality retrieval + lawyer relevance feedback + private firm knowledge.**

The moat is not the underlying LLM.

---

# 3. Product principles

### Evidence before generation

Every important legal proposition must point to the source supporting it.

### Search before reasoning

The model must retrieve relevant legal material before generating an authoritative legal answer.

### Exact law matters

Keyword and citation retrieval must remain first-class.

Embeddings do not replace exact legal search.

### Historical law matters

The platform must know which version of legislation applied at a particular date.

### Structure matters

A statutory Article cannot be treated as an isolated paragraph of text.

The system should understand:

```
```

```
Law
→ Part
→ Chapter
→ Article
→ SubArticle
→ Paragraph
```

### Authority and relevance are different

A highly similar case is not necessarily controlling or authoritative.

### Public law and private firm knowledge remain separate

Global legal corpus:

```
```

```
PUBLIC / SHARED
```

Firm data:

```
```

```
PRIVATE / TENANT-SCOPED
```

### AI assists lawyers

The platform does not automatically make binding legal decisions.

### Never invent authority

No fabricated:

-  judgments; 
-  citations; 
-  case numbers; 
-  statutory provisions; 
-  quotations; 
-  holdings; 
-  deadlines. 

---

# 4. Information states

The system must distinguish four concepts.

```
```

```
SOURCE FACT
```

Something actually contained in legislation, judgment, procedural rule or uploaded evidence.

```
```

```
STRUCTURED EXTRACTION
```

A system-extracted representation of that source.

```
```

```
MODEL INFERENCE
```

For example:

> This judgment appears factually similar.

```
```

```
LAWYER DECISION
```

For example:

> Rely on this authority.

These must never be conflated.

---

# 5. Public legal corpus architecture

The public corpus should eventually contain:

```
```

```
Jurisdiction
LegalSource
Court
Judgment
JudgmentVersion
Legislation
LegislationVersion
LegislationNode
ProceduralRule
Citation
JudgmentLegislationLink
ProvisionCrossReference
LegalConcept
LegalIssue
LegalChunk
SourceDocument
SourceSnapshot
```

Firm-private domain:

```
```

```
Organisation
User
Membership
Matter
MatterMember
Party
MatterDocument
MatterFact
MatterIssue
MatterEvent
MatterEvidence
MatterAuthority
LawyerNote
Argument
ArgumentEvidence
Deadline
Task
Draft
FirmPrecedent
FirmTemplate
```

---

# 6. Source policy

This is a hard architectural requirement.

Every external source must have:

```
```

```
SourceRegistry
```

Fields should include at minimum:

```
```

```
id
name
jurisdiction
source_type

official_source
primary_source

base_url

reuse_status

licence
licence_url

commercial_reuse_allowed
automated_access_allowed
bulk_download_allowed
api_available

attribution_required

terms_checked_at
terms_checked_by
terms_snapshot_hash

adapter_enabled
```

Suggested reuse states:

```
```

```
APPROVED_OPEN
APPROVED_WITH_ATTRIBUTION
APPROVED_API_ONLY
PERMISSION_REQUIRED
RESTRICTED
UNKNOWN
DISABLED
```

Hard rule:

```
```

```
UNKNOWN != permission
```

The ingestion service must refuse bulk ingestion when reuse status is not approved.

---

# 7. Initial legal sources

## Cyprus National Open Data Portal

This is one of the safest sources to build around where relevant datasets exist.

The portal states that datasets are generally made available under **Creative Commons Attribution 4.0 International**, allowing reproduction and modification subject to source attribution and identification of changes. 

Initial status:

```
```

```
official_source = true
reuse_status = APPROVED_WITH_ATTRIBUTION
licence = CC BY 4.0
```

But still store the licence attached to each individual dataset because exceptions may exist.

---

# 8. Cyprus Government Gazette

The Government Gazette is the authoritative publication source for legislative acts.

Gov.cy provides an official Gazette service operated by the Government Printing Office and states that users can search issues and annexes containing legislative acts, tenders, appointments and other official material. 

Use it as a **primary legal authority source**.

However:

```
```

```
authoritative_source != automatically approved for bulk crawling
```

Before automated corpus ingestion, verify:

-  robots/automation rules; 
-  copyright/reuse notice; 
-  open-data status; 
-  permitted bulk access mechanism; 
-  attribution requirements. 

Until then:

```
```

```
reuse_status = UNKNOWN or PERMISSION_REQUIRED
```

depending on the source-specific review.

---

# 9. Cyprus Supreme Court / Judicial Service

The Supreme Court's official site currently publishes decisions across categories and years, including current final decisions. 

This should be treated as a primary source for judgments.

Again, authority does not itself establish permission for unrestricted automated mirroring.

Source adapter should exist, but activation for bulk harvesting requires explicit reuse verification.

---

# 10. CyLaw

CyLaw is valuable as:

-  research reference; 
-  quality benchmark; 
-  cross-check; 
-  link-out source; 
-  structural inspiration. 

But do **not** bulk crawl or mirror CyLaw unless written permission exists.

NOMOS should preferably reconstruct its public corpus from sources we have the right to ingest.

CyLaw may later become:

```
```

```
AUTHORIZED_SECONDARY_SOURCE
```

if permission is obtained.

---

# 11. EUR-Lex

EUR-Lex should become a major approved EU-law source.

Its official webservice is free after registration, and EUR-Lex specifically directs large-volume users toward CELLAR and data-dump services. 

EU public-sector reuse rules also expressly support commercial and non-commercial reuse and machine-readable/open-access mechanisms subject to applicable conditions. 

Use:

```
```

```
EUR-Lex
CELLAR REST API
EUR-Lex Webservice
EUR-Lex Data Dumps
```

Prefer official bulk mechanisms over HTML scraping.

---

# 12. HUDOC

HUDOC is the official European Court of Human Rights case-law database.

It contains judgments, decisions, communicated cases, advisory opinions and legal summaries. 

HUDOC also supports result export and RSS-based monitoring. 

However, the agent must verify the exact reuse/licensing and automated-access conditions before building unrestricted bulk harvesting.

Until verified:

```
```

```
source = official
authority = primary
bulk_reuse_status = UNVERIFIED
```

Do not infer reuse permission merely from public accessibility.

---

# 13. Source ingestion architecture

Source adapters perform:

```
```

```
discover()
fetch()
normalize()
```

Adapters do **not** own canonical persistence.

Central service:

```
```

```
IngestionService
```

handles:

```
```

```
deduplication
raw persistence
normalization
versioning
hashing
provenance
licence enforcement
canonical mapping
```

Pipeline:

```
```

```
DISCOVER
↓
FETCH
↓
RAW
↓
NORMALIZED
↓
ENRICHED
↓
INDEXED
↓
DERIVED
```

RAW is immutable.

---

# 14. Raw source preservation

For every acquired source object preserve:

```
```

```
source_id
source_record_id
source_url
source_identifier

observed_at
published_at
effective_at

content_hash

http_metadata
raw_payload
raw_object_storage_path

mime_type
encoding
language

adapter_version
normalizer_version

licence
licence_snapshot

ingestion_run_id
```

Never overwrite original source material.

---

# 15. Legislation model

Core:

```
```

```
Legislation
LegislationVersion
LegislationNode
LegislationAmendment
ProvisionCrossReference
```

Hierarchy:

```
```

```
LAW
 └─ PART
     └─ CHAPTER
         └─ ARTICLE
             └─ SUBARTICLE
                 └─ PARAGRAPH
```

Each node:

```
```

```
node_id
legislation_id
version_id
parent_id

node_type
label
number
title

original_text
normalized_text
language

effective_from
effective_to

source_document_id
source_locator

sort_order
```

---

# 16. Temporal legislation

This is mandatory.

Do not simply overwrite Article text when law changes.

Represent:

```
```

```
Version 1
effective_from = 2015-01-01
effective_to   = 2018-06-20

Version 2
effective_from = 2018-06-21
effective_to   = 2023-02-03

Version 3
effective_from = 2023-02-04
effective_to   = null
```

Then:

> What law applied on 14 April 2019?

resolves to Version 2.

---

# 17. Amendments

Model:

```
```

```
AmendingAct
AmendmentOperation
```

Operations may include:

```
```

```
INSERT
DELETE
REPLACE
RENUMBER
REPEAL
COMMENCE
```

Store:

```
```

```
affected_node
previous_text
new_text
effective_date
source
```

Do not ask an LLM to reconstruct legislation history when deterministic amendment data is available.

---

# 18. Judgment model

Store:

```
```

```
Judgment
JudgmentVersion
```

Fields:

```
```

```
case_name
case_number
ECLI
court
division
judges

decision_date
publication_date

language

original_text

source_document
source_url
source_hash
```

AI/deterministic enrichment can produce:

```
```

```
facts
legal_issues
procedural_history
parties
arguments
legal_principles
reasoning
holding
remedy/order
legislation_references
case_references
```

Derived material always links back to source evidence.

---

# 19. Judgment segmentation

Do not chunk a judgment every 500 tokens.

Use legal structure:

```
```

```
metadata
paragraph
facts
procedural_history
issue
party_argument
legal_analysis
holding
order
separate_opinion
```

Retain paragraph-level chunks even when larger semantic sections exist.

---

# 20. Citation graph

Explicit relationships:

```
```

```
CASE --CITES--> CASE

CASE --INTERPRETS--> PROVISION

CASE --APPLIES--> PROVISION

CASE --DISCUSSES--> PROVISION

PROVISION --REFERENCES--> PROVISION
```

AI-reviewable relationships:

```
```

```
CASE --FOLLOWS--> CASE
CASE --DISTINGUISHES--> CASE
CASE --APPROVES--> CASE
CASE --CRITICISES--> CASE
CASE --OVERRULES--> CASE
```

Only assert these where evidence supports them.

---

# 21. Search is the heart of the product

Do not build NOMOS as:

```
```

```
documents
→ embeddings
→ chatbot
```

Build:

```
```

```
QUERY
↓
QUERY UNDERSTANDING
↓
MULTI-RETRIEVAL
↓
FUSION
↓
RERANKING
↓
LEGAL STRUCTURE ENRICHMENT
↓
RESULT EXPLANATION
```

---

# 22. Query understanding

Extract deterministically or with lightweight NLP:

```
```

```
language
case citation
case number
ECLI

law
chapter
article
subarticle

date/time constraint

court
practice area

legal concepts
fact pattern
procedural posture
```

---

# 23. Exact/legal-reference parser

Implement deterministic parsers for common Cyprus legal forms.

Examples:

```
```

```
ΚΕΦ. 6
Κεφ. 148

Ν. 123(I)/2020

άρθρο 15
Άρθρο 15(2)
Άρθρο 15(2)(α)

Πολ. Εφ.
Ποιν. Έφ.

ECLI
case numbers
dates
```

This is L0 deterministic work.

---

# 24. Lexical search

Use BM25.

Support:

```
```

```
exact phrase
AND
OR
NOT

field query

proximity

Greek normalization

case number

ECLI

legislation number

Article number

judge

court

date range
```

Never remove lexical search because semantic search appears better.

Legal practice often depends on precise wording.

---

# 25. Semantic search

Semantic retrieval must operate over legally meaningful chunks.

Recommended initial embedding candidate:

```
```

```
Qwen3-Embedding-0.6B
```

Benchmark against alternatives rather than treating it as permanent.

Candidate alternatives:

```
```

```
BGE-M3
multilingual-e5 family
other multilingual legal-domain models
```

Selection must be based on Cyprus-law retrieval evaluation.

---

# 26. Cross-language retrieval

Required:

```
```

```
Greek query → Greek judgment
Greek query → English judgment

English query → English judgment
English query → Greek judgment
```

Original source language always retained.

Do not replace Greek text with translated English.

Store:

```
```

```
original_text
normalized_text
optional_translation
translation_provider
translation_version
```

---

# 27. Hybrid retrieval

Initial candidate retrieval:

```
```

```
BM25 top N
+
dense semantic top N
+
exact-reference results
+
legislation-tree expansion
+
citation graph expansion
```

Deduplicate.

Then fuse using:

```
```

```
RRF
or
validated weighted rank fusion
```

Do not arbitrarily sum incomparable raw scores.

---

# 28. Reranking

Top candidates pass through a reranker.

Initial candidate:

```
```

```
Qwen3-Reranker-0.6B
```

Keep replaceable.

The reranker should evaluate query-document relevance.

Legal-domain features can then modify/explain ranking:

```
```

```
same provision
same court level
same procedural posture
relevant date
citation relationship
exact authority
```

---

# 29. Different kinds of similarity

Never reduce legal similarity to one vector score.

Store or compute:

```
```

```
LEGAL_ISSUE_SIMILARITY
FACTUAL_SIMILARITY
PROCEDURAL_SIMILARITY
STATUTORY_SIMILARITY
REMEDY_SIMILARITY
```

Example:

```
```

```
Legal issue        92%
Facts              81%
Procedure          39%
Same provision     yes
```

Scores should be accompanied by an explanation.

---

# 30. Authority metadata

Search result should expose:

```
```

```
court
court level
date
case number
ECLI

statutes involved

citations

later treatment

procedural context
```

Do not generate an opaque “authority score” and pretend it determines legal force.

---

# 31. Legislation-aware retrieval

Querying one Article may expand to:

```
```

```
target Article
parent Part/Chapter
definitions
referenced Articles
Articles referencing target
relevant amendments
applicable historic version
subsidiary regulations
cases interpreting provision
cases applying provision
```

Graph expansion is deterministic where possible.

---

# 32. Search explanation

Every result should explain why it appeared.

Example:

```
```

```
WHY THIS RESULT?

• exact match to Article 15(2)
• fact pattern similar to current matter
• Supreme Court decision
• cites Case X
• decided under the same version of the legislation
```

---

# 33. Search modes

UI:

### Hybrid

Default.

### Exact

Keyword/citation focus.

### Semantic

Natural-language similarity.

### Advanced

Detailed filters.

---

# 34. Filters

Support:

```
```

```
court
court level

date range

case type

legislation
Article

judge

case number
ECLI

language

procedural stage

legal issue

cites case
cited by case

legislation version
```

---

# 35. Matter workspace

A matter represents a firm's private legal file.

Fields:

```
```

```
matter_id
organisation_id

matter_number
title

client

matter_type

court
jurisdiction

status

opened_at
closed_at

assigned_users

confidentiality_level
```

---

# 36. Matter documents

Supported:

```
```

```
PDF
scanned PDF
DOCX
email
HTML
plain text
images
```

Possible later:

```
```

```
audio transcription
```

Pipeline:

```
```

```
upload
→ immutable storage
→ hash
→ detect type
→ parse
→ OCR if required
→ classify
→ segment
→ extract metadata
→ index privately
```

---

# 37. OCR

Greek and English are mandatory.

Suggested candidate:

```
```

```
PP-OCRv5 Greek/English
```

Keep OCR behind capability abstraction.

Possible fallback:

```
```

```
Tesseract eng+ell
```

---

# 38. Document parsing

Suggested:

```
```

```
Docling
PyMuPDF
```

Use deterministic parsers first.

Do not ask an LLM to infer text/layout if parsers can extract it reliably.

---

# 39. Matter facts

AI can propose:

```
```

```
MatterFact
```

Example:

```
```

```
fact:
Employee was terminated 27 February 2024

evidence:
Termination letter, page 1

confidence:
0.99

status:
ACCEPTED
```

Another:

```
```

```
fact:
Employer orally ordered relocation

evidence:
Witness statement ¶12

confidence:
0.71

status:
REVIEW_REQUIRED
```

---

# 40. Matter chronology

Create:

```
```

```
MatterEvent
```

Fields:

```
```

```
date
time
event_type
description
source
evidence
confidence
review_status
```

Timeline UI:

```
```

```
3 June 2018 — employment begins
14 February 2024 — relocation instruction
19 February — employee objects
27 February — termination
4 March — letter before action
```

---

# 41. Issue spotting

System may propose:

```
```

```
MatterIssue
```

Examples:

```
```

```
limitation
breach of contract
termination
redundancy
negligence
procedural jurisdiction
```

State:

```
```

```
SUGGESTED
ACCEPTED
REJECTED
```

Accepted issues become research inputs.

---

# 42. Matter authority workspace

For each matter:

```
```

```
RELIED_ON
POTENTIALLY_USEFUL
ADVERSE
DISTINGUISHABLE
REJECTED
```

Store:

```
```

```
matter
authority
issue

relevant_paragraphs

lawyer_note

distinction

supporting_proposition
```

---

# 43. Contrary authorities

The system should intentionally search for:

```
```

```
supporting authority
contrary authority
distinguishable authority
```

Do not optimize only for arguments favorable to the user's client.

---

# 44. Argument graph

Structure:

```
```

```
ISSUE
│
├─ POSITION A
│  ├─ Proposition
│  │  ├─ Authority
│  │  └─ Evidence
│
└─ POSITION B
   ├─ Proposition
   │  ├─ Authority
   │  └─ Evidence
```

The lawyer controls final classification.

---

# 45. Legal research assistant

User may ask:

> Which Cyprus Supreme Court judgments discuss this Article?

> Find factually similar cases.

> Show cases distinguishing Case X.

> What law applied on 12 May 2018?

> What authority is adverse to our position?

> What facts distinguish our matter from Case Y?

The answer pipeline:

```
```

```
query
↓
retrieve
↓
rerank
↓
source validation
↓
reason
↓
cite
```

No evidence:

```
```

```
"No sufficiently supported authority was found."
```

Not invented text.

---

# 46. Citation validation

Generated citations must be validated against canonical database records.

Before displaying:

```
```

```
case_exists?
provision_exists?
source_span_exists?
```

If not:

```
```

```
reject citation
```

---

# 47. Quotation validation

The LLM cannot produce authoritative quotations from memory.

Quotes must be retrieved as exact source spans.

Store:

```
```

```
document_id
paragraph
char_start
char_end
text_hash
```

---

# 48. Firm knowledge base

Each organisation can privately index:

```
```

```
previous matters
pleadings
opinions
research memos
templates
letters
internal precedents
work product
```

Retrieval should distinguish:

```
```

```
PUBLIC LEGAL AUTHORITY
```

from:

```
```

```
INTERNAL FIRM MATERIAL
```

Never show internal work as if it were primary law.

---

# 49. Private precedent search

Example:

> Find previous firm cases with similar factual patterns.

> Show pleadings we previously used for limitation arguments.

> Find internal opinions discussing Article X.

> What authorities did we rely on in similar matters?

This becomes a major firm-specific moat.

---

# 50. Drafting

Support:

```
```

```
research memorandum
case summary
chronology
legal letter
argument outline
pleading section
opinion outline
submission draft
```

Inputs:

```
```

```
accepted matter facts
accepted issues
selected authorities
verified legislation
firm template
lawyer instructions
```

Not:

```
```

```
single prompt → unrestricted legal document
```

---

# 51. Procedural rule engine

Procedural deadlines should be deterministic whenever possible.

Model:

```
```

```
ProceduralRule
```

Fields:

```
```

```
jurisdiction
court
procedure_type

trigger_event

duration
duration_unit

business_day_rules
weekend_rules
holiday_rules

effective_from
effective_to

source_provision
```

The LLM may detect the trigger.

Code calculates the deadline.

---

# 52. Deadline uncertainty

If the necessary triggering date or applicable rule is uncertain:

```
```

```
REVIEW_REQUIRED
```

Do not guess.

---

# 53. Notifications

Users can follow:

```
```

```
law
Article
case
practice area
legal issue
```

New source ingest may trigger:

```
```

```
new judgment
new amendment
new case citing saved authority
law version changed
```

---

# 54. Public corpus vs private data

Global:

```
```

```
judgments
legislation
procedural rules
citations
public metadata
```

Private:

```
```

```
matters
client documents
firm precedents
notes
drafts
user annotations
```

Private content must never leak into global search.

---

# 55. Multi-tenancy

Every private row requires:

```
```

```
organisation_id
```

Matter-sensitive resources also require:

```
```

```
matter_id
```

Deny by default.

Do not rely only on frontend filtering.

Authorization enforced server-side.

---

# 56. Ethical walls

Architecture should allow later:

```
```

```
matter-specific user ACLs
matter teams
restricted matters
ethical walls
```

Do not need full conflict-management product initially, but domain should allow restricted access.

---

# 57. Evidence model

Create reusable:

```
```

```
Evidence
```

Evidence may point to:

```
```

```
source document
page
paragraph
bounding box
character span
legislation node
judgment paragraph
matter document
```

All inferred facts should support:

**Show evidence**

---

# 58. Confidence model

Do not overload one number.

Possible:

```
```

```
ocr_confidence
extraction_confidence
retrieval_score
reranker_score
semantic_similarity
evidence_quality
normalization_confidence
```

A 0.98 OCR score is not a 98% legal conclusion.

---

# 59. AI architecture

Four layers:

```
```

```
L0 deterministic
L1 local ML
L2 local open-source LLM
L3 remote model
```

Use lowest capable layer.

Examples:

| CapabilityLevel                 |          |
| ------------------------------- | -------- |
| case-number parsing             | L0       |
| legislation references          | L0 first |
| date arithmetic                 | L0       |
| citation graph lookup           | L0       |
| BM25                            | L0       |
| embeddings                      | L1       |
| reranking                       | L1       |
| OCR                             | L1       |
| document classification         | L1/L2    |
| fact extraction                 | L2       |
| issue extraction                | L2       |
| case comparison explanation     | L2       |
| complex cross-document analysis | L2/L3    |
| drafting                        | L2/L3    |

---

# 60. AI Router

Business modules request capabilities, never providers.

Example capabilities:

```
```

```
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

AI Router decides provider/model.

---

# 61. AI call logging

Persist:

```
```

```
capability
provider
model
model_version

prompt_template
prompt_version

inputs_hash

latency

input_tokens
output_tokens

cost

success/failure

output_hash
```

For sensitive firm data, logs must not casually persist entire prompts.

---

# 62. Remote AI privacy

Never send private firm/client data to a remote provider unless:

```
```

```
organisation policy permits it
AND
provider policy permits intended use
```

Support organisation configuration:

```
```

```
REMOTE_AI_DISABLED
PUBLIC_ONLY
PRIVATE_ALLOWED
```

---

# 63. Suggested core stack

Backend:

```
```

```
Python
FastAPI
Pydantic
SQLAlchemy
Alembic
```

Authoritative DB:

```
```

```
PostgreSQL
```

Search:

```
```

```
OpenSearch
```

Object storage:

```
```

```
MinIO locally
S3-compatible abstraction
```

Jobs:

```
```

```
Redis
Celery / equivalent durable worker architecture
```

Frontend:

```
```

```
Next.js
TypeScript
React
```

Parsing:

```
```

```
Docling
PyMuPDF
```

OCR:

```
```

```
PP-OCRv5
Tesseract fallback
```

Embeddings:

```
```

```
Qwen3-Embedding-0.6B baseline
```

Reranker:

```
```

```
Qwen3-Reranker-0.6B baseline
```

Models stay replaceable.

---

# 64. OpenSearch indexes

Suggested:

```
```

```
public_judgments
public_legislation
public_legal_chunks
```

Private:

either per-tenant index strategy or secure shared index with enforced tenant filtering.

Example fields:

```
```

```
document_id
document_type

title
text

language

court
decision_date

law_id
article

embedding

metadata
```

---

# 65. PostgreSQL remains source of truth

OpenSearch is a projection.

If index disappears:

```
```

```
PostgreSQL + raw source
→ rebuild index
```

Do not keep essential canonical state only in search engine.

---

# 66. Knowledge graph

Initially use relational graph representation.

Tables:

```
```

```
case_citations
case_legislation_links
provision_cross_references
matter_authorities
argument_links
```

No Neo4j required initially.

Add specialized graph DB only after actual need.

---

# 67. Frontend

Core navigation:

```
```

```
Research
Case Law
Legislation
Matters
Firm Knowledge
Updates
Admin
```

Matter:

```
```

```
Overview
Documents
Facts
Issues
Chronology
Evidence
Authorities
Arguments
Deadlines
Drafts
Activity
```

---

# 68. Research result page

Each result:

```
```

```
case title
court
date

relevant excerpt

legal issue similarity
fact similarity

legislation involved

why result matched

source link
```

Actions:

```
```

```
Open case
Compare with matter
Save authority
View citing cases
View legislation
```

---

# 69. Judgment view

Tabs:

```
```

```
Source
Summary
Facts
Issues
Reasoning
Holding
Legislation
Cited Cases
Citing Cases
Similar Cases
```

Generated vs source material must be visually distinct.

---

# 70. Legislation view

Left:

```
```

```
hierarchical tree
```

Main:

```
```

```
Article text
```

Side panel:

```
```

```
effective dates
amendments
historic versions
definitions
cross-references
cases interpreting
cases applying
```

This should become a signature screen.

---

# 71. Research quality benchmark

Create a Cyprus-specific labelled dataset.

A query entry:

```
```

```
{
  "query": "...",
  "language": "el",
  "highly_relevant_cases": [],
  "relevant_cases": [],
  "relevant_provisions": [],
  "hard_negatives": []
}
```

Lawyers eventually label relevance.

---

# 72. Retrieval metrics

Track:

```
```

```
Recall@10
Recall@50
MRR
nDCG@10
Precision@10
```

Separate benchmarks:

```
```

```
Greek query
English query
cross-language query
citation query
Article query
fact-pattern query
procedural query
```

---

# 73. Case-comparison benchmark

Store:

```
```

```
Case A
Case B

same_issue
fact_similarity 1–5
procedure_similarity 1–5
same_provision
```

Compare embedding/reranker/LLM performance.

---

# 74. User feedback loop

Lawyer actions create retrieval-quality feedback:

```
```

```
result opened
authority saved
authority rejected
marked adverse
marked irrelevant
cited in draft
```

Do not immediately retrain models from every click.

Aggregate and curate.

---

# 75. Source quality

Each authority should expose:

```
```

```
source
source type
official status
last synchronized
hash
```

Preferred order:

```
```

```
official primary
approved official repository
licensed source
secondary source
```

---

# 76. Hallucination policy

Hard requirements:

```
```

```
NO_SOURCE_NO_LEGAL_CLAIM
```

Before emitting a judgment citation:

```
```

```
validate judgment ID
```

Before emitting statute:

```
```

```
validate legislation node
```

Before quoting:

```
```

```
validate exact span
```

---

# 77. Draft disclaimer semantics

AI-generated work should visibly say:

```
```

```
Draft / lawyer review required
```

Do not imply generated research replaces professional review.

---

# 78. Audit log

Append-only audit events:

```
```

```
actor
organisation
matter

action

resource
before_hash
after_hash

timestamp
correlation_id
```

Relevant actions:

```
```

```
document upload
AI analysis
fact accepted
issue rejected
authority saved
draft generated
deadline
```
---

# 79. Subscription and entitlement architecture

Do not hard-code pricing into domain logic.

Entitlements should include, at minimum:

```text
PUBLIC_RESEARCH
HYBRID_SEARCH
CASE_SIMILARITY
TEMPORAL_LEGISLATION
CITATION_GRAPH
MATTER_WORKSPACE
PRIVATE_FIRM_SEARCH
LEGAL_ASSISTANT
ARGUMENT_BUILDER
DRAFTING
LEGAL_MONITORING
API_ACCESS
PRIVATE_DEPLOYMENT
```

Meterable usage can include:

```text
seats
active_matters
private_storage
ocr_pages
embedding_jobs
advanced_research_runs
remote_ai_tokens
```

Possible commercial packages may later include Solo, Firm, Professional, Enterprise, and Private/On-Prem. Pricing is a commercial decision and is not part of initial implementation.

---

# 80. Product non-goals

NOMOS is not initially:

- a court e-filing system;
- a replacement for lawyers;
- a fully autonomous legal advice service;
- a billing/accounting practice-management suite;
- a client-facing consumer advice chatbot;
- a source of fabricated outcome probabilities;
- a system that silently trains on client confidential data;
- a mirror of restricted third-party legal databases.

The product may integrate with practice-management/document-management systems later through adapters.

---

# 81. Core user journeys

## Research-only journey

```text
lawyer enters query
→ system parses exact references, language, dates and legal concepts
→ BM25 + semantic + exact-reference + graph/tree retrieval
→ candidate fusion
→ reranking
→ temporal/authority metadata
→ source-backed results
→ lawyer opens judgment/provision
→ saves authority or refines query
```

## Matter journey

```text
create matter
→ upload pleadings/evidence/contracts/correspondence
→ immutable storage + parsing/OCR
→ propose facts/events/issues
→ lawyer reviews
→ accepted facts/issues drive research
→ authorities linked to matter
→ supporting and adverse positions built
→ chronology/deadlines generated
→ lawyer-approved evidence and authorities feed drafting
```

## Legislation journey

```text
open law
→ navigate hierarchy
→ select date
→ resolve applicable version
→ inspect amendment timeline
→ see cross-references
→ see cases applying/interpreting provision
→ compare historical/current text
```

---

# 82. Functional completion standard

A feature is not complete merely because a model, endpoint, schema, placeholder service, or mock test exists.

A feature is functionally complete when the intended workflow executes against the real local development stack with representative test data and produces a correct, traceable result.

Examples:

### Search

```text
Greek legal query
→ lexical results
→ semantic results
→ exact-reference results where applicable
→ candidate fusion
→ reranking
→ filters honored
→ source metadata shown
→ result explanation shown
```

### Legal assistant

```text
matter question
→ public-law retrieval
→ private matter evidence retrieval
→ validated sources
→ grounded synthesis
→ every authoritative proposition has a source
→ fabricated citation rejected
```

### Temporal legislation

```text
query + historical date
→ applicable legislation version resolved
→ exact source shown
→ later amendment clearly distinguished
```

### Matter extraction

```text
upload document
→ immutable object stored
→ parsed/OCR text stored
→ proposed fact/event linked to exact evidence
→ review state created
→ accepted item becomes matter knowledge
```

---

# 83. Functional verification vs performance validation

During product implementation, functional correctness takes priority.

Allowed and encouraged for functional verification:

- Docker Compose for NOMOS services;
- PostgreSQL migrations and real integration tests;
- OpenSearch indexing and retrieval checks;
- Redis/background-job checks;
- MinIO/S3 object-storage checks;
- frontend ↔ API ↔ DB ↔ worker integration;
- small representative OCR/document/legal fixtures;
- targeted remote AI provider smoke tests using public or synthetic text.

Deferred unless specifically requested:

- sustained load/stress tests;
- large concurrency benchmarks;
- long soak tests;
- production penetration testing;
- chaos testing;
- cloud/Pi parity benchmarking;
- sustained Raspberry Pi thermal/OCR throughput benchmarking;
- production deployment.

Obvious correctness/safety defects such as runaway memory, unbounded loops, data loss, broken tenancy, disk-filling behavior, or deadlocks must still be fixed when discovered.

---

# 84. Data retention and provenance

Public source material must retain provenance and source snapshots. Private matter data must support organisation-level retention policy and later legal-hold capabilities.

For generated/derived artifacts retain:

```text
input hashes
source IDs
source versions
pipeline version
model run ID where applicable
created_at
supersedes / superseded_by
review status
```

Never silently overwrite accepted lawyer work or canonical source snapshots.

---

# 85. Security and confidentiality baseline

Required from the beginning:

- organisation-scoped authorization;
- server-side matter access checks;
- secure password/session handling;
- encrypted transport;
- secret management outside source control;
- signed object access rather than public private-file URLs;
- audit logging for material access and decisions;
- remote-AI policy controls;
- log redaction for confidential content;
- least-privilege service credentials;
- deterministic tenant filters for private search.

Private matter content must never appear in another tenant's search results.

---

# 86. Privacy and remote-model policy

Organisation policy must determine whether remote AI may receive:

```text
PUBLIC_ONLY
PRIVATE_ALLOWED
REMOTE_AI_DISABLED
```

Default new organisations conservatively unless product requirements explicitly choose otherwise.

A model provider's technical availability does not establish that confidential legal documents may be sent to it. Provider terms, data-retention settings, organisation policy, and contractual requirements must be satisfied.

---

# 87. Human approval boundaries

Lawyer approval is required before treating the following as adopted work product:

- legal issue classification;
- reliance on an authority;
- adverse-authority treatment;
- final chronology where disputed dates exist;
- procedural deadline where trigger/applicable rule is uncertain;
- argument characterization;
- legal memorandum/submission/pleading draft;
- any client-facing legal conclusion.

AI output may be useful without being approved, but it must stay visibly differentiated from source fact and lawyer decision.

---

# 88. Explainability standard

A lawyer should be able to ask:

> Why did NOMOS show this result or make this suggestion?

The system should be able to answer through data, not a post-hoc invented explanation.

Possible reasons include:

```text
exact phrase match
exact Article match
same legislation version
semantic issue similarity
factual similarity
procedural similarity
citation relationship
same court / court level
saved matter issue
private precedent relationship
```

---

# 89. Quality strategy

Quality is measured separately for:

- source ingestion accuracy;
- metadata normalization;
- OCR;
- legal-reference extraction;
- lexical retrieval;
- semantic retrieval;
- reranking;
- temporal version resolution;
- case-to-provision linking;
- fact extraction;
- issue extraction;
- citation validation;
- grounded generation.

Do not collapse product quality into one AI benchmark.

---

# 90. Initial development phases

Implementation should proceed dependency-first:

```text
A Platform foundation
B Source registry + public legal corpus
C Search and retrieval
D Legal graph + temporal legislation
E Legal intelligence enrichment
F Matter workspace + private corpus
G Research assistant + argument support
H Firm knowledge
I Procedure + drafting + monitoring
J SaaS hardening
```

Detailed acceptance criteria are defined in `IMPLEMENTATION_PLAN.md`.

---

# 91. North-star product workflow

```text
Lawyer creates a matter
↓
uploads documents
↓
NOMOS extracts proposed chronology, facts and issues with evidence
↓
lawyer reviews important items
↓
NOMOS runs hybrid search against approved public sources
↓
legislation tree + historical versions + citation graph enrich results
↓
reranker prioritizes relevant cases/provisions
↓
system explains similarities, distinctions and adverse material
↓
lawyer selects authorities
↓
argument graph connects propositions, authorities and matter evidence
↓
procedural engine calculates supported deadlines deterministically
↓
drafting engine prepares source-grounded work product
↓
lawyer reviews and edits
↓
firm-private knowledge improves future research without contaminating the public corpus
```

That is the target product. NOMOS must not be reduced to a generic RAG chatbot.
