# Booking Service - External Service Calls
import requests
from config import Config


def get_service_url(service_name):
# Get service URL from Consul
    
    try:
        consul_url = f"http://{Config.CONSUL_HOST}:{Config.CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(consul_url, timeout=5)
        if response.ok and response.json():
            service = response.json()[0]
            return f"http://{service['ServiceAddress']}:{service['ServicePort']}"
        
        # Fallback
        ports = {
            'room-service': 5002,
            'user-service': 5003,
            'contract-service': 5006,
            'notification-service': 5010
        }
        return f"http://{service_name}:{ports.get(service_name, 5001)}"
    except Exception as e:
        print(f"Error getting service URL: {e}")
        return None


def _prepare_auth_header(token):
# Prepare authorization header
    
    if not token:
        return {}
    if not token.startswith('Bearer ') and not token.startswith('bearer '):
        token = f'Bearer {token}'
    return {'Authorization': token}


def check_room_availability(room_id, token):
# Check if room exists and get its details
    
    try:
        url = get_service_url('room-service')
        if not url:
            return None, "Không thể kết nối tới Room Service"
        
        response = requests.get(
            f"{url}/api/rooms/{room_id}",
            headers=_prepare_auth_header(token),
            timeout=5
        )
        
        if response.ok:
            return response.json(), None
        return None, "Phòng không tồn tại"
    except Exception as e:
        return None, f"Lỗi kết nối Room Service: {str(e)}"


def update_room_status(room_id, status, user_id=None):
# Update room status via internal API
    
    try:
        url = get_service_url('room-service')
        if not url:
            return False
        
        payload = {'status': status}
        if user_id:
            payload['user_id'] = str(user_id)
        
        response = requests.put(
            f"{url}/internal/rooms/{room_id}/status",
            json=payload,
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=5
        )
        return response.ok
    except Exception as e:
        print(f"Error updating room status: {e}")
        return False


def get_user_info(user_id, token):
# Get user information
    
    try:
        url = get_service_url('user-service')
        if not url:
            return None
        
        response = requests.get(
            f"{url}/api/users/{user_id}",
            headers=_prepare_auth_header(token),
            timeout=5
        )
        
        if response.ok:
            return response.json()
        return None
    except Exception as e:
        print(f"Error getting user info: {e}")
        return None


def create_contract(contract_data, token=None):
# Create contract via contract-service
    
    try:
        url = get_service_url('contract-service')
        if not url:
            return None, "Không thể kết nối tới Contract Service"
        
        headers = {'Content-Type': 'application/json'}
        if token:
            headers.update(_prepare_auth_header(token))
        else:
            headers['X-Internal-Api-Key'] = Config.INTERNAL_API_KEY
        
        response = requests.post(
            f"{url}/api/contracts",
            json=contract_data,
            headers=headers,
            timeout=10
        )
        
        if response.ok:
            return response.json(), None
        return None, response.json().get('message', 'Lỗi tạo hợp đồng')
    except Exception as e:
        return None, f"Lỗi kết nối Contract Service: {str(e)}"


def send_notification(user_id, title, message, notification_type, metadata=None):
# Send notification via notification-service
    
    try:
        url = get_service_url('notification-service')
        if not url:
            return False
        
        response = requests.post(
            f"{url}/api/notifications",
            json={
                'user_id': str(user_id),
                'title': title,
                'message': message,
                'type': notification_type,
                'metadata': metadata or {}
            },
            headers={
                'X-Internal-Api-Key': Config.INTERNAL_API_KEY,
                'Content-Type': 'application/json'
            },
            timeout=5
        )
        return response.ok
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False
