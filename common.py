"""Configurație comună pentru backend, gateway și simulator."""
import asyncio
import os
import sys

# aiomqtt nu funcționează cu ProactorEventLoop (default pe Windows)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# --- Broker MQTT public ---
MQTT_HOST = os.getenv("MQTT_HOST", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
# Broker public = toți utilizatorii văd topicurile tale. Schimbă rădăcina
# cu ceva unic (ex: ids_ionut_2026) ca să nu se amestece cu alții.
TOPIC_ROOT = os.getenv("MQTT_ROOT", "ids")

# --- Gateway ---
GATEWAY_ID = os.getenv("GATEWAY_ID", "edge_01")
GATEWAY_HOST = os.getenv("GATEWAY_HOST", "127.0.0.1")
GATEWAY_PORT = int(os.getenv("GATEWAY_PORT", "5050"))

# --- Backend: server TCP pentru înregistrare (gateway / device) ---
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_TCP_PORT = int(os.getenv("BACKEND_TCP_PORT", "9100"))

FEATURE_COLUMNS = [
    "Header_Length", "Protocol Type", "Time_To_Live", "Rate",
    "fin_flag_number", "syn_flag_number", "rst_flag_number",
    "psh_flag_number", "ack_flag_number", "ece_flag_number",
    "cwr_flag_number", "ack_count", "syn_count", "fin_count",
    "rst_count", "HTTP", "HTTPS", "DNS", "Telnet", "SMTP",
    "SSH", "IRC", "TCP", "UDP", "DHCP", "ARP", "ICMP",
    "IGMP", "IPv", "LLC", "Tot sum", "Min", "Max", "AVG",
    "Std", "Tot size", "IAT", "Number", "Variance",
]
