"""Idempotently load the engineering source registry seed."""
import os

import yaml
from sqlalchemy.orm import Session

from ..config import settings
from .. import models


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