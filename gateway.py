import socket
import threading
import json

HOST = "localhost"
PORT = 5050

def handle_client(client_socket, client_address):
    """Handles communication with a single connected IoT device."""
    client_ip, client_port = client_address
    print(f"[Gateway] Incoming connection accepted from {client_ip}:{client_port}")
    buffer = ""
    
    try:
        while True:
            # Receive data in 1024-byte chunks
            data = client_socket.recv(1024)
            if not data:
                break # Empty byte string means the client closed the connection
            
            buffer += data.decode('utf-8')
            
            # Split by newline to handle TCP packet coalescing
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if line.strip():
                    payload = json.loads(line)
                    print(f"[Gateway] Data from {payload['device_id']}: Temp={payload['temperature']}°C, Humidity={payload['humidity']}%")
                    
    except ConnectionResetError:
        print(f"[Gateway] Connection forcefully closed by {client_ip}:{client_port}")
    except json.JSONDecodeError:
        print(f"[Gateway] Received malformed JSON from {client_ip}:{client_port}")
    finally:
        # Always ensure the socket is cleaned up
        client_socket.close()
        print(f"[Gateway] Connection closed for {client_ip}:{client_port}")

def start_gateway():
    # Create a raw TCP/IP socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Allow immediate reuse of the port to avoid "Address already in use" errors during testing
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Bind the socket to the port and start listening
    server_socket.bind((HOST, PORT))
    server_socket.listen(5) # Allow a backlog of 5 connections before rejecting
    
    print(f"[Gateway] Server listening on {HOST}:{PORT}...")
    print("[Gateway] Waiting for IoT devices to connect. Press Ctrl+C to stop.")
    
    try:
        while True:
            # Block and wait for an incoming connection
            client_socket, client_address = server_socket.accept()
            
            # Spawn a new thread to handle this specific device concurrently
            client_thread = threading.Thread(
                target=handle_client, 
                args=(client_socket, client_address),
                daemon=True # Daemon threads exit automatically when the main program stops
            )
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\n[Gateway] Shutting down.")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_gateway()