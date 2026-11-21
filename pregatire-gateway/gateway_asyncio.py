import asyncio
import json

HOST = "localhost"
PORT = 5050

async def process_data(data_queue):
    """Consumer: Runs continuously in the async event loop, processing data."""
    print("[Processor] Background processing task started.")
    while True:
        # await yields control back to the event loop while waiting for data
        payload = await data_queue.get()
        print(f"[Processor] Saved data from {payload['device_id']}: Temp={payload['temperature']}°C, Humidity={payload['humidity']}%")
        data_queue.task_done()

async def handle_client(reader, writer, data_queue):
    """Producer: Handles network I/O asynchronously for a single connection."""
    client_address = writer.get_extra_info('peername')
    client_ip, client_port = client_address
    
    print(f"[Gateway] Incoming connection accepted from {client_ip}:{client_port}")
    
    try:
        while True:
            # readline() yields to the event loop while waiting for network packets
            data = await reader.readline()
            if not data:
                break # Connection closed by client
            
            line = data.decode('utf-8').strip()
            if line:
                try:
                    payload = json.loads(line)
                    await data_queue.put(payload)
                except json.JSONDecodeError:
                    print(f"[Gateway] Received malformed JSON from {client_ip}:{client_port}")
                    
    except ConnectionResetError:
        print(f"[Gateway] Connection forcefully closed by {client_ip}:{client_port}")
    finally:
        writer.close()
        await writer.wait_closed() # Ensure the socket is fully closed non-blockingly
        print(f"[Gateway] Connection closed for {client_ip}:{client_port}")

async def start_gateway():
    # Asyncio queue to buffer messages between network coroutines and the processor
    data_queue = asyncio.Queue()
    
    # Fire up the single consumer task in the background
    asyncio.create_task(process_data(data_queue))

    # Wrapper to pass our queue into the handler
    async def client_callback(reader, writer):
        await handle_client(reader, writer, data_queue)

    # Start the async TCP server - this accepts unlimited connections
    server = await asyncio.start_server(client_callback, HOST, PORT)
    
    print(f"[Gateway] Async server listening on {HOST}:{PORT}...")
    print("[Gateway] Unrestricted concurrency. Waiting for IoT devices to connect. Press Ctrl+C to stop.")
    
    # Keep the server running forever
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        # asyncio.run() sets up the event loop and kicks off the main coroutine
        asyncio.run(start_gateway())
    except KeyboardInterrupt:
        print("\n[Gateway] Shutting down.")