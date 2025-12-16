"""Notification Service - Consul Registry"""
import socket, os, time, consul
from config import Config

class ServiceRegistry:
    def __init__(self):
        self.consul_client = None
        self.service_id = None
    
    def register(self):
        for i in range(10):
            try:
                self.consul_client = consul.Consul(host=Config.CONSUL_HOST, port=Config.CONSUL_PORT)
                self.consul_client.agent.self()
                break
            except:
                if i < 9: time.sleep(2)
                else: return False
        try:
            addr = os.getenv('HOSTNAME', socket.gethostname())
            try:
                ip = socket.gethostbyname(addr)
                if ip != "127.0.0.1": addr = ip
            except: pass
            self.service_id = f"{Config.SERVICE_NAME}-{addr}"
            self.consul_client.agent.service.register(
                name=Config.SERVICE_NAME, service_id=self.service_id,
                address=addr, port=Config.SERVICE_PORT,
                check=consul.Check.http(f"http://{addr}:{Config.SERVICE_PORT}/health", interval="10s", timeout="5s")
            )
            print(f"[CONSUL] ✓ Registered {Config.SERVICE_NAME}")
            return True
        except Exception as e:
            print(f"[CONSUL] ✗ Failed: {e}")
            return False
    
    def deregister(self):
        if self.consul_client and self.service_id:
            try: self.consul_client.agent.service.deregister(self.service_id)
            except: pass

_registry = ServiceRegistry()
def register_service(): return _registry.register()
def deregister_service(): return _registry.deregister()
