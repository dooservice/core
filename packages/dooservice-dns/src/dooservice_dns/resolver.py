"""DNS verification helpers."""

from __future__ import annotations

import dns.asyncresolver
from dns.exception import DNSException
from dns.resolver import NXDOMAIN, NoAnswer

from dooservice_models import DomainVerificationResult

from .errors import DnsResolutionError


async def verify_cname_record(domain: str, expected_target: str) -> DomainVerificationResult:
    expected = expected_target.rstrip(".")
    try:
        answers = await dns.asyncresolver.resolve(domain, "CNAME")
    except (NXDOMAIN, NoAnswer):
        return DomainVerificationResult(
            domain=domain,
            expected_target=expected,
            verified=False,
            reason="record not found",
        )
    except DNSException as error:
        raise DnsResolutionError(domain, str(error)) from error

    for answer in answers:
        resolved = str(answer.target).rstrip(".")
        if resolved == expected:
            return DomainVerificationResult(
                domain=domain,
                expected_target=expected,
                verified=True,
                resolved_target=resolved,
            )

    first = str(answers[0].target).rstrip(".") if answers else None
    return DomainVerificationResult(
        domain=domain,
        expected_target=expected,
        verified=False,
        resolved_target=first,
        reason="target mismatch",
    )
