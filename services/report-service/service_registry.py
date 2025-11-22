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
        # Trong Docker network, sử dụng container name (hostname) để các service khác có thể kết nối
        container_name = os.getenv('HOSTNAME', socket.gethostname())
        
        c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)
        
        try:
            container_ip = socket.gethostbyname(container_name)
            if container_ip == "127.0.0.1":
                service_address = container_name
            else:
                service_address = container_ip
        except:
            service_address = container_name
        
        health_url = f"http://{service_address}:{SERVICE_PORT}/health"
        
        c.agent.service.register(
            SERVICE_NAME,
            address=service_address,
            port=SERVICE_PORT,
            check=consul.Check.http(health_url, interval="10s", timeout="5s")
        )
        
        print(f"[CONSUL] ✓ Registered {SERVICE_NAME} at {service_address}:{SERVICE_PORT}")
        print(f"[CONSUL]   Health check: {health_url}")
    except Exception as e:
        print(f"[CONSUL] ✗ Error registering service: {e}")
        import traceback
        traceback.print_exc()