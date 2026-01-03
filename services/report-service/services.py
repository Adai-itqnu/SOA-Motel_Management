# Report Service - External Service Calls
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
    
    ports = {'room-service': 5002, 'contract-service': 5006, 'payment-service': 5007}
    return f"http://{service_name}:{ports.get(service_name, 5001)}"


def _auth_header(token):
# Prepare auth header
    
    if not token:
        return {}
    if not token.startswith('Bearer '):
        token = f'Bearer {token}'
    return {'Authorization': token}


def fetch_service_data(service_name, endpoint, token):
# Fetch data from other service
    
    try:
        url = get_service_url(service_name)
        response = requests.get(f"{url}{endpoint}", headers=_auth_header(token), timeout=10)
        return response.json() if response.ok else None
    except Exception as e:
        print(f"Error fetching from {service_name}: {e}")
        return None


def get_room_stats(token):
# Get room statistics
    
    return fetch_service_data('room-service', '/api/rooms/stats', token)


def get_contracts(token, status=None):
# Get contracts list
    
    endpoint = f"/api/contracts?status={status}" if status else "/api/contracts"
    return fetch_service_data('contract-service', endpoint, token)


def get_contract_detail(contract_id, token):
# Get contract details
    
    return fetch_service_data('contract-service', f"/api/contracts/{contract_id}", token)


def get_room_contracts(room_id, token):
# Get contracts for a room
    
    return fetch_service_data('contract-service', f"/api/contracts/room/{room_id}", token)


def get_room_detail(room_id, token):
# Get room details
    
    return fetch_service_data('room-service', f"/api/rooms/{room_id}", token)


def get_payments(token, status=None):
# Get payments list from payment-service
    
    endpoint = f"/api/payments?status={status}" if status else "/api/payments"
    return fetch_service_data('payment-service', endpoint, token)
