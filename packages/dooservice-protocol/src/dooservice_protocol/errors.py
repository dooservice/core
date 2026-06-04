from __future__ import annotations


class ProtocolError(Exception):
    pass


class AuthError(ProtocolError):
    pass


class HandshakeTimeoutError(AuthError):
    def __init__(self) -> None:
        super().__init__("Handshake timed out")


class AgentNotRegisteredError(AuthError):
    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent '{agent_id}' is not registered")


class InvalidSignatureError(AuthError):
    def __init__(self) -> None:
        super().__init__("Invalid signature")


class ReplayAttackError(AuthError):
    def __init__(self) -> None:
        super().__init__("Timestamp outside acceptable window (possible replay attack)")


class JobNotFoundError(ProtocolError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job '{job_id}' not found")
