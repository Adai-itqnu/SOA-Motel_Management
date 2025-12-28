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
            host = service.get('ServiceAddress') or service.get('Address') or service_name
            return f"http://{host}:{service['ServicePort']}"
        # Fallback: use service name directly in Docker network
        service_ports = {
            'bill-service': 5007,
            'booking-service': 5005,
            'contract-service': 5006,
            'notification-service': 5010,
            'room-service': 5002,
            'payment-service': 5008,
        }
        port = service_ports.get(service_name, 5001)
        return f"http://{service_name}:{port}"
    except Exception as e:
        print(f"Error getting service URL: {e}")
        # Fallback: use service name directly in Docker network
        service_ports = {
            'bill-service': 5007,
            'booking-service': 5005,
            'contract-service': 5006,
            'notification-service': 5010,
            'room-service': 5002,
            'payment-service': 5008,
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

def update_booking_deposit_status(booking_id, status, transaction_id=None, payment_id=None):
    """Notify booking-service about deposit status changes."""
    try:
        booking_service_url = get_service_url('booking-service')
        if not booking_service_url:
            print("Booking service URL not found for deposit update")
            return False
        payload = {'status': status}
        if transaction_id:
            payload['transaction_id'] = transaction_id
        if payment_id:
            payload['payment_id'] = payment_id
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


def hold_room_reservation(room_id, tenant_id, payment_id):
    """Hold a room during VNPay deposit payment."""
    try:
        room_service_url = get_service_url('room-service')
        if not room_service_url:
            print('Room service URL not found for reservation hold')
            return False
        payload = {'tenant_id': str(tenant_id), 'payment_id': str(payment_id)}
        response = requests.put(
            f"{room_service_url}/internal/rooms/{room_id}/reservation/hold",
            json=payload,
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY, 'Content-Type': 'application/json'},
            timeout=8,
        )
        if not response.ok:
            print(f"Failed to hold room reservation: {response.text}")
        return response.ok
    except Exception as exc:
        print(f"Error holding room reservation: {exc}")
        return False


def confirm_room_reservation(room_id, payment_id):
    """Confirm room reservation after payment success and create booking record."""
    try:
        room_service_url = get_service_url('room-service')
        booking_service_url = get_service_url('booking-service')
        
        if not room_service_url:
            print('Room service URL not found for reservation confirm')
            return False
        
        # Get payment info first to extract tenant_id
        payment = payments_collection.find_one({'_id': payment_id})
        tenant_id = payment.get('tenant_id') if payment else None
        
        payload = {
            'payment_id': str(payment_id),
            'tenant_id': tenant_id
        }
        response = requests.put(
            f"{room_service_url}/internal/rooms/{room_id}/reservation/confirm",
            json=payload,
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY, 'Content-Type': 'application/json'},
            timeout=8,
        )
        if not response.ok:
            print(f"Failed to confirm room reservation: {response.text}")
            return False
        
        # Now create booking record from payment
        if booking_service_url:
            try:
                # Get payment info to extract booking details
                payment = payments_collection.find_one({'_id': payment_id})
                if payment:
                    booking_payload = {
                        'room_id': room_id,
                        'user_id': payment.get('tenant_id'),
                        'check_in_date': payment.get('check_in_date'),
                        'deposit_amount': payment.get('amount', 0),
                        'deposit_status': 'paid',
                        'deposit_payment_id': payment_id,
                        'payment_method': 'vnpay',
                        'status': 'deposit_paid'
                    }
                    resp = requests.post(
                        f"{booking_service_url}/internal/bookings/create-from-payment",
                        json=booking_payload,
                        headers={'X-Internal-Api-Key': INTERNAL_API_KEY, 'Content-Type': 'application/json'},
                        timeout=5,
                    )
                    if not resp.ok:
                        print(f"Failed to create booking record: {resp.text}")
            except Exception as e:
                print(f"Error creating booking record: {e}")
        
        return True
    except Exception as exc:
        print(f"Error confirming room reservation: {exc}")
        return False


def release_room_reservation(room_id, payment_id):
    """Release a held room when payment cancelled/failed."""
    try:
        room_service_url = get_service_url('room-service')
        if not room_service_url:
            print('Room service URL not found for reservation release')
            return False
        payload = {'payment_id': str(payment_id)}
        response = requests.put(
            f"{room_service_url}/internal/rooms/{room_id}/reservation/release",
            json=payload,
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY, 'Content-Type': 'application/json'},
            timeout=8,
        )
        if not response.ok:
            print(f"Failed to release room reservation: {response.text}")
        return response.ok
    except Exception as exc:
        print(f"Error releasing room reservation: {exc}")
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


def auto_create_contract(room_id, tenant_id, payment_id, check_in_date=None):
    """Auto-create contract after successful room deposit payment."""
    try:
        contract_service_url = get_service_url('contract-service')
        if not contract_service_url:
            print('Contract service URL not found for auto-create')
            return False
        
        payload = {
            'room_id': room_id,
            'tenant_id': str(tenant_id),
            'payment_id': str(payment_id),
        }
        if check_in_date:
            payload['check_in_date'] = check_in_date
        
        response = requests.post(
            f"{contract_service_url}/internal/contracts/auto-create",
            json=payload,
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY, 'Content-Type': 'application/json'},
            timeout=10,
        )
        if not response.ok:
            print(f"Failed to auto-create contract: {response.text}")
            return False
        print(f"Auto-created contract for room {room_id}, tenant {tenant_id}")
        return True
    except Exception as exc:
        print(f"Error auto-creating contract: {exc}")
        return False

