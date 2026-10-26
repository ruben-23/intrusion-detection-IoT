
import asyncio
import json
import csv
import os

HOST = "127.0.0.1"
PORT = 5050

QUEUE_MAXSIZE = 1000
OUTPUT_FILE = "gateway_received_data.csv"

# Original CIC IoT dataset feature columns
FEATURE_COLUMNS = [
    "Header_Length", "Protocol Type", "Time_To_Live", "Rate",
    "fin_flag_number", "syn_flag_number", "rst_flag_number",
    "psh_flag_number", "ack_flag_number", "ece_flag_number",
    "cwr_flag_number", "ack_count", "syn_count", "fin_count",
    "rst_count", "HTTP", "HTTPS", "DNS", "Telnet", "SMTP",
    "SSH", "IRC", "TCP", "UDP", "DHCP", "ARP", "ICMP",
    "IGMP", "IPv", "LLC", "Tot sum", "Min", "Max", "AVG",
    "Std", "Tot size", "IAT", "Number", "Variance"
]

CSV_COLUMNS = [
    "device_id", "timestamp", "sequence"
] + FEATURE_COLUMNS


def initialize_csv():
    """Create the output CSV and header if it doesn't exist."""
    if not os.path.exists(OUTPUT_FILE) or os.path.getsize(OUTPUT_FILE) == 0:
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
            writer.writeheader()

        print(f"[Gateway] Created CSV: {OUTPUT_FILE}")


def save_reading(payload):
    """Append one received reading to the output CSV."""
    features = payload.get("data", {})

    row = {
        "device_id": payload.get("device_id", ""),
        "timestamp": payload.get("timestamp", ""),
        "sequence": payload.get("sequence", ""),
    }

    # Preserve the original dataset feature names and values.
    for column in FEATURE_COLUMNS:
        row[column] = features.get(column, "")

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
        writer.writerow(row)


async def process_data(data_queue):
    """Consume queued readings and save them to CSV."""
    print("[Processor] Background processing started.")

    while True:
        payload = await data_queue.get()

        try:
            save_reading(payload)

            print(
                f"[Processor] Saved reading from "
                f"{payload.get('device_id', 'UNKNOWN')} | "
                f"Sequence={payload.get('sequence', 'N/A')} | "
                f"Rate={payload.get('data', {}).get('Rate', 'N/A')}"
            )

        except (OSError, csv.Error) as exc:
            print(f"[Processor] CSV save error: {exc}")

        finally:
            data_queue.task_done()


async def handle_client(reader, writer, data_queue):
    """Receive newline-delimited JSON messages from sensors."""
    address = writer.get_extra_info("peername")
    print(f"[Gateway] Connected: {address}")

    try:
        while True:
            line = await reader.readline()

            if not line:
                break

            try:
                payload = json.loads(line.decode("utf-8"))

                if not isinstance(payload, dict):
                    print("[Gateway] Invalid message: expected JSON object")
                    continue

                if not isinstance(payload.get("data"), dict):
                    print("[Gateway] Invalid message: missing data object")
                    continue

                await data_queue.put(payload)

            except (json.JSONDecodeError, UnicodeDecodeError):
                print(f"[Gateway] Malformed JSON from {address}")

    except (ConnectionResetError, BrokenPipeError) as exc:
        print(f"[Gateway] Connection interrupted: {exc}")

    finally:
        writer.close()

        try:
            await writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError):
            pass

        print(f"[Gateway] Disconnected: {address}")


async def start_gateway():
    initialize_csv()

    data_queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
    processor_task = asyncio.create_task(process_data(data_queue))

    server = await asyncio.start_server(
        lambda reader, writer: handle_client(
            reader, writer, data_queue
        ),
        HOST,
        PORT,
        limit=64 * 1024,
    )

    print(f"[Gateway] Listening on {HOST}:{PORT}")
    print(f"[Gateway] Saving readings to {OUTPUT_FILE}")

    try:
        async with server:
            await server.serve_forever()

    finally:
        server.close()
        await server.wait_closed()

        # Finish writing queued readings before stopping.
        await data_queue.join()

        processor_task.cancel()
        await asyncio.gather(
            processor_task, return_exceptions=True
        )

        print("[Gateway] Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(start_gateway())
    except KeyboardInterrupt:
        print("\n[Gateway] Shutting down.")
