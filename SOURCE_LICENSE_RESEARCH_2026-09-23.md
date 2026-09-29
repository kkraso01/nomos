# Source License / Reuse Research — 23 Sep 2026

Verdict per source, based on URL-checked evidence captured this date. **Anything not
marked CONFIRMED requires human legal review before commercial resale in a paid service.**
The product refuses bulk ingestion for the paid service until `commercial_reuse_allowed`
is recorded True in the registry (see `IMPLEMENTATION_LOG.md`).

## CONFIRMED
### Cyprus National Open Data Portal — data.gov.cy
- Evidence URL: https://www.data.gov.cy/en/faq (reachable, text captured)
- License statement (official FAQ, translated): *datasets published on data.gov.cy are
  available under a Creative Commons – Attribution 4.0 International (CC BY 4.0) licence,
  allowing anyone to use, reproduce and modify them without any restriction beyond the
  obligation to attribute the source and to explicitly indicate any differentiation of the
  primary from the secondary material.*
- Verdict: **APPROVED** — CC BY 4.0 is explicit. CC BY permits use/reproduction/modification
  and **does not restrict commercial use**; the conditions are attribution + derivative-marking.
  -> registry: `reuse_status=APPROVED_WITH_ATTRIBUTION`, `adapter_enabled=true`,
     `commercial_reuse_allowed=true`, `licence=CC BY 4.0`.
- Caveat: dataset-specific terms/datasheets must still be preserved (portal says "generally".
  Confirm per-dataset before large-scale use.

## NOT CONFIRMED (stays gated)
### EUR-Lex / CELLAR
- Research page https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html
  is currently bot-gated (HTTP 202, zero bytes) from this network; the official reuse page states
  reuse is free of charge subject to copyright conditions.
- Verdict: reuse for general purposes APPROVED_OPEN, but **commercial resale in a paid service is
  NOT independently confirmed here** -> `commercial_reuse_allowed=false` (blocked for the paid
  service until a human confirms terms). Also note full-text endpoints are bot-gated, so automated
  bulk fetch is not currently possible from this host regardless.

### ECHR / HUDOC
- https://www.echr.coe.int/copyright reachable but the licence body is JS-rendered; static HTML
  yields only navigation. Reuse/automation terms could not be confirmed from the network today.
- Verdict: UNKNOWN -> `adapter_enabled=false`, `commercial_reuse_allowed=false` (blocked).

### Government Gazette (gov.cy) and Supreme Court
- Portal: reachable at https://www.gov.cy/... but document/bulk-reuse terms not confirmed on a
  licence page from the network; Supreme Court returns a JS shell (no text).
- Verdict: UNKNOWN -> blocked.

### CyLaw
- Terms (https://www.cylaw.org/terms.html) prohibit external indexing by robots and
  mass/systematic downloading without prior written consent.
- Verdict: PERMISSION_REQUIRED -> blocked (link/reference only, no bulk ingestion).

## Rule enforced in code
`IngestionService.check_reuse_gate` blocks bulk ingestion in commercial-service mode unless the
source's `commercial_reuse_allowed` is True (an audited human clearance step via
`PUT /sources/registry/{id}/clearance`). No source is ingested for resale on the strength of
"official/public/free" status alone.