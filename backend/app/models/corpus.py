"""Canonical, jurisdiction-agnostic legal-knowledge model (re-export from .core).

Legacy duplicate entity definitions were removed in the green-field refactor; the
canonical model lives in app.models.core. This module re-exports it so
`from ..models.corpus import ...` continues to resolve to the canonical classes.
"""
from .core import (  # noqa: F401
    Jurisdiction, Court, LegalSource,
    Legislation, LegislationVersion, LegislationNode, LegislationNodeVersion,
    LegislationAmendment,
    ProvisionCrossReference,
    Judgment, JudgmentVersion, JudgmentSection, JudgmentParagraph,
    CaseCitation, JudgmentLegislationLink, CaseTreatment,
    LegalChunk, JurisdictionConfig,
)