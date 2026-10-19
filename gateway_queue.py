import socket
import threading
import json
import queue

HOST = "localhost"
PORT = 5050

# Create a thread-safe Queue to act as a buffer between network and processing
data_queue = queue.Queue()

def process_data():
    """Consumer: Runs in the background, pulls data from the queue, and processes it."""
    print("[Processor] Background processing thread started.")
    while True:
        # .get() blocks and waits until an item is available in the queue
        payload = data_queue.get()
        
        # Simulate processing (e.g., writing to a database, triggering alerts)
        print(f"[Processor] Saved data from {payload['device_id']}: Temp={payload['temperature']}°C, Humidity={payload['humidity']}%")
        
        # Signal that the queue item has been fully processed
        data_queue.task_done()

def handle_client(client_socket, client_address):
    """Producer: Handles the network connection and puts parsed data into the queue."""
    client_ip, client_port = client_address
    print(f"[Gateway] Incoming connection accepted from {client_ip}:{client_port}")
    buffer = ""
    
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            
            buffer += data.decode('utf-8')
            
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if line.strip():
                    payload = json.loads(line)
                    # Instead of processing directly, hand off the data to the queue
                    data_queue.put(payload)
                    
    except ConnectionResetError:
        print(f"[Gateway] Connection forcefully closed by {client_ip}:{client_port}")
    except json.JSONDecodeError:
        print(f"[Gateway] Received malformed JSON from {client_ip}:{client_port}")
    finally:
        client_socket.close()
        print(f"[Gateway] Connection closed for {client_ip}:{client_port}")

def start_gateway():
    # Start the single background consumer thread
    processor_thread = threading.Thread(target=process_data, daemon=True)
    processor_thread.start()

    # Set up the raw socket server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    
    print(f"[Gateway] Server listening on {HOST}:{PORT}...")
    print("[Gateway] Waiting for IoT devices to connect. Press Ctrl+C to stop.")
    
    try:
        while True:
            client_socket, client_address = server_socket.accept()
            
            # Spawn a new producer thread for each device
            client_thread = threading.Thread(
                target=handle_client, 
                args=(client_socket, client_address),
                daemon=True
            )
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\n[Gateway] Shutting down.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_gateway()