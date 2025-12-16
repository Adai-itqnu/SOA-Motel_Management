"""Contract Service - External Service Calls"""
import requests
from config import Config

def get_service_url(service_name):
    try:
        url = f"http://{Config.CONSUL_HOST}:{Config.CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(url, timeout=5)
        if response.ok and response.json():
            svc = response.json()[0]
            return f"http://{svc['ServiceAddress']}:{svc['ServicePort']}"
        ports = {'room-service': 5002, 'tenant-service': 5003}
        return f"http://{service_name}:{ports.get(service_name, 5001)}"
    except:
        return None

def _auth_header(token):
    if not token:
        return {}
    if not token.startswith('Bearer '):
        token = f'Bearer {token}'
    return {'Authorization': token}

def check_room(room_id, token):
    try:
        url = get_service_url('room-service')
        if not url:
            return None, "Không thể kết nối Room Service"
        resp = requests.get(f"{url}/api/rooms/{room_id}", headers=_auth_header(token), timeout=5)
        return (resp.json(), None) if resp.ok else (None, "Phòng không tồn tại")
    except Exception as e:
        return None, str(e)

def update_room_status(room_id, status, tenant_id, token):
    try:
        url = get_service_url('room-service')
        if not url:
            return False
        data = {'status': status}
        if tenant_id:
            data['tenant_id'] = str(tenant_id)
        resp = requests.put(f"{url}/api/rooms/{room_id}", json=data, headers=_auth_header(token), timeout=5)
        return resp.ok
    except:
        return False

def get_tenant_info(tenant_id, token):
    try:
        url = get_service_url('tenant-service')
        if not url:
            return None
        resp = requests.get(f"{url}/api/tenants/{tenant_id}", headers=_auth_header(token), timeout=5)
        return resp.json() if resp.ok else None
    except:
        return None
