from __future__ import annotations

JOBS_STREAM    = "JOBS"
RESULTS_STREAM = "RESULTS"

# ── Async jobs (JetStream — at-least-once, queue group) ──────────────────────

def job_inbox(region: str) -> str:
    return f"jobs.region.{region}"


def job_inbox_agent(agent_id: str) -> str:
    return f"jobs.agent.{agent_id}"


# ── Sync queries (Core NATS — request-reply) ──────────────────────────────────

def query_inbox(region: str) -> str:
    return f"query.region.{region}"


def query_inbox_agent(agent_id: str) -> str:
    return f"query.agent.{agent_id}"


# ── Results (JetStream — async jobs only) ────────────────────────────────────

def job_results(job_id: str) -> str:
    return f"results.{job_id}.>"


def job_progress(job_id: str) -> str:
    return f"results.{job_id}.progress"


def job_completed(job_id: str) -> str:
    return f"results.{job_id}.completed"


def job_failed(job_id: str) -> str:
    return f"results.{job_id}.failed"


# ── Heartbeat ─────────────────────────────────────────────────────────────────

def agent_heartbeat(agent_id: str) -> str:
    return f"agents.{agent_id}.heartbeat"
