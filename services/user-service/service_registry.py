"""User Service Registry"""

import os
import time
import consul
from config import Config


_consul_client = None
_service_id = None


def get_consul_client():
    global _consul_client
    if _consul_client is None:
        _consul_client = consul.Consul(host=Config.CONSUL_HOST, port=Config.CONSUL_PORT)
    return _consul_client


def _wait_for_consul(max_retries=10, retry_delay=2):
    for attempt in range(max_retries):
        try:
            client = get_consul_client()
            client.agent.self()
            return True
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return False


def _get_service_address():
    # Stable docker DNS name; docker-compose sets container_name: user-service
    return os.getenv("SERVICE_ADDRESS") or Config.SERVICE_NAME


def _get_service_id():
    # Stable ID prevents instance count growing on each rebuild/restart
    return os.getenv("SERVICE_ID") or f"{Config.SERVICE_NAME}-{Config.SERVICE_PORT}"


def register_service():
    global _service_id
    try:
        if not _wait_for_consul():
            print("[Consul] ✗ Cannot connect to Consul")
            return

        client = get_consul_client()
        service_address = _get_service_address()
        _service_id = _get_service_id()
        health_url = f"http://{service_address}:{Config.SERVICE_PORT}/health"

        # Best-effort: clear any previous registration with same ID
        try:
            client.agent.service.deregister(_service_id)
        except Exception:
            pass

        client.agent.service.register(
            name=Config.SERVICE_NAME,
            service_id=_service_id,
            address=service_address,
            port=Config.SERVICE_PORT,
            check={
                "HTTP": health_url,
                "Interval": "10s",
                "Timeout": "5s",
                "DeregisterCriticalServiceAfter": "1m",
            },
        )
        print(f"[Consul] ✓ Registered {Config.SERVICE_NAME} ({_service_id})")
    except Exception as e:
        print(f"[Consul] Registration failed: {e}")


def deregister_service():
    global _service_id
    if _service_id:
        try:
            client = get_consul_client()
            client.agent.service.deregister(_service_id)
            print(f"[Consul] ✓ Deregistered {Config.SERVICE_NAME} ({_service_id})")
        except Exception as e:
            print(f"[Consul] Deregistration failed: {e}")
