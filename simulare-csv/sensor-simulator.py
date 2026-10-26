
import asyncio
import csv
import json
from datetime import datetime, timezone

# Configuration
GATEWAY_HOST = "127.0.0.1"
GATEWAY_PORT = 5050
DATA_FILE = "DOS-HTTP_Flood.pcap.csv"

DEVICE_IDS = ["DEV-01", "DEV-02", "DEV-03"]
SEND_INTERVAL = 1  # Seconds between readings


def load_dataset():
    """Load CSV rows and convert numeric fields to numbers."""
    rows = []

    with open(DATA_FILE, "r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        for row in reader:
            reading = {}

            for key, value in row.items():
                if value is None or value.strip() == "":
                    reading[key] = None
                    continue

                try:
                    reading[key] = float(value)
                except ValueError:
                    reading[key] = value

            rows.append(reading)

    if not rows:
        raise ValueError("The CSV contains no data rows.")

    return rows


async def simulate_device(device_id, rows, delay=SEND_INTERVAL):
    """Simulate a sensor that streams CSV readings to the gateway."""
    reader, writer = None, None

    try:
        reader, writer = await asyncio.open_connection(
            GATEWAY_HOST, GATEWAY_PORT
        )

        print(f"[{device_id}] Connected to gateway.")

        for sequence, row in enumerate(rows, start=1):
            payload = {
                "device_id": device_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sequence": sequence,
                "data": row,
            }

            message = json.dumps(payload) + "\n"

            writer.write(message.encode("utf-8"))
            await writer.drain()

            print(
                f"[{device_id}] Sent reading {sequence}: "
                f"Rate={row.get('Rate')}"
            )

            await asyncio.sleep(delay)

        print(f"[{device_id}] Finished sending data.")

    except (ConnectionRefusedError, OSError) as exc:
        print(f"[{device_id}] Gateway connection error: {exc}")

    finally:
        if writer is not None:
            writer.close()
            await writer.wait_closed()


async def main():
    try:
        rows = load_dataset()
    except (OSError, ValueError, csv.Error) as exc:
        print(f"Dataset error: {exc}")
        return

    print(f"Loaded {len(rows)} CSV readings.")
    print(f"Starting {len(DEVICE_IDS)} simulated sensors.")

    rows = rows[:100]

    # Give each device its own partition of the dataset.
    tasks = [
        simulate_device(device_id, rows[i::len(DEVICE_IDS)])
        for i, device_id in enumerate(DEVICE_IDS)
    ]

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
