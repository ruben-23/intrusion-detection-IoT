"""Simulator de senzori:
- DEV-01 preia trafic malițios din DOS-HTTP_Flood.pcap.csv
- DEV-02 preia trafic malițios din DDoS-SYN_Flood.pcap.csv
- ambele alternează faze de trafic benign sintetic cu faze de atac
- la pornire fiecare device se înregistrează la gateway prin TCP
"""
import asyncio
import csv
import json
import random
from datetime import datetime, timezone

from common import FEATURE_COLUMNS, GATEWAY_HOST, GATEWAY_PORT

SEND_INTERVAL = 1.0        # secunde între citiri (1 rând = 1 flow de 1s)
MAX_ATTACK_ROWS = 1000     # câte rânduri citim din fiecare CSV

DEVICES = [
    {"device_id": "DEV-01", "mac_address": "02:1A:2B:3C:4D:01",
     "device_type": "IP_Camera", "attack_file": "DOS-HTTP_Flood.pcap.csv"},
    {"device_id": "DEV-02", "mac_address": "02:1A:2B:3C:4D:02",
     "device_type": "Smart_Thermostat", "attack_file": "DDoS-SYN_Flood.pcap.csv"},
]


def load_attack_rows(path: str) -> list[dict]:
    rows = []
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        for raw in csv.DictReader(f):
            raw = {k.strip(): v for k, v in raw.items() if k}
            row = {}
            for col in FEATURE_COLUMNS:
                try:
                    row[col] = float(raw.get(col) or 0.0)
                except ValueError:
                    row[col] = 0.0
            rows.append(row)
            if len(rows) >= MAX_ATTACK_ROWS:
                break
    if not rows:
        raise ValueError(f"{path} nu conține rânduri")
    return rows


def benign_row() -> dict:
    """Flow benign sintetic: rată mică, flag-uri RST aproape zero, IAT mare."""
    n = random.randint(5, 60)                       # pachete în fereastra de 1s
    avg = random.uniform(70, 600)                   # dimensiune medie pachet
    mx = avg + random.uniform(50, 800)
    ack = random.randint(n // 2, n)
    syn = random.randint(0, 2)
    fin = random.randint(0, 1)
    rst = random.choice([0, 0, 0, 1])
    web = random.choice(["HTTP", "HTTPS", "HTTPS"])

    row = dict.fromkeys(FEATURE_COLUMNS, 0.0)
    row.update({
        "Header_Length": round(random.uniform(20, 40), 2),
        "Protocol Type": 6.0,
        "Time_To_Live": random.choice([64.0, 128.0]),
        "Rate": round(random.uniform(1, 80), 3),
        "fin_flag_number": round(fin / n, 2),
        "syn_flag_number": round(syn / n, 2),
        "rst_flag_number": round(rst / n * 0.2, 2),
        "psh_flag_number": round(random.uniform(0.1, 0.5), 2),
        "ack_flag_number": round(ack / n, 2),
        "ack_count": ack, "syn_count": syn, "fin_count": fin, "rst_count": rst,
        web: 1.0, "TCP": 1.0, "IPv": 1.0, "LLC": 1.0,
        "Tot sum": round(n * avg), "Min": 54.0, "Max": round(mx, 1),
        "AVG": round(avg, 2), "Std": round(random.uniform(10, 200), 3),
        "Tot size": round(avg, 2), "IAT": round(random.uniform(0.02, 1.0), 4),
        "Number": float(n), "Variance": round(random.uniform(100, 5000), 2),
    })
    return row


def traffic_stream(attack_rows: list[dict]):
    """Generator infinit: faze benign (15-25 citiri) alternate cu atac (10-15 citiri)."""
    idx = 0
    while True:
        for _ in range(random.randint(15, 25)):
            yield "benign", benign_row()
        for _ in range(random.randint(10, 15)):
            yield "ATAC", dict(attack_rows[idx % len(attack_rows)])
            idx += 1


async def send(writer, msg: dict) -> None:
    writer.write((json.dumps(msg) + "\n").encode())
    await writer.drain()


async def register(reader, writer, dev: dict) -> bool:
    await send(writer, {"type": "register", "device_id": dev["device_id"],
                        "mac_address": dev["mac_address"], "device_type": dev["device_type"]})
    reply = json.loads(await asyncio.wait_for(reader.readline(), timeout=10))
    return reply.get("status") == "ok"


async def run_device(dev: dict) -> None:
    name = dev["device_id"]
    try:
        attack_rows = load_attack_rows(dev["attack_file"])
    except (OSError, ValueError, csv.Error) as exc:
        print(f"[{name}] Eroare dataset: {exc}")
        return
    print(f"[{name}] {len(attack_rows)} rânduri de atac încărcate din {dev['attack_file']}")

    stream = traffic_stream(attack_rows)
    sequence = 0
    while True:
        writer = None
        try:
            reader, writer = await asyncio.open_connection(GATEWAY_HOST, GATEWAY_PORT)
            if not await register(reader, writer, dev):
                print(f"[{name}] Înregistrare eșuată (backend pornit?). Reîncerc în 3s...")
                await asyncio.sleep(3)
                continue
            print(f"[{name}] Înregistrat ({dev['mac_address']}). Încep transmisia.")

            while True:
                kind, row = next(stream)
                sequence += 1
                await send(writer, {
                    "type": "reading", "device_id": name, "mac_address": dev["mac_address"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "sequence": sequence, "data": row,
                })
                print(f"[{name}] #{sequence} {kind:6s} Rate={row['Rate']:.1f}")
                await asyncio.sleep(SEND_INTERVAL)
        except (OSError, asyncio.TimeoutError, ValueError) as exc:
            print(f"[{name}] Eroare conexiune: {exc}. Reîncerc în 3s...")
            await asyncio.sleep(3)
        finally:
            if writer is not None:
                writer.close()


async def main():
    await asyncio.gather(*(run_device(d) for d in DEVICES))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Simulator] Oprit.")
