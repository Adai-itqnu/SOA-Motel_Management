"""
Booking Service - Consul Service Registry
"""
import os
import time
import consul
from config import Config


class ServiceRegistry:
    def __init__(self):
        self.consul_client = None
        self.service_id = None
    
    def _wait_for_consul(self, max_retries=10, retry_delay=2):
        for attempt in range(max_retries):
            try:
                self.consul_client = consul.Consul(host=Config.CONSUL_HOST, port=Config.CONSUL_PORT)
                self.consul_client.agent.self()
                print("[CONSUL] ✓ Connected to Consul")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"[CONSUL] Waiting for Consul... ({attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                else:
                    print(f"[CONSUL] ✗ Cannot connect: {e}")
                    return False
        return False

    def _get_service_address(self):
        return os.getenv('SERVICE_ADDRESS') or Config.SERVICE_NAME

    def _get_service_id(self):
        return os.getenv('SERVICE_ID') or f"{Config.SERVICE_NAME}-{Config.SERVICE_PORT}"
    
    def register(self):
        if not self._wait_for_consul():
            return False
        
        try:
            service_address = self._get_service_address()
            self.service_id = self._get_service_id()
            health_url = f"http://{service_address}:{Config.SERVICE_PORT}/health"

            try:
                self.consul_client.agent.service.deregister(self.service_id)
            except Exception:
                pass

            self.consul_client.agent.service.register(
                name=Config.SERVICE_NAME,
                service_id=self.service_id,
                address=service_address,
                port=Config.SERVICE_PORT,
                check={
                    "HTTP": health_url,
                    "Interval": "10s",
                    "Timeout": "5s",
                    "DeregisterCriticalServiceAfter": "1m",
                }
            )
            print(f"[CONSUL] ✓ Registered {Config.SERVICE_NAME} at {service_address}:{Config.SERVICE_PORT}")
            return True
        except Exception as e:
            print(f"[CONSUL] ✗ Failed: {e}")
            return False
    
    def deregister(self):
        if self.consul_client and self.service_id:
            try:
                self.consul_client.agent.service.deregister(self.service_id)
                print(f"[CONSUL] ✓ Deregistered {self.service_id}")
            except Exception as e:
                print(f"[CONSUL] ✗ Deregistration failed: {e}")


_registry = ServiceRegistry()

def register_service():
    return _registry.register()

def deregister_service():
    return _registry.deregister()
