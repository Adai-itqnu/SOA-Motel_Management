import consul
import socket
import os
from config import SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT

def register_service():
    """Register service with Consul"""
    import time
    
    # Đợi Consul sẵn sàng
    max_retries = 10
    for i in range(max_retries):
        try:
            c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
            # Test connection
            c.agent.self()
            break
        except Exception as e:
            if i < max_retries - 1:
                print(f"[CONSUL] Waiting for Consul... (attempt {i+1}/{max_retries})")
                time.sleep(2)
            else:
                print(f"[CONSUL] Cannot connect to Consul: {e}")
                return
    
    try:
        # Lấy IP của container (trong Docker) hoặc localhost (local)
        try:
            # Trong Docker, lấy hostname sẽ resolve về container IP
            hostname = socket.gethostname()
            container_ip = socket.gethostbyname(hostname)
            # Nếu là localhost, dùng container name
            if container_ip == "127.0.0.1":
                container_ip = hostname
        except:
            # Fallback về container name nếu không resolve được
            container_ip = os.getenv('HOSTNAME', 'localhost')
        
        c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
        
        # Health check URL - dùng container IP hoặc service name
        health_url = f"http://{container_ip}:{SERVICE_PORT}/health"
        
        c.agent.service.register(
            SERVICE_NAME,
            address=container_ip,
            port=SERVICE_PORT,
            check=consul.Check.http(health_url, interval="10s", timeout="5s")
        )
        
        print(f"[CONSUL] ✓ Registered {SERVICE_NAME} at {container_ip}:{SERVICE_PORT}")
        print(f"[CONSUL]   Health check: {health_url}")
    except Exception as e:
        print(f"[CONSUL] ✗ Error registering service: {e}")
        import traceback
        traceback.print_exc()

