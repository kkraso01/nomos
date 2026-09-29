"""Idempotently load the engineering source registry seed."""
import os

import yaml
from sqlalchemy.orm import Session

from ..config import settings
from .. import models
from ..models.core import Jurisdiction, Court, JurisdictionConfig


_NODE_TERMS = {
    "CY": {"1": "LAW", "2": "PART", "3": "CHAPTER", "4": "ARTICLE", "5": "SUBARTICLE", "6": "PARAGRAPH"},
    "UK": {"1": "ACT", "2": "PART", "3": "Section", "4": "Subsection", "5": "Paragraph"},
    "EU": {"1": "REGULATION", "2": "TITLE", "3": "ARTICLE", "4": "PARAGRAPH", "5": "SUB-PARAGRAPH"},
}

_CY_COURTS = [
    ("Supreme Court (Ανώτατο Δικαστήριο)", 3, "supreme", None),
    ("District Court (Επαρχιακό Δικαστήριο)", 1, "district", None),
    ("Family Court (Οικογενειακό Δικαστήριο)", 2, "family", None),
    ("Assize Court (Κακουργιοδικείο)", 2, "assize", None),
    ("Industrial Disputes Court", 1, "industrial", None),
]


def seed_core(db: Session) -> dict:
    """Idempotently seed jurisdictions and representative court hierarchies."""
    created_j, created_c = 0, 0
    for code, name in [("CY", "Cyprus"), ("EU", "European Union"), ("ECHR", "European Convention on Human Rights"),
                       ("GR", "Greece"), ("UK", "United Kingdom")]:
        j = db.get(Jurisdiction, code)
        if j is None:
            db.add(Jurisdiction(code=code, name=name, node_terms=_NODE_TERMS.get(code, _NODE_TERMS["CY"]),
                                default_language="en" if code != "CY" else "el", active=True))
            created_j += 1
    db.flush()
    for name, level, code, parent in _CY_COURTS:
        c = db.query(Court).filter_by(jurisdiction="CY", name=name).first()
        if c is None:
            db.add(Court(jurisdiction="CY", name=name, court_level=level, code=code))
            created_c += 1
    db.commit()
    return {"jurisdictions_created": created_j, "courts_created": created_c}


def _defaults(payload: dict) -> dict:
    fields = {
        "official_source": False, "primary_source": False, "base_url": None,
        "reuse_status": "UNKNOWN", "licence": None, "licence_url": None,
        "commercial_reuse_allowed": False, "automated_access_allowed": False,
        "bulk_download_allowed": False, "api_available": False,
        "attribution_required": False, "adapter_enabled": False, "notes": None,
    }
    merged = dict(fields)
    for k, v in payload.items():
        if v is not None:
            merged[k] = v
    return merged


def seed_sources_from_yaml(db: Session, path: str | None = None) -> dict:
    path = path or os.path.join(settings.root_dir, "SOURCE_REGISTRY_SEED.yaml")
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    TYPE_BY_KEY = {
        "cyprus_open_data": "PORTAL",
        "cyprus_gazette": "GAZETTE",
        "cyprus_supreme_court": "JUDGMENT",
        "cylaw": "DATABASE",
        "eurlex": "LEGISLATION",
        "hudoc": "JUDGMENT",
    }

    created, updated, skipped = 0, 0, 0
    for item in data.get("sources", []):
        name = item["name"].strip()
        row = db.query(models.SourceRegistry).filter_by(name=name).first()
        kwargs = _defaults(item)
        kwargs.pop("key", None)
        kwargs.pop("name", None)
        if not kwargs.get("source_type"):
            kwargs["source_type"] = TYPE_BY_KEY.get(item.get("key"), "DATABASE")
        if row is None:
            db.add(models.SourceRegistry(name=name, **kwargs))
            created += 1
        else:
            changed = False
            for k, v in kwargs.items():
                if getattr(row, k) != v:
                    setattr(row, k, v)
                    changed = True
            updated += 1 if changed else 0
            skipped += 0 if changed else 1
    db.commit()
    return {"created": created, "updated": updated, "skipped": skipped}