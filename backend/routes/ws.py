import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.event_bus import event_bus
from backend.utils.logging import get_logger

router = APIRouter(tags=["websocket"])
logger = get_logger(__name__)


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    await websocket.accept()
    queue = await event_bus.subscribe()

    for event in event_bus.recent(30):
        await websocket.send_json(event)

    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("ws.events_error", error=str(exc))
    finally:
        await event_bus.unsubscribe(queue)
