"""Real adapter: EUR-Lex / CELLAR — the major EU production corpus.

Approved means (SOURCE_REGISTRY_SEED.yaml `eurlex` = APPROVED_OPEN):
  * CELLAR REST (content-addressed, all formats)   https://publications.europa.eu/web/cellar/
  * EUR-Lex XMLEXPORT/webservice                    https://eur-lex.europa.eu/
  * official data dumps (monthly full corpus)

EDGES/CONSTRAINTS honoured here:
  * Never scrape EUR-Lex presentation HTML.
  * Do not invent CELEX numbers, titles, article text, dates or citations.
  * The adapter normalizes OFFICIAL records only (title/nature/CELEX/date/language
    carried by the act itself). If a record lacks an official CELEX it is refused.
  * Live full-text acquisition is available ONLY through the approved mass-data
    channel; when that channel is gated/unreachable from the host (EUR-Lex 202
    anti-bot, cellar-imm-pub unreachable) fetch() raises AdapterConfigError and the
    runner records BLOCKED_EXTERNAL — never a fabricated substitute.

The seed set below is REAL, producer-listed Cyprus-relevant EU instruments, kept
as metadata (CELEX + official el/en titles). No statutory text is invented.
"""
import re
from typing import Iterator, Optional

import httpx

from .base import SourceAdapter, AdapterConfigError

UA = "Mozilla/5.0 (X11; Linux x86_64) NOMOS-research/0.1"

REGISTRY_KEY = "eurlex"

# CELEX -> (nature, el_official_title, en_official_title). These identifiers and
# titles are public, producer-stable metadata of the acts themselves.
CELEX_SEED = {
    "32011L0083": {
        "nature": "DIRECTIVE",
        "title_el": "Οδηγία 2011/83/ΕΕ του Ευρωπαϊκού Κοινοβουλίου και του Συμβουλίου, "
                    "της 25ης Οκτωβρίου 2011, σχετικά με τα δικαιώματα των καταναλωτών",
        "title_en": "Directive 2011/83/EU of the European Parliament and of the Council "
                    "of 25 October 2011 on consumer rights",
    },
    "32016R0679": {
        "nature": "REGULATION",
        "title_el": "Κανονισμός (ΕΕ) 2016/679 του Ευρωπαϊκού Κοινοβουλίου και του Συμβουλίου, "
                    "της 27ης Απριλίου 2016, για την προστασία των φυσικών προσώπων έναντι "
                    "της επεξεργασίας δεδομένων προσωπικού χαρακτήρα",
        "title_en": "Regulation (EU) 2016/679 of the European Parliament and of the Council "
                    "of 27 April 2016 on the protection of natural persons with regard to "
                    "the processing of personal data",
    },
    "32015L2302": {
        "nature": "DIRECTIVE",
        "title_el": "Οδηγία (ΕΕ) 2015/2302 του Ευρωπαϊκού Κοινοβουλίου και του Συμβουλίου, "
                    "της 25ης Νοεμβρίου 2015, για τις συμβάσεις οργανωμένων ταξιδιών και "
                    "συνδεδεμένων ταξιδιωτικών διακανονισμών",
        "title_en": "Directive (EU) 2015/2302 of the European Parliament and of the Council "
                    "of 25 November 2015 on package travel and linked travel arrangements",
    },
}

# Approved mass-data channel. fetch() resolves a CELEX to its canonical CELLAR/EUR-Lex
# retrieval; the exact working URL is deployment/live-channel dependent.
CELLAR_BASE = "https://publications.europa.eu/web/cellar/"


class EurLexCellarAdapter(SourceAdapter):
    name = "eurlex_cellar"
    registry_key = REGISTRY_KEY

    def __init__(self, session: Optional[httpx.Client] = None):
        self.session = session or httpx.Client(headers={"User-Agent": UA}, timeout=60.0,
                                               follow_redirects=True)

    def discover(self, cursor: Optional[str] = None) -> Iterator[dict]:
        for celex, meta in CELEX_SEED.items():
            if cursor and celex < cursor:
                continue
            yield {
                "kind": "legislation",
                "celex": celex,
                "jurisdiction": "EU",
                "nature": meta["nature"],
                "title_el": meta["title_el"],
                "title_en": meta["title_en"],
                "language": "el",
                "source_url": f"{CELLAR_BASE}data/{celex}",
                "_staged": True,  # metadata-only records; full text requires bulk channel
            }

    def fetch(self, record: dict) -> bytes:
        # If a lawfully staged official payload is supplied (fixture), use it.
        staged = record.get("staged_payload")
        if staged is not None:
            if isinstance(staged, bytes):
                return staged
            if isinstance(staged, str):
                return staged.encode("utf-8")
        # Otherwise go through the approved mass-data channel. A 202 anti-bot /
        # connection failure / 4xx from the gateway is NOT legal to bypass.
        url = record.get("source_url")
        try:
            r = self.session.get(url)
            if r.status_code == 202:
                raise AdapterConfigError(
                    f"EUR-Lex/CELLAR acquisition gated from this host (HTTP {r.status_code} "
                    f"anti-bot): live bulk BLOCKED_EXTERNAL; use the approved bulk channel from "
                    f"an unconstrained network or a monthly data dump.")
            r.raise_for_status()
            return r.content
        except AdapterConfigError:
            raise
        except Exception as e:  # noqa: BLE001
            raise AdapterConfigError(f"EUR-Lex/CELLAR unreachable from this host: {e}")

    def normalize(self, raw: bytes, record: dict) -> list[dict]:
        """Parse an EU act into canonical legislation fields.

        `raw` is the official payload (or fixture). Only CELEX + official titles are
        promoted; no statutory text is invented. Deterministic checks:
          1. CELEX must be present and well-formed (^[1-4][0-9]{2}[0-9]{2}[LR][0-9]{4}$).
          2. >=1 official language title must be present.
        """
        text = raw.decode("utf-8", errors="replace")
        celex = record.get("celex", "")
        if not re.fullmatch(r"[1-4]\d{2}\d{2}[LR]\d{4}", celex or ""):
            raise AdapterConfigError(f"invalid/missing CELEX: {celex!r} — refusing (never invent)")
        title = record.get("title_el") or record.get("title_en")
        if not title:
            raise AdapterConfigError("no official title present — refusing")
        language = record.get("language", "el")
        body = "\n".join(x for x in (title, record.get("title_en", "")) if x)
        return [{
            "kind": "legislation",
            "canonical_key": celex,
            "title": title,
            "language": language,
            "body": body,
            "celex": celex,
            "nature": record.get("nature"),
            "jurisdiction": "EU",
            "source_url": record.get("source_url"),
            "licence": "Reuse permitted subject to copyright conditions (EUR-Lex)",
        }]