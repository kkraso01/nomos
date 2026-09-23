import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr


# ---- Auth / identity ----
class OrgCreate(BaseModel):
    name: str
    slug: str
    remote_ai_policy: Literal["REMOTE_AI_DISABLED", "PUBLIC_ONLY", "PRIVATE_ALLOWED"] = "PUBLIC_ONLY"


class RegisterRequest(BaseModel):
    org: OrgCreate
    admin_email: EmailStr
    admin_password: str = "adminpass"
    admin_full_name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    org_id: uuid.UUID
    user_id: uuid.UUID
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: Optional[str]
    is_active: bool


# ---- Matters ----
class MatterCreate(BaseModel):
    title: str
    description: Optional[str] = None


class MatterOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ---- Document storage ----
class DocumentOut(BaseModel):
    key: str
    content_type: str
    private: bool
    content_length: Optional[int] = None


# ---- Source registry ----
class SourceRegistryCreate(BaseModel):
    name: str
    jurisdiction: str
    source_type: str
    official_source: bool = False
    primary_source: bool = False
    base_url: Optional[str] = None
    reuse_status: Literal[
        "UNKNOWN", "PERMISSION_REQUIRED", "RESTRICTED", "DISABLED",
        "APPROVED_OPEN", "APPROVED_WITH_ATTRIBUTION", "APPROVED_API_ONLY",
    ] = "UNKNOWN"
    licence: Optional[str] = None
    licence_url: Optional[str] = None
    commercial_reuse_allowed: bool = False
    automated_access_allowed: bool = False
    bulk_download_allowed: bool = False
    api_available: bool = False
    attribution_required: bool = False
    adapter_enabled: bool = False
    notes: Optional[str] = None


class SourceRegistryOut(BaseModel):
    id: uuid.UUID
    name: str
    jurisdiction: str
    source_type: str
    reuse_status: str
    adapter_enabled: bool
    bulk_download_allowed: bool
    api_available: bool
    automated_access_allowed: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---- Ingestion ----
class IngestRawRequest(BaseModel):
    canonical_key: str
    title: Optional[str] = None
    language: Optional[str] = None
    mime_type: Optional[str] = None
    raw_payload: str
    source_record_id: Optional[str] = None


class IngestRawResponse(BaseModel):
    document_id: uuid.UUID
    canonical_key: str
    content_hash: str
    created_new: bool
    version_changed: bool
    deduplicated: bool


# ---- Jobs ----
class JobOut(BaseModel):
    id: str
    status: str
    result: Optional[dict]
    error: Optional[str]