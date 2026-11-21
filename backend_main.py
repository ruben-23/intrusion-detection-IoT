"""Backend FastAPI:
- server TCP pentru înregistrarea gateway-urilor și device-urilor
- subscriber MQTT (telemetry / alerts / heartbeat) -> bază de date
- REST + WebSocket
"""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import aiomqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from db import (Device, Gateway, Incident, Session, Telemetry,
                        init_db, utcnow)
from common import BACKEND_HOST, BACKEND_TCP_PORT, MQTT_HOST, MQTT_PORT, TOPIC_ROOT


# ---------------- Scheme Pydantic ----------------
class TelemetryPayload(BaseModel):
    mac_address: str = Field(..., max_length=17)
    timestamp: datetime
    total_packets: int
    total_bytes: int
    active_flows: int
    status: str


class IncidentPayload(BaseModel):
    mac_address: str = Field(..., max_length=17)
    timestamp: datetime
    predicted_class: str
    confidence_score: float
    action_taken: str
    inference_latency_ms: float
    forensic_features: Dict[str, Any]


class HeartbeatPayload(BaseModel):
    cpu_usage_pct: float
    ram_mb_used: float
    avg_inference_ms: float


class RegisterGateway(BaseModel):
    gateway_id: str = Field(..., max_length=50)


class RegisterDevice(BaseModel):
    gateway_id: str = Field(..., max_length=50)
    device_id: str = Field(..., max_length=50)
    mac_address: str = Field(..., max_length=17)
    device_type: Optional[str] = None


# ---------------- WebSocket manager ----------------
class WSManager:
    def __init__(self):
        self.clients: set[WebSocket] = set()

    async def broadcast(self, event: dict):
        message = jsonable_encoder(event)
        for ws in list(self.clients):
            try:
                await ws.send_json(message)
            except Exception:
                self.clients.discard(ws)


ws_manager = WSManager()


# ---------------- Înregistrare prin TCP ----------------
async def register(msg: dict) -> None:
    kind = msg.get("type")
    async with Session() as s:
        if kind == "register_gateway":
            p = RegisterGateway(**msg)
            await s.merge(Gateway(gateway_id=p.gateway_id, status="ONLINE",
                                  last_heartbeat=utcnow()))
            print(f"[Backend] Gateway înregistrat: {p.gateway_id}")
        elif kind == "register_device":
            p = RegisterDevice(**msg)
            if await s.get(Gateway, p.gateway_id) is None:
                raise ValueError(f"gateway necunoscut: {p.gateway_id}")
            await s.merge(Device(mac_address=p.mac_address, device_id=p.device_id,
                                 gateway_id=p.gateway_id, device_type=p.device_type,
                                 current_status="ACTIVE"))
            print(f"[Backend] Device înregistrat: {p.device_id} ({p.mac_address})")
        else:
            raise ValueError(f"tip necunoscut: {kind}")
        await s.commit()


async def handle_registration(reader, writer):
    try:
        while line := await reader.readline():
            try:
                await register(json.loads(line))
                reply = {"status": "ok"}
            except ValueError as exc:  # include JSONDecodeError și ValidationError
                reply = {"status": "error", "detail": str(exc)[:200]}
            writer.write((json.dumps(reply) + "\n").encode())
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        writer.close()


# ---------------- MQTT -> DB ----------------
async def handle_message(topic: str, raw: bytes) -> None:
    parts = topic.split("/")
    gateway_id, kind = parts[-2], parts[-1]
    event = None
    try:
        data = json.loads(raw)
        async with Session() as s:
            gw = await s.get(Gateway, gateway_id)
            if gw is None:
                print(f"[MQTT] Ignorat: gateway neînregistrat '{gateway_id}'")
                return

            if kind == "heartbeat":
                p = HeartbeatPayload(**data)
                gw.cpu_usage_pct, gw.ram_mb_used = p.cpu_usage_pct, p.ram_mb_used
                gw.avg_inference_ms = p.avg_inference_ms
                gw.last_heartbeat, gw.status = utcnow(), "ONLINE"

            elif kind in ("telemetry", "alerts"):
                p = (TelemetryPayload if kind == "telemetry" else IncidentPayload)(**data)
                dev = await s.get(Device, p.mac_address)
                if dev is None or dev.gateway_id != gateway_id:
                    print(f"[MQTT] Ignorat: device necunoscut {p.mac_address}")
                    return
                if kind == "telemetry":
                    s.add(Telemetry(**p.model_dump()))
                    if p.status == "BENIGN":
                        dev.current_status = "ACTIVE"
                else:
                    s.add(Incident(**p.model_dump()))
                    dev.current_status = "ISOLATED"
                    event = {"type": "incident", "device_id": dev.device_id,
                             **p.model_dump(exclude={"forensic_features"})}
                    print(f"[MQTT] INCIDENT {dev.device_id}: {p.predicted_class} "
                          f"({p.confidence_score})")
            else:
                return
            await s.commit()
        if event:
            await ws_manager.broadcast(event)
    except ValueError as exc:
        print(f"[MQTT] Mesaj invalid pe {topic}: {str(exc)[:150]}")


async def mqtt_worker():
    while True:
        try:
            async with aiomqtt.Client(MQTT_HOST, MQTT_PORT) as client:
                for kind in ("telemetry", "alerts", "heartbeat"):
                    await client.subscribe(f"{TOPIC_ROOT}/+/{kind}", qos=1)
                print(f"[MQTT] Conectat la {MQTT_HOST}:{MQTT_PORT}, topic root '{TOPIC_ROOT}'")
                async for message in client.messages:
                    await handle_message(str(message.topic), message.payload)
        except aiomqtt.MqttError as exc:
            print(f"[MQTT] Eroare: {exc}. Reîncerc în 3s...")
            await asyncio.sleep(3)


async def offline_watcher():
    """Marchează gateway-urile fără heartbeat de 20s ca OFFLINE."""
    while True:
        await asyncio.sleep(10)
        async with Session() as s:
            await s.execute(update(Gateway)
                            .where(Gateway.last_heartbeat < utcnow() - timedelta(seconds=20))
                            .values(status="OFFLINE"))
            await s.commit()


# ---------------- Aplicația ----------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    tcp = await asyncio.start_server(handle_registration, BACKEND_HOST, BACKEND_TCP_PORT)
    print(f"[Backend] Server TCP înregistrare pe {BACKEND_HOST}:{BACKEND_TCP_PORT}")
    tasks = [asyncio.create_task(mqtt_worker()), asyncio.create_task(offline_watcher())]
    yield
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    tcp.close()
    await tcp.wait_closed()


app = FastAPI(title="IoT IDS Backend", lifespan=lifespan)


def to_dict(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


async def list_rows(model, order_col, limit: int, mac: Optional[str] = None):
    q = select(model).order_by(order_col.desc()).limit(min(limit, 1000))
    if mac:
        q = q.where(model.mac_address == mac)
    async with Session() as s:
        return [to_dict(r) for r in (await s.scalars(q)).all()]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/gateways")
async def gateways():
    async with Session() as s:
        return [to_dict(r) for r in (await s.scalars(select(Gateway))).all()]


@app.get("/api/devices")
async def devices():
    async with Session() as s:
        return [to_dict(r) for r in (await s.scalars(select(Device))).all()]


@app.get("/api/telemetry")
async def telemetry(limit: int = 50, mac: Optional[str] = None):
    return await list_rows(Telemetry, Telemetry.timestamp, limit, mac)


@app.get("/api/incidents")
async def incidents(limit: int = 50, mac: Optional[str] = None):
    return await list_rows(Incident, Incident.timestamp, limit, mac)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_manager.clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # menține conexiunea deschisă
    except WebSocketDisconnect:
        ws_manager.clients.discard(ws)
