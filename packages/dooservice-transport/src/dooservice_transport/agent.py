from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import logging
from typing import Any

import msgspec
import nats
import nats.js

from . import subjects
from .protocol.messages import (
    AgentHeartbeat,
    JobCompleted,
    JobFailed,
    JobProgress,
    JobSubmit,
    QueryRequest,
    QueryResponse,
)

log = logging.getLogger(__name__)

AsyncJobHandler  = Callable[[JobSubmit], Coroutine[Any, Any, None]]
SyncQueryHandler = Callable[[str, dict], Awaitable[dict]]


class AgentTransport:
    def __init__(
        self,
        nats_url:          str,
        agent_id:          str,
        region:            str,
        user:              str       = "",
        password:          str       = "",
        base_domain:       str       = "",
        secondary_domains: list[str] = [],
    ) -> None:
        self.nats_url          = nats_url
        self.agent_id          = agent_id
        self.region            = region
        self.base_domain       = base_domain
        self.secondary_domains = secondary_domains
        self.user     = user
        self.password = password
        self.nc: nats.NATS | None                = None
        self.js: nats.js.JetStreamContext | None  = None

    async def connect(self) -> None:
        nc = await nats.connect(
            self.nats_url,
            user=self.user or None,
            password=self.password or None,
            reconnect_time_wait=2,
            max_reconnect_attempts=-1,
            error_cb=self._on_error,
            disconnected_cb=self._on_disconnect,
            reconnected_cb=self._on_reconnect,
        )
        self.nc = nc
        self.js = nc.jetstream()
        log.info("Agent %s connected to NATS", self.agent_id)

    async def close(self) -> None:
        if self.nc:
            await self.nc.drain()

    async def start(self, async_handler: AsyncJobHandler, sync_handler: SyncQueryHandler) -> None:
        assert self.nc is not None
        assert self.js is not None

        pending_jobs: set[asyncio.Task] = set()

        async def on_async_job(msg: nats.Msg) -> None:
            job = msgspec.json.decode(msg.data, type=JobSubmit)
            await msg.ack()
            task = asyncio.create_task(async_handler(job))
            pending_jobs.add(task)
            task.add_done_callback(pending_jobs.discard)

        async def on_sync_query(msg: nats.Msg) -> None:
            query = msgspec.json.decode(msg.data, type=QueryRequest)
            try:
                data = await sync_handler(query.kind, query.args)
                await msg.respond(msgspec.json.encode(QueryResponse(ok=True, data=data)))
            except Exception as error:
                await msg.respond(msgspec.json.encode(QueryResponse(ok=False, error=str(error))))

        region_consumer = f"workers-{self.region}"
        agent_consumer  = f"agent-{self.agent_id}"

        await self.js.subscribe(
            subjects.job_inbox(self.region),
            queue=region_consumer,
            durable=region_consumer,
            cb=on_async_job,
        )
        await self.js.subscribe(
            subjects.job_inbox_agent(self.agent_id),
            durable=agent_consumer,
            cb=on_async_job,
        )
        await self.nc.subscribe(subjects.query_inbox(self.region), cb=on_sync_query)
        await self.nc.subscribe(subjects.query_inbox_agent(self.agent_id), cb=on_sync_query)

        log.info("Agent %s ready (region=%s)", self.agent_id, self.region)

    async def report_progress(self, job_id: str, stage: str, pct: int) -> None:
        assert self.js is not None
        await self.js.publish(subjects.job_progress(job_id), msgspec.json.encode(JobProgress(job_id=job_id, stage=stage, pct=pct)))

    async def report_completed(self, job_id: str, result: dict) -> None:
        assert self.js is not None
        await self.js.publish(subjects.job_completed(job_id), msgspec.json.encode(JobCompleted(job_id=job_id, result=result)))

    async def report_failed(self, job_id: str, error: str) -> None:
        assert self.js is not None
        await self.js.publish(subjects.job_failed(job_id), msgspec.json.encode(JobFailed(job_id=job_id, error=error)))

    async def send_heartbeat(
        self,
        uptime_seconds: int          = 0,
        last_backup_at: str | None   = None,
        last_backup_ok: bool | None  = None,
        cpu_percent:    float | None = None,
        mem_percent:    float | None = None,
        mem_used_gb:    float | None = None,
        mem_total_gb:   float | None = None,
        disk_used_gb:   float | None = None,
        disk_total_gb:  float | None = None,
    ) -> None:
        assert self.nc is not None
        await self.nc.publish(
            subjects.agent_heartbeat(self.agent_id),
            msgspec.json.encode(AgentHeartbeat(
                agent_id=self.agent_id,
                region=self.region,
                base_domain=self.base_domain,
                secondary_domains=self.secondary_domains,
                uptime_seconds=uptime_seconds,
                last_backup_at=last_backup_at,
                last_backup_ok=last_backup_ok,
                cpu_percent=cpu_percent,
                mem_percent=mem_percent,
                mem_used_gb=mem_used_gb,
                mem_total_gb=mem_total_gb,
                disk_used_gb=disk_used_gb,
                disk_total_gb=disk_total_gb,
            )),
        )

    async def _on_error(self, error: Exception) -> None:
        log.error("NATS error on agent %s: %s", self.agent_id, error)

    async def _on_disconnect(self) -> None:
        log.warning("Agent %s disconnected from NATS", self.agent_id)

    async def _on_reconnect(self) -> None:
        log.info("Agent %s reconnected to NATS", self.agent_id)
