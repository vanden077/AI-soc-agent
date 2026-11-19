import asyncio
import base64
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.services import JobProgressService
from src.api.websocket import WebSocketConnectionManager

logger = logging.getLogger(__name__)

rt_threat_analysis_progress = APIRouter(tags=["Threat Analysis WebSocket"])

_READ_ONLY_NOTICE = {
    "notice": base64.b64decode(
        "TmljZSB0cnksIEkgd2Fzbid0IGJvcm4geWVzdGVyZGF5IOKAlCB5b3UnbGwgaGF2ZSB0byBiZSBzbWFydGVyIHRoYW4gdGhhdCA7KSAocmVhZC1vbmx5IGNoYW5uZWwp"
    ).decode("utf-8")
}


@rt_threat_analysis_progress.websocket("/threat_analyzer/progress")
async def stream_job_progress(websocket: WebSocket) -> None:
    """
    Read-only server-push WebSocket endpoint streaming real-time forensic job
    progress snapshots (processed / total).
    """
    ws_manager: WebSocketConnectionManager = websocket.state.ws_manager
    progress_service: JobProgressService = websocket.state.progress_service

    await ws_manager.connect(websocket)
    try:
        initial_snapshot = await asyncio.to_thread(progress_service.get_snapshot)
        await websocket.send_json(initial_snapshot)
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            await websocket.send_json(_READ_ONLY_NOTICE)
    except WebSocketDisconnect:
        logger.debug("[WS ROUTER] Client disconnected from job progress stream.")
    finally:
        ws_manager.disconnect(websocket)
