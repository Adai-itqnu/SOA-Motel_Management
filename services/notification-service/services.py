# Notification Service - External Service Calls
import requests
from config import Config


def get_service_url(service_name):
# Get service URL from Consul
    
    try:
        url = f"http://{Config.CONSUL_HOST}:{Config.CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(url, timeout=5)
        if response.ok and response.json():
            svc = response.json()[0]
            return f"http://{svc['ServiceAddress']}:{svc['ServicePort']}"
    except:
        pass
    
    ports = {'bill-service': 5007, 'booking-service': 5005}
    return f"http://{service_name}:{ports.get(service_name, 5000)}"


def fetch_unpaid_bills():
# Fetch unpaid bills from bill-service
    
    try:
        url = get_service_url('bill-service')
        response = requests.get(
            f"{url}/internal/bills/unpaid",
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=10
        )
        if response.ok:
            return response.json().get('bills', [])
        return []
    except Exception as e:
        print(f"Error fetching unpaid bills: {e}")
        return []
