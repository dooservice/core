from __future__ import annotations

from collections.abc import Awaitable, Callable

import msgspec

from ..sdk import DooServiceSDK
from .scheduler import BackupSchedulerProtocol

ProgressFn = Callable[[str, int], Awaitable[None]]


class JobContext(msgspec.Struct):
    args:      dict
    sdk:       DooServiceSDK
    progress:  ProgressFn
    scheduler: BackupSchedulerProtocol | None = None
