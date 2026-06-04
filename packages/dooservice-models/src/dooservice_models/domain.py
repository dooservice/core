"""Custom domains attached to an environment."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

import msgspec


class CustomDomainStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class CustomDomain(msgspec.Struct):
    domain: str
    status: CustomDomainStatus = CustomDomainStatus.PENDING
    expected_target: str = ""
    verification_error: str | None = None
    created_at: datetime = msgspec.field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = msgspec.field(default_factory=lambda: datetime.now(UTC))
    verified_at: datetime | None = None
    last_checked_at: datetime | None = None
