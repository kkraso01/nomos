"""Offline adapter tests: EUR-Lex/CELLAR (no network) + data.gov.cy normalizers.

These lock the adapter contract: licence-aware dispatch, no-invention guarantees
(invalid CELEX / missing title refused), and faithful normalisation of REAL
recorded fixtures. Live EUR-Lex bulk acquisition is separately BLOCKED_EXTERNAL.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.adapters import DataGovCyAdapter, EurLexCellarAdapter
from app.adapters.base import AdapterConfigError

FIXTURES = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "fixtures")


# ---- EUR-Lex / CELLAR -----------------------------------------------------
def test_discovery_yields_real_celex_seeds():
    adapter = EurLexCellarAdapter()
    celexes = [r["celex"] for r in adapter.discover()]
    assert "32011L0083" in celexes       # Consumer Rights Directive (real CELEX)
    assert "32016R0679" in celexes       # GDPR (real CELEX)
    for r in adapter.discover():
        assert r["jurisdiction"] == "EU"
        assert r["kind"] == "legislation"


def test_normalize_requires_valid_celex():
    adapter = EurLexCellarAdapter()
    with pytest.raises(AdapterConfigError):
        adapter.normalize(b"x", {"celex": "", "title_en": "Some act"})
    with pytest.raises(AdapterConfigError):
        # well-formed-looking but not a real 4-2-L/R-4 CELEX -> refuse (never invent)
        adapter.normalize(b"x", {"celex": "123456L9999", "title_en": "T"})


def test_normalize_requires_official_title():
    adapter = EurLexCellarAdapter()
    with pytest.raises(AdapterConfigError):
        adapter.normalize(b"x", {"celex": "32011L0083"})


def test_normalize_maps_official_metadata():
    adapter = EurLexCellarAdapter()
    rec = next(r for r in adapter.discover() if r["celex"] == "32011L0083")
    out = adapter.normalize(b"staged", rec)[0]
    assert out["canonical_key"] == "32011L0083"
    assert out["jurisdiction"] == "EU"
    assert out["kind"] == "legislation"
    assert "δικαιώματα των καταναλωτών" in out["title"]
    assert out["nature"] == "DIRECTIVE"


def test_fetch_gated_raises_adapterconfig():
    class _202Session:
        def get(self, url):
            class R:
                status_code = 202
            return R()
    adapter = EurLexCellarAdapter(session=_202Session())
    with pytest.raises(AdapterConfigError):
        adapter.fetch({"celex": "32011L0083", "source_url": "x"})


def test_fetch_staged_payload_used():
    class _Never:
        def get(self, url):
            raise AssertionError("should not hit network when staged payload present")
    adapter = EurLexCellarAdapter(session=_Never())
    raw = adapter.fetch({"staged_payload": b"official-dump-xml"})
    assert raw == b"official-dump-xml"


# ---- data.gov.cy normalizers (offline, recorded real fixtures) ------------
def test_consumer_csv_normalizer_real_fixture():
    adapter = DataGovCyAdapter()
    meta = adapter.DATASETS["consumer_decisions"]
    raw = open(os.path.join(FIXTURES, "data_gov_cy_consumer_decisions.csv"), "rb").read()
    recs = adapter.normalize(raw, {**meta, "dataset_key": "consumer_decisions"})
    assert len(recs) >= 100          # real 2010-2017 table
    first = recs[0]
    assert first["authority_type"] == "ADMINISTRATIVE_DECISION"
    assert first["decision_no"]
    assert first["licence"] == "CC BY 4.0"
    # deterministic statutory-basis text preserved, never fabricated into a number
    assert "Legislation" in first or "Statutory basis" in first["body"]


def test_labour_xlsx_normalizer_real_fixture():
    adapter = DataGovCyAdapter()
    meta = adapter.DATASETS["labour_inspection_court_stats"]
    raw = open(os.path.join(FIXTURES, "data_gov_cy_labour_court_stats.xlsx"), "rb").read()
    recs = adapter.normalize(raw, {**meta, "dataset_key": "labour_inspection_court_stats"})
    assert len(recs) > 200
    assert recs[0]["authority_type"] == "CASE_STATISTICS"
    assert all(r["kind"] == "source_document" for r in recs)


def test_licence_snapshot_guardrail():
    snapshot = DataGovCyAdapter().licence_snapshot(
        {**DataGovCyAdapter.DATASETS["council_ministers_decisions"],
         "dataset_key": "council_ministers_decisions"})
    # Council content lives on an external unverified host -> must not be treated as reusable
    assert snapshot["commercial_reuse_allowed"] is None
    assert DataGovCyAdapter.DATASETS["council_ministers_decisions"]["linked_on_external"] is True