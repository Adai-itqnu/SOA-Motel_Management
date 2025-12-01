import requests
import socket
from config import SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT

def register_service():
    """Register the service with Consul for discovery."""
    try:
        host_name = socket.gethostbyname(socket.gethostname())
    except Exception:
        host_name = "127.0.0.1"

    registration = {
        "ID": f"{SERVICE_NAME}-{SERVICE_PORT}",
        "Name": SERVICE_NAME,
        "Address": host_name,
        "Port": SERVICE_PORT,
        "Check": {
            "HTTP": f"http://{host_name}:{SERVICE_PORT}/health",
            "Interval": "10s"
        }
    }

    try:
        consul_url = f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/agent/service/register"
        response = requests.put(consul_url, json=registration, timeout=5)
        if response.status_code == 200:
            print(f"{SERVICE_NAME} registered with Consul successfully.")
        else:
            print(f"Failed to register service: {response.text}")
    except requests.RequestException as exc:
        print(f"Error registering service with Consul: {exc}")

