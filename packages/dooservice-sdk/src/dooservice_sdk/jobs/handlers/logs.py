from __future__ import annotations

from uuid import UUID

import msgspec

from dooservice_protocol import EnvLogsArgs

from ..context import JobContext


class EnvLogs:
    async def run(self, ctx: JobContext) -> dict:
        args = msgspec.convert(ctx.args, EnvLogsArgs)
        env  = await ctx.sdk.environments.get(UUID(args.environment_id))
        if not env.container_id:
            return {"logs": "", "lines": 0}
        output = await ctx.sdk.docker.read_logs(env.container_id, tail=args.tail)
        return {"logs": output, "lines": output.count("\n")}
