"""Jurisdiction-agnostic legal knowledge-core models.

Canonical design (per goal):
  Permanent provision identity (LegislationNode) is SEPARATE from its versioned
  text (LegislationNodeVersion). Amendments are first-class events. Cross-
  references, judgment structure, citations, treatment and structural chunks are
  all jurisdiction/source-aware. Cyprus is the Phase-1 module, but no CY
  assumption is encoded in these shared contracts.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, JSON,
                        String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import UUID

from . import Base


def _now():
    return datetime.now(timezone.utc)


_JURISDICTIONS = ("CY", "EU", "ECHR", "GR", "UK")


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"
    code = Column(String(16), primary_key=True)
    name = Column(String(255), nullable=False)
    # node terminology per jurisdiction, e.g.
    # {"1": "LAW", "2": "PART", "3": "CHAPTER", "4": "ARTICLE", "5": "SUBARTICLE", "6": "PARAGRAPH"}
    # vs {"1":"ACT","2":"PART","3":"Section","4":"Subsection","5":"Paragraph"}
    node_terms = Column(JSON, nullable=False, default=dict)
    default_language = Column(String(16), nullable=True)
    active = Column(Boolean, nullable=False, default=True)


class Court(Base):
    __tablename__ = "courts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jurisdiction = Column(String(16), ForeignKey("jurisdictions.code"), nullable=False, index=True)
    court_level = Column(Integer, nullable=False, default=1)
    name = Column(String(255), nullable=False)
    name_el = Column(String(255), nullable=True)
    parent_court_id = Column(UUID(as_uuid=True), nullable=True)
    code = Column(String(64), nullable=True)
    __table_args__ = (UniqueConstraint("jurisdiction", "name", name="uq_court_jur_name"),)


class LegalSource(Base):
    __tablename__ = "legal_sources_core"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jurisdiction = Column(String(16), ForeignKey("jurisdictions.code"), nullable=False, index=True)
    source_key = Column(String(255), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    official_source = Column(Boolean, nullable=False, default=False)
    primary_source = Column(Boolean, nullable=False, default=False)
    base_url = Column(String(1024), nullable=True)


class Legislation(Base):
    __tablename__ = "legislation"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_id = Column(String(255), nullable=False, index=True)
    title = Column(String(1024), nullable=False)
    jurisdiction = Column(String(16), ForeignKey("jurisdictions.code"), nullable=False, index=True)
    source_id = Column(UUID(as_uuid=True), nullable=True)
    language = Column(String(16), nullable=True)
    current_version_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class LegislationVersion(Base):
    __tablename__ = "legislation_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legislation_id = Column(UUID(as_uuid=True), ForeignKey("legislation.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(64), nullable=False)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="current")
    supersedes_version_id = Column(UUID(as_uuid=True), nullable=True)
    source_snapshot_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint("legislation_id", "version_number", name="uq_leg_version"),)


class LegislationNode(Base):
    """Permanent provision identity. Wording lives in LegislationNodeVersion."""
    __tablename__ = "legislation_nodes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    legislation_id = Column(UUID(as_uuid=True), ForeignKey("legislation.id"), nullable=False, index=True)
    parent_id = Column(UUID(as_uuid=True), nullable=True)
    node_type = Column(String(32), nullable=False)      # term from Jurisdiction.node_terms
    number = Column(String(64), nullable=True)          # canonical number, e.g. "15" or "15(2)(a)"
    title = Column(String(512), nullable=True)
    sort_order = Column(Integer, nullable=True, default=0)
    __table_args__ = (
        UniqueConstraint("legislation_id", "node_type", "number", name="uq_leg_node_identity"),
    )


class LegislationNodeVersion(Base):
    """The wording of a LegislationNode within a legislation version."""
    __tablename__ = "legislation_node_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_id = Column(UUID(as_uuid=True), ForeignKey("legislation_nodes.id"), nullable=False, index=True)
    legislation_version_id = Column(UUID(as_uuid=True), ForeignKey("legislation_versions.id"), nullable=False, index=True)
    source_text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=True)
    language = Column(String(16), nullable=True)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    source_locator = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=True)
    __table_args__ = (UniqueConstraint("node_id", "legislation_version_id", name="uq_node_version"),)


class LegislationAmendment(Base):
    __tablename__ = "legislation_amendments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jurisdiction = Column(String(16), ForeignKey("jurisdictions.code"), nullable=False, index=True)
    amending_legislation_id = Column(UUID(as_uuid=True), nullable=True)   # the amending law
    affected_legislation_id = Column(UUID(as_uuid=True), nullable=False)
    affected_node_id = Column(UUID(as_uuid=True), ForeignKey("legislation_nodes.id"), nullable=True)
    operation = Column(String(32), nullable=False)  # INSERT/DELETE/REPLACE/RENUMBER/REPEAL/COMMENCE
    previous_text = Column(Text, nullable=True)
    new_text = Column(Text, nullable=True)
    publication_date = Column(DateTime(timezone=True), nullable=True)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    source_snapshot_id = Column(UUID(as_uuid=True), nullable=True)
    source_evidence = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class ProvisionCrossReference(Base):
    __tablename__ = "provision_cross_references"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jurisdiction = Column(String(16), ForeignKey("jurisdictions.code"), nullable=False, index=True)
    source_node_id = Column(UUID(as_uuid=True), ForeignKey("legislation_nodes.id"), nullable=True)
    source_jurisdiction = Column(String(16), nullable=True)
    source_cross_jurisdiction_key = Column(String(255), nullable=True)   # cross-jurisdiction target key
    target_node_id = Column(UUID(as_uuid=True), ForeignKey("legislation_nodes.id"), nullable=True)
    target_jurisdiction = Column(String(16), nullable=True)
    target_external_key = Column(String(255), nullable=True)             # e.g. EUR-Lex CELEX / ECLI
    relationship = Column(String(32), nullable=False, default="REFERENCES")
    source_span_start = Column(Integer, nullable=True)
    source_span_end = Column(Integer, nullable=True)
    source_text = Column(Text, nullable=True)
    confidence = Column(String(16), nullable=False, default="high")      # high/medium/review
    created_at = Column(DateTime(timezone=True), default=_now)


class Judgment(Base):
    __tablename__ = "judgments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_id = Column(String(255), nullable=False, index=True)
    title = Column(String(1024), nullable=True)
    jurisdiction = Column(String(16), ForeignKey("jurisdictions.code"), nullable=False, index=True)
    court_id = Column(UUID(as_uuid=True), ForeignKey("courts.id"), nullable=True)
    court = Column(String(128), nullable=True)          # display
    case_number = Column(String(255), nullable=True)
    ecli = Column(String(128), nullable=True, index=True)
    judgment_date = Column(DateTime(timezone=True), nullable=True)
    judges = Column(JSON, nullable=True)
    language = Column(String(16), nullable=True)
    source_id = Column(UUID(as_uuid=True), nullable=True)
    current_version_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class JudgmentVersion(Base):
    __tablename__ = "judgment_versions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    judgment_id = Column(UUID(as_uuid=True), ForeignKey("judgments.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(64), nullable=False)
    source_snapshot_id = Column(UUID(as_uuid=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    __table_args__ = (UniqueConstraint("judgment_id", "version_number", name="uq_judgment_version"),)


class JudgmentSection(Base):
    __tablename__ = "judgment_sections"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = Column(UUID(as_uuid=True), ForeignKey("judgment_versions.id"), nullable=False, index=True)
    section_type = Column(String(32), nullable=False)  # facts/procedural_history/issue/party_argument/legal_analysis/holding/order/separate_opinion
    title = Column(String(255), nullable=True)
    sort_order = Column(Integer, nullable=True, default=0)


class JudgmentParagraph(Base):
    __tablename__ = "judgment_paragraphs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version_id = Column(UUID(as_uuid=True), ForeignKey("judgment_versions.id"), nullable=False, index=True)
    section_id = Column(UUID(as_uuid=True), ForeignKey("judgment_sections.id"), nullable=True)
    para_number = Column(String(64), nullable=True)
    text = Column(Text, nullable=False)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)
    sort_order = Column(Integer, nullable=True, default=0)
    language = Column(String(16), nullable=True)


class CaseCitation(Base):
    __tablename__ = "case_citations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_jurisdiction = Column(String(16), nullable=True)
    source_case_id = Column(UUID(as_uuid=True), ForeignKey("judgments.id"), nullable=True)
    source_case_key = Column(String(255), nullable=True)          # cross-jurisdiction source key
    target_jurisdiction = Column(String(16), nullable=True)
    target_case_id = Column(UUID(as_uuid=True), ForeignKey("judgments.id"), nullable=True)
    target_case_key = Column(String(255), nullable=True)          # e.g. ECLI / external
    kind = Column(String(16), nullable=False, default="CITES")
    evidence_paragraph_id = Column(UUID(as_uuid=True), nullable=True)
    confidence = Column(String(16), nullable=True)
    review_status = Column(String(32), nullable=False, default="review_required")
    created_at = Column(DateTime(timezone=True), default=_now)


class JudgmentLegislationLink(Base):
    __tablename__ = "judgment_legislation_links"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    judgment_jurisdiction = Column(String(16), nullable=True)
    judgment_id = Column(UUID(as_uuid=True), ForeignKey("judgments.id"), nullable=True)
    judgment_key = Column(String(255), nullable=True)
    legislation_jurisdiction = Column(String(16), nullable=True)
    legislation_id = Column(UUID(as_uuid=True), ForeignKey("legislation.id"), nullable=True)
    provision_node_id = Column(UUID(as_uuid=True), ForeignKey("legislation_nodes.id"), nullable=True)
    provision_external_key = Column(String(255), nullable=True)     # CELEX / statute key
    relationship = Column(String(32), nullable=False, default="APPLIES")  # INTERPRETS/APPLIES/DISCUSSES
    evidence_paragraph_id = Column(UUID(as_uuid=True), nullable=True)
    confidence = Column(String(16), nullable=True)
    review_status = Column(String(32), nullable=False, default="review_required")
    created_at = Column(DateTime(timezone=True), default=_now)


class CaseTreatment(Base):
    __tablename__ = "case_treatment"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_case_jurisdiction = Column(String(16), nullable=True)
    source_case_id = Column(UUID(as_uuid=True), ForeignKey("judgments.id"), nullable=True)
    source_case_key = Column(String(255), nullable=True)
    target_case_jurisdiction = Column(String(16), nullable=True)
    target_case_id = Column(UUID(as_uuid=True), ForeignKey("judgments.id"), nullable=True)
    target_case_key = Column(String(255), nullable=True)
    treatment = Column(String(32), nullable=False)  # FOLLOWS/DISTINGUISHES/APPROVES/CRITICISES/OVERRULES/DISCUSSES
    evidence_paragraph_id = Column(UUID(as_uuid=True), nullable=True)
    confidence = Column(String(16), nullable=True)
    extracted_by = Column(String(32), nullable=True)   # deterministic|llm|human
    review_status = Column(String(32), nullable=False, default="review_required")
    created_at = Column(DateTime(timezone=True), default=_now)


class LegalChunk(Base):
    """Structural (not fixed-token) retrieval unit."""
    __tablename__ = "legal_chunks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jurisdiction = Column(String(16), ForeignKey("jurisdictions.code"), nullable=False, index=True)
    document_type = Column(String(32), nullable=False)           # legislation | judgment | source_document
    document_id = Column(UUID(as_uuid=True), nullable=True)
    document_key = Column(String(255), nullable=True)
    version_id = Column(UUID(as_uuid=True), nullable=True)
    chunk_type = Column(String(32), nullable=False)              # paragraph | section
    text = Column(Text, nullable=False)                          # canonical source text (unchanged)
    hierarchy_context = Column(Text, nullable=True)              # embedding input (prepended context)
    normalized_text = Column(Text, nullable=True)
    language = Column(String(16), nullable=True)
    parent_node_id = Column(UUID(as_uuid=True), nullable=True)
    section_id = Column(UUID(as_uuid=True), nullable=True)
    paragraph_number = Column(String(64), nullable=True)
    law_id = Column(UUID(as_uuid=True), nullable=True)
    article_number = Column(String(64), nullable=True)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_to = Column(DateTime(timezone=True), nullable=True)
    source_document_id = Column(UUID(as_uuid=True), nullable=True)
    source_locator = Column(JSON, nullable=True)
    embedding_provider = Column(String(64), nullable=True)
    embedding_model = Column(String(128), nullable=True)
    embedding_version = Column(String(64), nullable=True)
    embedding_dimensions = Column(Integer, nullable=True)
    embedding_created_at = Column(DateTime(timezone=True), nullable=True)
    embedding = Column(JSON, nullable=True)  # vector as JSON float array (pgvector substitute)
    content_hash = Column(String(64), nullable=True)
    model_run_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class JurisdictionConfig:
    """Per-jurisdiction behavior registry (terminology + court order + ref syntax)."""
    _NODE_TERMS = {
        "CY": {"1": "LAW", "2": "PART", "3": "CHAPTER", "4": "ARTICLE", "5": "SUBARTICLE", "6": "PARAGRAPH"},
        "UK": {"1": "ACT", "2": "PART", "3": "Section", "4": "Subsection", "5": "Paragraph"},
        "EU": {"1": "REGULATION", "2": "TITLE", "3": "ARTICLE", "4": "PARAGRAPH", "5": "SUB-PARAGRAPH"},
    }

    @staticmethod
    def node_terms(code: str) -> dict:
        return JurisdictionConfig._NODE_TERMS.get(code, JurisdictionConfig._NODE_TERMS["CY"])