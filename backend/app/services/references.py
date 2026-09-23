"""L0 exact legal-reference parser for Cyprus/EU forms.

Deterministic. When a query fully matches a canonical legal reference (exact
Article/law, ECLI, case number) the search pipeline must bypass fuzzy
ambiguity and return the exact object.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime

# Case numbers: civil case e.g. 1234/2018, ECLI:CY:AD:2019:A123, 1/2015


@dataclass
class ParsedReference:
    kind: str            # legislation_article | legislation | judgment | unknown
    law: str | None = None
    article: str | None = None
    article_number: str | None = None
    law_number: str | None = None
    law_year: str | None = None
    case_number: str | None = None
    ecli: str | None = None
    court: str | None = None
    raw: str = ""
    confidence: float = 0.0


_ARTICLE_LAW_RE = re.compile(
    r"(?:Article|άρθρο)\s+([0-9IVXL]+(?:[A-Z])?)\s+"
    r"(?:of|του)\s+(?:the\s+)?(?:Law\s+|Νόμο?ü?\s+)?([0-9]+)",
    re.IGNORECASE,
)

_ECLI_RE = re.compile(r"\bECLI:([A-Z]{2}):[A-Z0-9]{1,6}:[0-9]{4}:[A-Z0-9]{1,6}\b", re.IGNORECASE)

_CASE_NUMBER_RE = re.compile(
    r"(?:Civil|Criminal|Appeal|Αγ\.|App\.)?\s*([0-9]{1,5})\s*/\s*([0-9]{4})", re.IGNORECASE)


def parse_reference(text: str, default_law_number: str | None = None) -> ParsedReference:
    raw = (text or "").strip()
    if not raw:
        return ParsedReference(kind="unknown", raw=raw)

    m = _ARTICLE_LAW_RE.search(raw)
    if m:
        return ParsedReference(kind="legislation_article", article_number=m.group(1),
                               law_number=m.group(2), article=f"Article {m.group(1)}",
                               law=default_law_number or m.group(2), raw=raw,
                               confidence=0.97)

    e = _ECLI_RE.search(raw)
    if e:
        return ParsedReference(kind="judgment", ecli=e.group(0), raw=raw, confidence=0.99)

    c = _CASE_NUMBER_RE.search(raw)
    if c:
        return ParsedReference(kind="judgment", case_number=f"{c.group(1)}/{c.group(2)}",
                               law_number=c.group(1), law_year=c.group(2), raw=raw,
                               confidence=0.8)

    # Bare law number
    ln = re.search(r"\bLaw\s+([0-9]+)", raw, re.IGNORECASE)
    if ln:
        return ParsedReference(kind="legislation", law_number=ln.group(1),
                               law=ln.group(1), raw=raw, confidence=0.9)
    return ParsedReference(kind="unknown", raw=raw, confidence=0.0)