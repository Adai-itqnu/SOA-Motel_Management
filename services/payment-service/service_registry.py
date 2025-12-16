import consul
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
        c = consul.Consul(host=CONSUL_HOST, port=CONSUL_PORT)

        service_address = os.getenv('SERVICE_ADDRESS') or SERVICE_NAME
        service_id = os.getenv('SERVICE_ID') or f"{SERVICE_NAME}-{SERVICE_PORT}"
        health_url = f"http://{service_address}:{SERVICE_PORT}/health"

        try:
            c.agent.service.deregister(service_id)
        except Exception:
            pass

        c.agent.service.register(
            SERVICE_NAME,
            service_id=service_id,
            address=service_address,
            port=SERVICE_PORT,
            check={
                "HTTP": health_url,
                "Interval": "10s",
                "Timeout": "5s",
                "DeregisterCriticalServiceAfter": "1m",
            }
        )

        print(f"[CONSUL] ✓ Registered {SERVICE_NAME} at {service_address}:{SERVICE_PORT}")
        print(f"[CONSUL]   Health check: {health_url}")
    except Exception as e:
        print(f"[CONSUL] ✗ Error registering service: {e}")
        import traceback
        traceback.print_exc()

