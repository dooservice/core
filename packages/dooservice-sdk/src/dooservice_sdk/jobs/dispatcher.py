from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
import time

from ..sdk import DooServiceSDK
from .context import JobContext
from .errors import UnknownJobKindError
from .registry import JOBS
from .scheduler import BackupSchedulerProtocol

log = logging.getLogger(__name__)

ReportProgressFn  = Callable[[str, str, int], Awaitable[None]]
ReportCompletedFn = Callable[[str, dict], Awaitable[None]]
ReportFailedFn    = Callable[[str, str], Awaitable[None]]


async def noop_progress(stage: str, pct: int) -> None:
    pass


class WorkflowDispatcher:
    def __init__(self, sdk: DooServiceSDK, scheduler: BackupSchedulerProtocol | None = None) -> None:
        self.sdk       = sdk
        self.scheduler = scheduler

    async def handle_sync(self, kind: str, args: dict) -> dict:
        handler_class = JOBS.get(kind)
        if handler_class is None:
            raise UnknownJobKindError(kind)
        ctx = JobContext(args=args, sdk=self.sdk, progress=noop_progress, scheduler=self.scheduler)
        return await handler_class().run(ctx)

    async def run(
        self,
        job_id:           str,
        kind:             str,
        args:             dict,
        on_progress:      ReportProgressFn,
        on_completed:     ReportCompletedFn,
        on_failed:        ReportFailedFn,
    ) -> None:
        handler_class = JOBS.get(kind)
        if handler_class is None:
            log.warning("No handler for job kind '%s'", kind)
            await on_failed(job_id, f"No handler for '{kind}'")
            return

        async def progress(stage: str, pct: int) -> None:
            await on_progress(job_id, stage, pct)
        ctx        = JobContext(args=args, sdk=self.sdk, progress=progress, scheduler=self.scheduler)
        started_at = time.monotonic()
        try:
            result = await handler_class().run(ctx)
            log.info("Job completed: %s (%.1fs)", kind, time.monotonic() - started_at)
            await on_completed(job_id, result)
        except Exception as error:
            log.error("Job failed: %s — %s", kind, error)
            await on_failed(job_id, str(error))
