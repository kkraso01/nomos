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

# --- Deterministic multi-reference extractor (returns exact spans) ---
_REF_ARTICLE = re.compile(
    r"(?:Άρθρο|άρθρο|Article|αρ\.)\s*\.?\s*"
    r"([0-9IVXLC]+(?:[A-Z])?)(?:\((\d+[a-z]?)\))?(?:\(([α-ω])\))?", re.IGNORECASE)
_REF_CHAPTER = re.compile(r"(?:ΚΕΦ\.|Κεφ\.|Κεφάλαιο|Chapter)\s*([0-9]+)", re.IGNORECASE)
_REF_LAW = re.compile(
    r"(?:Ν\.\s*|Law\s+|Νόμος\s+)?([0-9]+)(?:\(([IVXLC]+)\))?\s*/\s*([0-9]{4})", re.IGNORECASE)
_REF_ECLI = re.compile(r"\bECLI:([A-Z]{2}):[A-Z0-9]{1,6}:[0-9]{4}:[A-Z0-9]{1,6}\b", re.IGNORECASE)
_REF_CASE = re.compile(r"([0-9]{1,5})\s*/\s*([0-9]{4})", re.IGNORECASE)


def extract_references(text: str) -> list[dict]:
    """Return deterministic legal references with exact character spans.

    Each item: {"kind": article|chapter|law|judgment_ecli|judgment_case,
                "article"/"sub"/"para"/"chapter"/"law"/"ecli"/"case", start, end}
    """
    if not text:
        return []
    out = []
    for m in _REF_ARTICLE.finditer(text):
        out.append({"kind": "article", "article": m.group(1), "sub": m.group(2),
                    "para": m.group(3), "start": m.start(), "end": m.end(),
                    "text": text[m.start():m.end()]})
    for m in _REF_CHAPTER.finditer(text):
        out.append({"kind": "chapter", "chapter": m.group(1), "start": m.start(),
                    "end": m.end(), "text": text[m.start():m.end()]})
    for m in _REF_LAW.finditer(text):
        out.append({"kind": "law", "law": m.group(1), "roman": m.group(2),
                    "year": m.group(3), "start": m.start(), "end": m.end(),
                    "text": text[m.start():m.end()]})
    for m in _REF_ECLI.finditer(text):
        out.append({"kind": "judgment_ecli", "ecli": m.group(0), "start": m.start(),
                    "end": m.end(), "text": m.group(0)})
    for m in _REF_CASE.finditer(text):
        out.append({"kind": "judgment_case", "case": f"{m.group(1)}/{m.group(2)}",
                    "start": m.start(), "end": m.end(), "text": m.group(0)})
    return out
