"""L0 deterministic extraction of facts and chronology events from matter text.

Produces source-linked candidates (char spans). AI enrichment may later refine;
until then these are labelled `proposed` and reviewed by the lawyer.
"""
import re
from datetime import datetime

_DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
_AMOUNT_RE = re.compile(r"[€£$]\s?(\d[\d,.]*)")
_PARTY_RE = re.compile(r"\b((?:[A-Z][a-zA-Z]+\s?)+)\b")
_NAME_STOP = {"The", "This", "That", "In", "On", "At", "By", "For", "Any", "Shall",
              "From", "Under", "Court", "Agreement", "Party", "Article", "Section",
              "Schedule", "Cyprus", "Each"}

_OBLIGATION = {"shall", "must", "agrees to", "is liable", "shall pay",
               "warrants", "undertakes"}
_EVENT_KW = {"delivered", "signed", "commenced", "terminated", "filed",
             "appointed", "petitioned", "expired", "received", "paid"}


def extract_facts(text: str) -> list[dict]:
    results = []

    for m in _AMOUNT_RE.finditer(text):
        results.append({"kind": "amount", "text": m.group(0), "char_start": m.start(),
                        "char_end": m.end(), "confidence": 0.9})

    lower = text.lower()
    for kw in _OBLIGATION:
        start = 0
        while True:
            idx = lower.find(kw, start)
            if idx == -1:
                break
            window = text[max(0, idx - 40): idx + 40].strip()
            results.append({"kind": "obligation", "text": window,
                            "char_start": max(0, idx - 40), "char_end": idx + 40,
                            "confidence": 0.6})
            start = idx + len(kw)

    seen = set()
    for m in _PARTY_RE.finditer(text):
        name = m.group(0).strip()
        if name in _NAME_STOP or not any(c.islower() for c in name[1:]):
            continue
        # only index capitalized proper-noun-like names
        if len(name.split()) > 3:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append({"kind": "party", "text": name, "char_start": m.start(),
                        "char_end": m.end(), "confidence": 0.7})
    return results


def extract_events(text: str) -> list[dict]:
    events = []
    for m in _DATE_RE.finditer(text):
        try:
            dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            continue
        window = text[m.start(): m.end() + 40].strip()
        snippet = re.split(r"[.;]", window)[0]
        events.append({"event_date": dt.isoformat(), "description": snippet[:160],
                       "char_start": m.start(), "char_end": m.end(), "confidence": 0.9})
    for kw in _EVENT_KW:
        start = 0
        while True:
            idx = text.lower().find(kw, start)
            if idx == -1:
                break
            before = text[max(0, idx - 30): idx]
            if _DATE_RE.search(before):
                start = idx + len(kw)
                continue  # already covered by date event above
            snippet = text[idx - 40: idx + 40].strip()
            events.append({"event_date": None, "description": snippet[:160],
                           "char_start": max(0, idx - 40), "char_end": idx + 40,
                           "confidence": 0.5})
            start = idx + len(kw)
    return events

_ISSUE_RULES = [
    ({"insolven", "wound up", "liquidator", "bankrupt", "αφερεγγυ"},
     "Is the company insolvent and therefore liable to be wound up by the court?"),
    ({"negligence", "duty of care", "negligent", "αμέλεια"},
     "Did the defendant owe and breach a duty of care towards the claimant?"),
    ({"breach", "failed to", "default", "παραβίαση"},
     "Was there a breach of the parties' contractual obligations?"),
    ({"damages", "compensation", "loss", "ζημία"},
     "What damages or compensation is the claimant entitled to recover?"),
    ({"liable", "liability", "responsib", "ευθύν"},
     "Is the defendant liable to the claimant and on what legal basis?"),
    ({"limitation", "time-barred", "παρεγράφ"},
     "Is the claim barred by the applicable limitation period?"),
    ({"jurisdiction", "δικαιοδοσία"},
     "Does the court have jurisdiction to hear and determine the claim?"),
    ({"specific performance", "injunction"},
     "Is an equitable remedy (specific performance / injunction) available and appropriate?"),
]


def suggest_issues(facts: list[str]) -> list[dict]:
    """Deterministic L0: map accepted matter facts to candidate legal issues."""
    issues = []
    seen = set()
    all_txt = " ".join(facts).lower()
    for keywords, issue in _ISSUE_RULES:
        if any(k in all_txt for k in keywords) and issue not in seen:
            seen.add(issue)
            issues.append({"text": issue})
    return issues
