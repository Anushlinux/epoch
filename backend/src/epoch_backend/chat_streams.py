"""Bounded public chat previews. Saved conversation messages remain authoritative."""

import asyncio
import json
import threading
from collections import OrderedDict, deque
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse


class ChatStreams:
    def __init__(self):
        self.lock = threading.Lock()
        self.entries = OrderedDict()

    def start(self, chat_id, operation_id):
        with self.lock:
            key = (str(chat_id), str(operation_id))
            self.entries[key] = {
                "sequence": 0, "events": deque(maxlen=512),
                "state": {"text": "", "stage": "starting", "activity": "Starting Hermes",
                          "status": "running", "block": 0, "truncated": False, "saved": False},
            }
            while len(self.entries) > 16:
                self.entries.popitem(last=False)

    def publish(self, chat_id, operation_id, kind, **data):
        with self.lock:
            key = (str(chat_id), str(operation_id))
            entry = self.entries.get(key)
            if entry is None or entry["state"]["status"] != "running":
                return
            state = entry["state"]
            if kind == "answer_delta":
                text = data["text"]
                remaining = max(0, 128000 - len(state["text"]))
                data = {"text": text[:remaining], "block": state["block"]}
                state["text"] += data["text"]
                state["truncated"] = state["truncated"] or len(text) > remaining
                data["truncated"] = state["truncated"]
            elif kind == "answer_reset":
                state.update(text="", block=state["block"] + 1, truncated=False)
                data = {"block": state["block"]}
            elif kind in {"stage", "complete"}:
                state.update(data)
            entry["sequence"] += 1
            entry["events"].append({"chat_id": key[0], "operation_id": key[1],
                                    "sequence": entry["sequence"], "type": kind, "data": data})

    def read(self, chat_id, operation_id, cursor=None):
        with self.lock:
            key = (str(chat_id), str(operation_id))
            entry = self.entries.get(key)
            if entry is None:
                return None
            events = entry["events"]
            if cursor is None or (events and cursor < events[0]["sequence"] - 1):
                return [{"chat_id": key[0], "operation_id": key[1],
                         "sequence": entry["sequence"], "type": "snapshot",
                         "data": dict(entry["state"])}]
            return [event for event in events if event["sequence"] > cursor]


def chat_stream_router(service):
    router = APIRouter(tags=["chat"])

    @router.get("/api/chats/{chat_id}/operations/{operation_id}/events")
    async def events(chat_id: UUID, operation_id: UUID, request: Request):
        # Use the same conversation/operation boundary as ordinary chat reads.
        operation = await asyncio.to_thread(service.operation, chat_id, operation_id)

        async def stream():
            cursor = None
            idle = 0
            while not await request.is_disconnected():
                frames = service.streams.read(chat_id, operation_id, cursor)
                if frames is None:
                    # After a restart/eviction, read the durable result; never replay work.
                    current = await asyncio.to_thread(service.operation, chat_id, operation_id)
                    frame = {"chat_id": str(chat_id), "operation_id": str(operation_id),
                             "sequence": 0, "type": "unavailable", "data": {
                                 "status": current.status,
                                 "message": "Live preview unavailable; read the saved conversation.",
                             }}
                    yield f"event: unavailable\ndata: {json.dumps(frame)}\n\n"
                    return
                for frame in frames:
                    cursor = frame["sequence"]
                    yield (f"id: {cursor}\nevent: {frame['type']}\n"
                           f"data: {json.dumps(frame)}\n\n")
                    if frame["data"].get("status", "running") != "running":
                        return
                if operation.kind != "chat":
                    return
                idle += 1
                if idle % 150 == 0:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.1)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={
            "Cache-Control": "no-store", "X-Accel-Buffering": "no",
        })

    return router
