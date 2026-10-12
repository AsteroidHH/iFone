import asyncio
import json
import time
from typing import Optional
from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from app.auth import get_auth_context, AuthContext
from app.services.event_bus import event_bus

router = APIRouter()


@router.get("/events")
async def sse_events(
    last_event_id: Optional[int] = Header(None, alias="Last-Event-ID"),
    query_last_id: Optional[int] = Query(None, alias="last_event_id"),
    auth: AuthContext = Depends(get_auth_context),
):
    effective_last_id = last_event_id if last_event_id is not None else query_last_id
    buf = event_bus.get_tenant_buffer(auth.tenant)

    async def event_generator():
        # Check re-sync
        if effective_last_id is not None:
            missed = buf.get_events_since(effective_last_id)
            if missed is None:
                yield f"event: resync_required\ndata: {{}}\n\n"
            else:
                for ev in missed:
                    yield f"id: {ev.seq}\nevent: {ev.type}\ndata: {json.dumps(ev.model_dump())}\n\n"

        queue = buf.subscribe()
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"id: {ev.seq}\nevent: {ev.type}\ndata: {json.dumps(ev.model_dump())}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat
                    now_ms = int(time.time() * 1000)
                    yield f"event: heartbeat\ndata: {{\"ts\": {now_ms}}}\n\n"
        finally:
            buf.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
