from __future__ import annotations

import msgspec

# ── Async jobs — Orchestrator → Agent (JetStream) ────────────────────────────

class JobSubmit(msgspec.Struct):
    job_id: str
    kind:   str
    args:   dict


# ── Sync queries — Orchestrator → Agent (Core NATS request-reply) ────────────

class QueryRequest(msgspec.Struct):
    kind: str
    args: dict


class QueryResponse(msgspec.Struct):
    ok:    bool
    data:  dict | None = None
    error: str  | None = None


# ── Async results — Agent → Orchestrator (JetStream) ─────────────────────────

class JobProgress(msgspec.Struct):
    job_id: str
    stage:  str
    pct:    int


class JobCompleted(msgspec.Struct):
    job_id: str
    result: dict


class JobFailed(msgspec.Struct):
    job_id: str
    error:  str


class AgentHeartbeat(msgspec.Struct):
    agent_id:          str
    region:            str
    base_domain:       str          = ""
    secondary_domains: list[str]    = msgspec.field(default_factory=list)
    uptime_seconds:    int          = 0
    last_backup_at:    str | None   = None
    last_backup_ok:    bool | None  = None
    cpu_percent:       float | None = None
    mem_percent:       float | None = None
    mem_used_gb:       float | None = None
    mem_total_gb:      float | None = None
    disk_used_gb:      float | None = None
    disk_total_gb:     float | None = None


AgentResult = JobProgress | JobCompleted | JobFailed
