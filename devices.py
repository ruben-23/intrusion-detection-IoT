import threading
import socket
import csv
import json
import time

# Configuration
GATEWAY_HOST = "localhost"
GATEWAY_PORT = 5050
DATA_FILE = "sensor_data.csv"

def simulate_device(device_id, delay=2):
    # 1. Read and filter CSV data for this specific device
    device_data = []
    try:
        with open(DATA_FILE, 'r') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row['device_id'] == device_id:
                    device_data.append(row)
    except FileNotFoundError:
        print(f"[{device_id}] Error: {DATA_FILE} not found.")
        return

    if not device_data:
        print(f"[{device_id}] No data found in CSV. Exiting.")
        return

    # 2. Connect to the Gateway
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((GATEWAY_HOST, GATEWAY_PORT))
            print(f"[{device_id}] Successfully connected to gateway.")
            
            # 3. Stream data
            for reading in device_data:
                # Convert dictionary to JSON string and append newline for parsing
                payload = json.dumps(reading) + "\n"
                s.sendall(payload.encode('utf-8'))
                
                print(f"[{device_id}] Sent reading for timestamp {reading['timestamp']}")
                time.sleep(delay) # Simulate time passing between sensor reads
                
        except ConnectionRefusedError:
            print(f"[{device_id}] Connection failed. Is the gateway running?")

if __name__ == "__main__":
    device_ids = ["DEV-01", "DEV-02", "DEV-03"]
    threads = []

    print("[Manager] Starting IoT Device Threads...")
    
    # Spawn a thread for each device
    for d_id in device_ids:
        # Pass device_id and a 2-second delay between messages
        t = threading.Thread(target=simulate_device, args=(d_id, 2))
        t.start()
        threads.append(t)

    # Keep main thread alive until all device threads finish
    for t in threads:
        t.join()
        
    print("[Manager] All devices have finished transmitting their data.")