import requests
from config import CONSUL_HOST, CONSUL_PORT, INTERNAL_API_KEY
from model import payments_collection

# Helper function: Get service URL from Consul
def get_service_url(service_name):
    try:
        consul_url = f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(consul_url, timeout=5)
        if response.ok and response.json():
            service = response.json()[0]
            return f"http://{service['ServiceAddress']}:{service['ServicePort']}"
        # Fallback: use service name directly in Docker network
        service_ports = {
            'bill-service': 5007,
            'booking-service': 5002,
            'notification-service': 5008
        }
        port = service_ports.get(service_name, 5001)
        return f"http://{service_name}:{port}"
    except Exception as e:
        print(f"Error getting service URL: {e}")
        # Fallback: use service name directly in Docker network
        service_ports = {
            'bill-service': 5007,
            'booking-service': 5002,
            'notification-service': 5008
        }
        port = service_ports.get(service_name, 5001)
        return f"http://{service_name}:{port}"

# Helper function: Get data from other services
def fetch_service_data(service_name, endpoint, token=None):
    try:
        service_url = get_service_url(service_name)
        if not service_url:
            return None
        
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}' if not token.startswith('Bearer ') else token
        
        response = requests.get(
            f"{service_url}{endpoint}",
            headers=headers,
            timeout=10
        )
        
        if response.ok:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching from {service_name}: {e}")
        return None

# Helper function: Call service API (PUT/POST)
def call_service_api(service_name, method, endpoint, data=None, token=None):
    try:
        service_url = get_service_url(service_name)
        if not service_url:
            return None
        
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}' if not token.startswith('Bearer ') else token
        else:
            # Use Internal API key if no token provided (for service-to-service calls)
            headers['X-Internal-Api-Key'] = INTERNAL_API_KEY
        
        if method.upper() == 'PUT':
            response = requests.put(
                f"{service_url}{endpoint}",
                json=data,
                headers=headers,
                timeout=10
            )
        elif method.upper() == 'POST':
            response = requests.post(
                f"{service_url}{endpoint}",
                json=data,
                headers=headers,
                timeout=10
            )
        else:
            return None
        
        if response.ok:
            return response.json()
        return None
    except Exception as e:
        print(f"Error calling {service_name} {method}: {e}")
        return None

def update_booking_deposit_status(booking_id, status, transaction_id=None):
    """Notify booking-service about deposit status changes."""
    try:
        booking_service_url = get_service_url('booking-service')
        if not booking_service_url:
            print("Booking service URL not found for deposit update")
            return False
        payload = {'status': status}
        if transaction_id:
            payload['transaction_id'] = transaction_id
        response = requests.put(
            f"{booking_service_url}/api/bookings/{booking_id}/deposit-status",
            json=payload,
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY},
            timeout=5
        )
        if not response.ok:
            print(f"Failed to update booking deposit status: {response.text}")
        return response.ok
    except Exception as exc:
        print(f"Error updating booking deposit status: {exc}")
        return False

def send_notification(user_id, title, message, notification_type, metadata=None):
    try:
        notification_service_url = get_service_url('notification-service')
        if not notification_service_url:
            return False
        payload = {
            'user_id': str(user_id),
            'title': title,
            'message': message,
            'type': notification_type,
            'metadata': metadata or {}
        }
        response = requests.post(
            f"{notification_service_url}/api/notifications",
            json=payload,
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY, 'Content-Type': 'application/json'},
            timeout=5
        )
        if not response.ok:
            print(f"Failed to send notification: {response.text}")
        return response.ok
    except Exception as exc:
        print(f"Error sending notification: {exc}")
        return False

# Helper function: Tính tổng thanh toán đã hoàn thành của một bill
def calculate_total_paid(bill_id):
    pipeline = [
        {'$match': {'bill_id': bill_id, 'status': 'completed'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ]
    result = list(payments_collection.aggregate(pipeline))
    return result[0]['total'] if result else 0

# Helper function: Cập nhật bill status nếu thanh toán đủ
def update_bill_status_if_paid(bill_id, total_amount):
    total_paid = calculate_total_paid(bill_id)
    if total_paid >= total_amount:
        # Gọi bill-service để cập nhật status
        result = call_service_api(
            'bill-service',
            'PUT',
            f'/api/bills/{bill_id}/status',
            {'status': 'paid'}
        )
        return result is not None
    return False
