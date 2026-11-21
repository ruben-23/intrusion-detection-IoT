"""Edge Gateway:
1. La pornire se înregistrează la backend (TCP).
2. Primește de la device-uri (TCP): înregistrare + citiri, le forward-ează la backend la înregistrare.
3. Rulează modelul AI simulat pe fiecare citire.
4. Publică pe broker MQTT: telemetry (fiecare citire), alerts (doar atacuri), heartbeat (la 5s).
"""
import asyncio
import json
import os
import time
from collections import deque
from datetime import datetime, timezone

import aiomqtt
import psutil

from common import (BACKEND_HOST, BACKEND_TCP_PORT, GATEWAY_HOST, GATEWAY_ID,
                    GATEWAY_PORT, MQTT_HOST, MQTT_PORT, TOPIC_ROOT)
from model import MockIDS

ids_model = MockIDS(threshold=0.5)
mqtt_queue: asyncio.Queue = asyncio.Queue(maxsize=5000)
known_macs: set[str] = set()
latencies = deque(maxlen=100)
process = psutil.Process(os.getpid())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def publish(kind: str, payload: dict) -> None:
    try:
        mqtt_queue.put_nowait((f"{TOPIC_ROOT}/{GATEWAY_ID}/{kind}", payload))
    except asyncio.QueueFull:
        print("[Gateway] Coada MQTT plină, mesaj aruncat")


# ---------------- Comunicare TCP cu backend-ul ----------------
async def backend_rpc(msg: dict) -> dict:
    reader, writer = await asyncio.open_connection(BACKEND_HOST, BACKEND_TCP_PORT)
    try:
        writer.write((json.dumps(msg) + "\n").encode())
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=5)
        return json.loads(line)
    finally:
        writer.close()


async def register_gateway() -> None:
    while True:
        try:
            reply = await backend_rpc({"type": "register_gateway", "gateway_id": GATEWAY_ID})
            if reply.get("status") == "ok":
                print(f"[Gateway] Înregistrat la backend ca '{GATEWAY_ID}'")
                return
            print(f"[Gateway] Înregistrare refuzată: {reply}")
        except (OSError, asyncio.TimeoutError, ValueError) as exc:
            print(f"[Gateway] Backend indisponibil ({exc}). Reîncerc în 2s...")
        await asyncio.sleep(2)


async def register_device(msg: dict) -> dict:
    try:
        reply = await backend_rpc({
            "type": "register_device", "gateway_id": GATEWAY_ID,
            "device_id": msg.get("device_id"), "mac_address": msg.get("mac_address"),
            "device_type": msg.get("device_type"),
        })
    except (OSError, asyncio.TimeoutError, ValueError) as exc:
        return {"status": "error", "detail": f"backend indisponibil: {exc}"}
    if reply.get("status") == "ok":
        known_macs.add(msg["mac_address"])
        print(f"[Gateway] Device înregistrat: {msg['device_id']} ({msg['mac_address']})")
    return reply


# ---------------- Procesare citiri ----------------
def process_reading(msg: dict) -> None:
    mac, features = msg.get("mac_address"), msg.get("data")
    if mac not in known_macs or not isinstance(features, dict):
        print(f"[Gateway] Citire ignorată (device neînregistrat sau format invalid): {mac}")
        return

    features = {k: (0 if v is None else v) for k, v in features.items()}

    t0 = time.perf_counter()
    label, confidence = ids_model.predict(features)
    latency_ms = round((time.perf_counter() - t0) * 1000, 4)
    latencies.append(latency_ms)

    malicious = label != "Benign"
    timestamp = msg.get("timestamp") or now_iso()

    publish("telemetry", {
        "mac_address": mac,
        "timestamp": timestamp,
        "total_packets": int(features.get("Number", 0)),
        "total_bytes": int(features.get("Tot sum", 0)),
        # active_flows nu există în dataset -> estimat din contoarele TCP
        "active_flows": max(1, int(features.get("syn_count", 0) + features.get("fin_count", 0)
                                   + features.get("rst_count", 0))),
        "status": "MALICIOUS" if malicious else "BENIGN",
    })

    if malicious:
        publish("alerts", {
            "mac_address": mac,
            "timestamp": timestamp,
            "predicted_class": label,
            "confidence_score": confidence,
            "action_taken": "DROP_AND_ISOLATE",
            "inference_latency_ms": latency_ms,
            "forensic_features": {**features, "device_id": msg.get("device_id"),
                                  "sequence": msg.get("sequence")},
        })
        print(f"[Gateway] ALERTĂ {msg.get('device_id')}: {label} (conf={confidence})")


async def handle_client(reader, writer):
    peer = writer.get_extra_info("peername")
    print(f"[Gateway] Conectat: {peer}")
    try:
        while line := await reader.readline():
            try:
                msg = json.loads(line)
            except ValueError:
                print(f"[Gateway] JSON invalid de la {peer}")
                continue
            if not isinstance(msg, dict):
                continue

            if msg.get("type") == "register":
                reply = await register_device(msg)
                writer.write((json.dumps(reply) + "\n").encode())
                await writer.drain()
            elif msg.get("type") == "reading":
                process_reading(msg)
    except (ConnectionResetError, BrokenPipeError) as exc:
        print(f"[Gateway] Conexiune întreruptă: {exc}")
    finally:
        writer.close()
        print(f"[Gateway] Deconectat: {peer}")


# ---------------- MQTT ----------------
async def mqtt_publisher():
    while True:
        try:
            async with aiomqtt.Client(MQTT_HOST, MQTT_PORT) as client:
                print(f"[Gateway] Conectat la broker {MQTT_HOST}:{MQTT_PORT}")
                while True:
                    topic, payload = await mqtt_queue.get()
                    await client.publish(topic, json.dumps(payload), qos=1)
        except aiomqtt.MqttError as exc:
            print(f"[Gateway] Eroare MQTT: {exc}. Reîncerc în 3s...")
            await asyncio.sleep(3)


async def heartbeat_loop():
    psutil.cpu_percent(None)
    while True:
        await asyncio.sleep(5)
        publish("heartbeat", {
            "cpu_usage_pct": psutil.cpu_percent(None),
            "ram_mb_used": round(process.memory_info().rss / 1e6, 1),
            "avg_inference_ms": round(sum(latencies) / len(latencies), 4) if latencies else 0.0,
        })


async def main():
    await register_gateway()
    tasks = [asyncio.create_task(mqtt_publisher()), asyncio.create_task(heartbeat_loop())]
    server = await asyncio.start_server(handle_client, GATEWAY_HOST, GATEWAY_PORT,
                                        limit=64 * 1024)
    print(f"[Gateway] Ascult device-uri pe {GATEWAY_HOST}:{GATEWAY_PORT}")
    try:
        async with server:
            await server.serve_forever()
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Gateway] Oprit.")
