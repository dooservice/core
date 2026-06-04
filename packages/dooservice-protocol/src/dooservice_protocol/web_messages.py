"""Protocol structs for web client ↔ orchestrator communication."""

from __future__ import annotations

import msgspec


class WebInitMessage(msgspec.Struct):
    """Web client → Orchestrator: start encrypted handshake (only pub key plaintext)."""

    type: str  # "web_init"
    x25519_pub: str  # client's ephemeral X25519 public key hex


class WebInitAckMessage(msgspec.Struct):
    """Orchestrator → Web client: server ephemeral pub (plaintext) + encrypted nonce."""

    type: str  # "web_init_ack"
    orch_x25519_pub: str  # server's ephemeral X25519 public key hex (plaintext for ECDH)
    data: str  # hex: Box(orch_ephemeral_priv, client_pub).encrypt({ nonce })


class WebHelloMessage(msgspec.Struct):
    """Web client → Orchestrator: initiate handshake (plaintext)."""

    type: str  # "web_hello"
    api_key: str
    x25519_pub: str  # ephemeral X25519 public key hex
    ts: int  # Unix timestamp


class WebChallengeMessage(msgspec.Struct):
    """Orchestrator → Web client: nonce challenge (plaintext)."""

    type: str  # "web_challenge"
    orch_x25519_pub: str  # orchestrator ephemeral X25519 public key hex
    nonce: str  # 32 random bytes hex


class WebChallengeResponseMessage(msgspec.Struct):
    """Web client → Orchestrator: nonce echo (encrypted)."""

    nonce: str  # must match the challenge nonce


class WebAuthenticatedMessage(msgspec.Struct):
    """Orchestrator → Web client: session established (encrypted)."""

    type: str  # "authenticated"
    session_token: str
    user: dict
    organizations: list


class WebQueryMessage(msgspec.Struct):
    """Web client → Orchestrator: data query (encrypted envelope)."""

    id: str  # UUID for request/response correlation
    type: str  # "query.projects" | "query.environments" | ...
    payload: dict


class WebCommandMessage(msgspec.Struct):
    """Web client → Orchestrator: command that dispatches a job (encrypted envelope)."""

    id: str
    type: str  # "cmd.env.provision" | "cmd.env.start" | ...
    payload: dict


class WebResponseMessage(msgspec.Struct):
    """Orchestrator → Web client: response to a query or command (encrypted envelope)."""

    id: str  # matches the request id
    type: str  # "response.projects" | "response.job_submitted" | ...
    payload: dict


class WebEventMessage(msgspec.Struct):
    """Orchestrator → Web client: real-time event broadcast (encrypted envelope)."""

    type: str  # "event.env_state_changed" | "event.agent_online" | ...
    payload: dict


class WebErrorMessage(msgspec.Struct):
    """Orchestrator → Web client: error response (encrypted envelope)."""

    id: str
    message: str
    type: str = "error"
