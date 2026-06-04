from __future__ import annotations

import logging
import uuid

import msgspec
import nats
import nats.js
from nats.js.api import RetentionPolicy, StorageType, StreamConfig

from . import subjects
from .errors import AgentError
from .protocol.messages import JobSubmit, QueryRequest, QueryResponse
from .subjects import JOBS_STREAM, RESULTS_STREAM

log = logging.getLogger(__name__)


class OrchestratorTransport:
    def __init__(
        self,
        nats_url:    str,
        nats_ws_url: str = "",
        user:        str = "",
        password:    str = "",
    ) -> None:
        self.nats_url    = nats_url
        self.nats_ws_url = nats_ws_url
        self.user        = user
        self.password    = password
        self.nc: nats.NATS | None               = None
        self.js: nats.js.JetStreamContext | None = None

    async def connect(self) -> None:
        self.nc = await nats.connect(
            self.nats_url,
            user=self.user or None,
            password=self.password or None,
        )
        self.js = self.nc.jetstream()
        await self._provision_streams()
        log.info("OrchestratorTransport connected at %s", self.nats_url)

    async def close(self) -> None:
        if self.nc:
            await self.nc.drain()

    async def request(self, region: str, kind: str, args: dict, timeout: int = 30) -> dict:
        assert self.nc is not None
        payload  = msgspec.json.encode(QueryRequest(kind=kind, args=args))
        raw      = await self.nc.request(subjects.query_inbox(region), payload, timeout=timeout)
        response = msgspec.json.decode(raw.data, type=QueryResponse)
        if not response.ok:
            raise AgentError(response.error or "unknown agent error")
        return response.data or {}

    async def request_agent(self, agent_id: str, kind: str, args: dict, timeout: int = 30) -> dict:
        assert self.nc is not None
        payload  = msgspec.json.encode(QueryRequest(kind=kind, args=args))
        raw      = await self.nc.request(subjects.query_inbox_agent(agent_id), payload, timeout=timeout)
        response = msgspec.json.decode(raw.data, type=QueryResponse)
        if not response.ok:
            raise AgentError(response.error or "unknown agent error")
        return response.data or {}

    async def dispatch(self, region: str, kind: str, args: dict) -> str:
        """Fire-and-forget async job to any agent in region."""
        assert self.js is not None
        job_id = str(uuid.uuid4())
        await self.js.publish(subjects.job_inbox(region), msgspec.json.encode(JobSubmit(job_id=job_id, kind=kind, args=args)))
        return job_id

    async def dispatch_to_agent(self, agent_id: str, kind: str, args: dict) -> str:
        """Fire-and-forget async job to a specific agent."""
        assert self.js is not None
        job_id = str(uuid.uuid4())
        await self.js.publish(subjects.job_inbox_agent(agent_id), msgspec.json.encode(JobSubmit(job_id=job_id, kind=kind, args=args)))
        return job_id

    async def _provision_streams(self) -> None:
        assert self.js is not None
        streams = [
            StreamConfig(name=JOBS_STREAM,    subjects=["jobs.>"],    retention=RetentionPolicy.WORK_QUEUE, storage=StorageType.FILE),
            StreamConfig(name=RESULTS_STREAM, subjects=["results.>"], retention=RetentionPolicy.LIMITS,     storage=StorageType.FILE),
        ]
        for config in streams:
            try:
                await self.js.stream_info(config.name)
            except nats.js.errors.NotFoundError:
                await self.js.add_stream(config=config)
