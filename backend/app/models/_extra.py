"""Central registration of all model classes into the shared metadata."""
from ..core.audit import AuditEvent  # noqa: F401
from ..core.idempotency import IdempotencyRecord  # noqa: F401
from ..services.ingestion import LegalSource as _IgLegalSource, SourceSnapshot, SourceDocument  # noqa: F401
from .run_log import ModelRunLog  # noqa: F401
from .core import (  # noqa: F401
    Jurisdiction, Court, LegalSource,
    Legislation, LegislationVersion, LegislationNode, LegislationNodeVersion,
    LegislationAmendment, ProvisionCrossReference,
    Judgment, JudgmentVersion, JudgmentSection, JudgmentParagraph,
    CaseCitation, JudgmentLegislationLink, CaseTreatment,
    LegalChunk,
)
from .search import SearchEntry  # noqa: F401
from .matter_ws import (MatterDocument, MatterFact, MatterEvent, MatterIssue)  # noqa: F401
from .procedure import ProceduralRule  # noqa: F401
from .firm import FirmPrecedent  # noqa: F401
from .authority import (MatterAuthority, FollowedItem, Notification)  # noqa: F401