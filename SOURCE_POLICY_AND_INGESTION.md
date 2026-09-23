# NOMOS — Source Policy and Legal Ingestion Plan

**Purpose:** prevent the product from confusing "publicly visible" with "approved for commercial bulk ingestion" while prioritizing trustworthy primary legal sources.

**Important:** this file is an engineering/product policy, not legal advice. Reuse terms must be re-checked before production activation, especially because website terms can change.

## 1. Mandatory source registry

Every external source must have a `SourceRegistry` record containing at least:

```text
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
notes
```

Allowed reuse states:

```text
APPROVED_OPEN
APPROVED_WITH_ATTRIBUTION
APPROVED_API_ONLY
PERMISSION_REQUIRED
RESTRICTED
UNKNOWN
DISABLED
```

Hard gate:

```text
UNKNOWN != permission
```

`IngestionService` must refuse bulk/systematic ingestion unless the source/dataset is in an approved state compatible with the attempted acquisition mechanism.

## 2. Current source matrix (checked 23 Sep 2026)

| Source | Authority value | What it gives NOMOS | Current engineering reuse position | Adapter priority |
|---|---|---|---|---|
| Cyprus National Open Data Portal (`data.gov.cy`) | Official | Reusable public-sector datasets when relevant | Portal FAQ says datasets are generally CC BY 4.0, allowing reproduction/modification with attribution and identification of changes. Still preserve dataset-specific licence because exceptions may exist. | P0 where legal datasets exist |
| Cyprus Government Gazette (`gov.cy`, Government Printing Office) | Primary/official | Legislative acts and official Gazette issues/annexes | Official authoritative source. Bulk crawling/republication permission is **not assumed** from public access. Verify source-specific automation/reuse mechanism before enabling bulk ingestion. | P0 schema/adapter; acquisition gated |
| Cyprus Supreme Court / Judicial Service (`supremecourt.gov.cy`) | Primary/official | Official decisions | Official decisions are published, but unrestricted bulk mirroring/automated harvesting is **not assumed**. Verify terms/robots/approved access before enabling bulk acquisition. | P0 schema/adapter; acquisition gated |
| CyLaw (`cylaw.org`) | High-value secondary/reference | Case law, legislation organization, cross-check/reference | **Do not bulk crawl/index/mirror without prior written consent.** CyLaw terms prohibit external indexing by web robots and mass/systematic downloading, and tell other publishers/services to obtain texts from original sources or other approved methods. | Link/reference only unless permission obtained |
| EUR-Lex / CELLAR | Official EU primary repository | EU law, metadata, relationships, Official Journal content | EUR-Lex explicitly permits reuse free of charge subject to copyright conditions and provides webservice, data dumps, CELLAR REST/SPARQL and machine-readable formats. Prefer official mass-data mechanisms over HTML scraping. | P0 |
| HUDOC / ECHR | Official ECHR primary case-law database | ECtHR judgments, decisions, communicated cases, legal summaries, etc. | Official and searchable/exportable, but this package does **not** claim unrestricted commercial bulk reuse has been established. Verify exact reuse/automation conditions before bulk acquisition. | P1 schema/adapter; acquisition gated until verified |

## 3. Verified source notes

### Cyprus National Open Data Portal

Current official FAQ states datasets are generally available under **CC BY 4.0**, permitting reproduction and modification subject to attribution and clear identification of changes.

Engineering implications:

- capture licence per dataset, not only portal default;
- store attribution requirements;
- store dataset URL and version/retrieval timestamp;
- preserve raw downloaded representation;
- label derived/normalized data as modified where required.

### Cyprus Government Gazette

Gov.cy identifies the Government Gazette service as operated by the **Government Printing Office** and allows users to search issues/annexes containing legislative acts and other official material.

Engineering implications:

- model it as a primary legal authority source;
- build adapter interfaces and parsing logic;
- do not activate systematic harvesting until allowed acquisition method is verified;
- if official bulk/API/download mechanisms become available, use them instead of scraping presentation HTML.

### Cyprus Supreme Court / Judicial Service

The official Supreme Court website publishes current final decisions by categories/years.

Engineering implications:

- source is authoritative for published decisions;
- build decision metadata/parser fixtures from manually/publicly accessible examples as permitted;
- activation of systematic harvesting remains gated pending source-specific terms/automation review;
- preserve pseudonymization/anonymization as published; do not reverse it.

### CyLaw

CyLaw is a non-profit legal information service and an important research reference. Its current terms state that it is not intended as a database source for other publishers/services and identify prohibited uses without prior written consent, including:

- external indexing of files/documents by web robots;
- mass/systematic downloading, including automated processing;
- certain forms of embedding/reuse that obscure or confuse source provenance.

Therefore:

```text
reuse_status = PERMISSION_REQUIRED
adapter_enabled_for_bulk = false
```

Allowed product posture without permission:

- user-visible link-outs where appropriate;
- manual research/reference;
- quality cross-checking that does not violate access restrictions;
- source metadata maintained without bulk mirroring;
- request written permission if CyLaw ingestion would materially improve coverage.

### EUR-Lex / CELLAR

EUR-Lex states data can be reused free of charge subject to copyright conditions and provides:

- EUR-Lex webservice;
- official data dumps;
- CELLAR REST access;
- CELLAR SPARQL;
- structured/machine-readable formats.

For large volumes, use the documented mass-data services rather than HTML crawling.

Suggested initial ingestion:

- Cyprus-relevant EU legislation;
- cited EU instruments in Cyprus matters;
- metadata/citation relationships;
- historical versions where official metadata permits.

### HUDOC

HUDOC is the official ECHR case-law database and provides judgments, decisions, communicated cases, advisory opinions, and legal summaries.

Do not infer a blanket commercial bulk-reuse permission solely from public availability/export functionality. Verify terms before bulk acquisition.

## 4. Source adapter contract

Adapters perform acquisition-specific work only:

```python
class SourceAdapter:
    def discover(self, cursor): ...
    def fetch(self, source_key): ...
    def normalize(self, raw_record): ...
```

Adapters must not directly implement canonical domain persistence.

Central `IngestionService` owns:

```text
licence/reuse gate
deduplication
raw persistence
hashing
canonical identity
versioning
normalization persistence
provenance
index scheduling
error quarantine
```

## 5. Immutable ingestion stages

```text
DISCOVER
→ FETCH
→ RAW
→ NORMALIZED
→ ENRICHED
→ INDEXED
→ DERIVED
```

`RAW` is immutable.

Every acquired object stores:

```text
source_id
source_record_id
source_url
source_identifier
observed_at
published_at
effective_at
content_hash
http_metadata
raw_payload or raw_object_storage_path
mime_type
encoding
language
adapter_version
normalizer_version
licence_snapshot
ingestion_run_id
```

## 6. Trust hierarchy

Prefer, where available and legally reusable:

```text
official primary source
→ approved official repository
→ licensed/authorized source
→ secondary reference source
```

Do not rank a source as legally controlling merely because it has better formatting or search.

## 7. Acquisition safety

The agent must never:

- bypass CAPTCHA/access controls;
- evade robots/technical restrictions;
- rotate identities to defeat rate limits;
- crawl a source marked `UNKNOWN`, `RESTRICTED`, or `PERMISSION_REQUIRED` in bulk;
- remove provenance/attribution;
- republish source editorial enhancements as NOMOS-authored material;
- infer that an official source is automatically open for unrestricted commercial mirroring.

## 8. Development without live bulk access

If a source adapter is legally gated, development should continue using:

- synthetic fixtures;
- manually collected permitted samples;
- official openly licensed datasets;
- adapter contract tests;
- recorded response fixtures where lawful;
- mock discovery/fetch responses.

A live-source permission blocker should not stop unrelated feature development.

## 9. Re-verification process

Before enabling a source in production:

1. Re-open current terms/licence pages.
2. Record date and reviewer.
3. Store a terms/licence snapshot or hash/reference.
4. Confirm commercial reuse.
5. Confirm automated access mechanism.
6. Confirm bulk-download/indexing rights.
7. Confirm attribution obligations.
8. Confirm privacy/anonymization conditions.
9. Enable only the permitted adapter mode.
10. Re-check periodically and when source behavior/terms change.
