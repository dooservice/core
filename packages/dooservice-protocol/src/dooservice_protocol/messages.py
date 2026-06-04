"""Wire-level message types for the Agent ↔ Orchestrator protocol."""

from __future__ import annotations

from enum import StrEnum

import msgspec


class MessageType(StrEnum):
    # ── Handshake ────────────────────────────────────────────────
    HELLO = "hello"
    CHALLENGE = "challenge"
    CHALLENGE_RESPONSE = "challenge_response"
    AUTHENTICATED = "authenticated"
    AUTH_FAILED = "auth_failed"

    # ── Liveness ─────────────────────────────────────────────────
    PING = "ping"
    PONG = "pong"
    HEARTBEAT = "heartbeat"

    # ── Jobs (Orchestrator → Agent) ───────────────────────────────
    JOB_SUBMIT = "job.submit"
    JOB_CANCEL = "job.cancel"

    # ── Jobs (Agent → Orchestrator) ───────────────────────────────
    JOB_ACCEPTED = "job.accepted"
    JOB_PROGRESS = "job.progress"
    JOB_COMPLETED = "job.completed"
    JOB_FAILED = "job.failed"

    # ── Events (Agent → Orchestrator) ────────────────────────────
    EVENT = "event"


# ── Handshake structs ─────────────────────────────────────────────────────────


class AgentInitOuter(msgspec.Struct):
    """Agent → Orchestrator: outer init frame — only x25519_pub is plaintext."""

    x25519_pub: str  # agent's ephemeral X25519 public key hex
    data: str  # hex: Box(agent_ephemeral_priv, orch_static_pub).encrypt(hello_inner)


class HelloMessage(msgspec.Struct):
    """Agent → Orchestrator: initiate authentication."""

    agent_id: str  # UUID string
    ed25519_pub: str  # hex-encoded Ed25519 public key
    w: str  # hex-encoded X25519 public key
    ts: int  # Unix timestamp (seconds) — replay protection
    sig: str  # hex: sign(agent_id + x25519_pub + str(ts), ed25519_priv)


class ChallengeMessage(msgspec.Struct):
    """Orchestrator → Agent: nonce challenge."""

    nonce: str  # hex: 32 random bytes
    orch_x25519_pub: str  # hex: orchestrator X25519 public key
    sig: str  # hex: sign(nonce, orch_ed25519_priv)


class ChallengeResponseMessage(msgspec.Struct):
    """Agent → Orchestrator: prove ownership of private key.

    This message is ENCRYPTED with the derived nacl.Box session key.
    """

    sig: str  # hex: sign(nonce, agent_ed25519_priv)


class AuthenticatedMessage(msgspec.Struct):
    """Orchestrator → Agent: authentication confirmed.

    This message is ENCRYPTED.
    """

    session_id: str  # UUID for logging/debugging


# ── Liveness ──────────────────────────────────────────────────────────────────


class HeartbeatPayload(msgspec.Struct):
    agent_id: str
    hostname: str
    version: str
    cpu_pct: float
    mem_pct: float
    disk_pct: float
    uptime_seconds: float


# ── Job structs ───────────────────────────────────────────────────────────────


class JobSubmitPayload(msgspec.Struct):
    job_id: str  # UUID — orchestrator-assigned
    kind: str  # JobKind value
    args: dict  # kind-specific arguments
    timeout_seconds: int = 300


class JobProgressPayload(msgspec.Struct):
    job_id: str
    stage: str
    pct: int = 0  # 0-100


class JobCompletedPayload(msgspec.Struct):
    job_id: str
    result: dict


class JobFailedPayload(msgspec.Struct):
    job_id: str
    error_code: str
    message: str


class JobCancelPayload(msgspec.Struct):
    job_id: str


# ── Envelope (all post-auth messages) ────────────────────────────────────────


class Envelope(msgspec.Struct):
    """Encrypted message envelope. Serialized, then encrypted via nacl.Box."""

    id: str  # UUID — request/response correlation
    type: str  # MessageType value
    payload: dict  # type-specific payload (decoded from above structs)
