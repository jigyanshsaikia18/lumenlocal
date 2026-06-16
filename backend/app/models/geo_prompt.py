"""``GeoPrompt`` — niche-aware prompt library (DB schema §5).

Stores both default, global prompts (niche=NULL, is_custom=false) and custom,
tenant-owned prompts (is_custom=true, tenant_id set). GEO scans sample from
both default and custom pools, filtered by niche and tenant.
"""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeoPrompt(Base):
    __tablename__ = "geo_prompts"
    __table_args__ = (
        Index("ix_geo_prompts_niche", "niche"),
        Index("ix_geo_prompts_custom_tenant", "is_custom", "tenant_id"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )
    niche: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt: Mapped[str] = mapped_column(String(500), nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    tenant_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
