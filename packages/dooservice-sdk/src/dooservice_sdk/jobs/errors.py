from __future__ import annotations


class UnknownJobKindError(Exception):
    def __init__(self, kind: str) -> None:
        super().__init__(f"No handler registered for job kind '{kind}'")
