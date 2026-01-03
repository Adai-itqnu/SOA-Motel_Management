# Bill Service - Utility Functions
import datetime
import uuid
import requests
from config import CONSUL_HOST, CONSUL_PORT, INTERNAL_API_KEY
from model import bills_collection


# ============== ID & Timestamp ==============

# Generate unique bill ID
def generate_bill_id():
    while True:
        bill_id = f"BILL{uuid.uuid4().hex[:8].upper()}"
        if not bills_collection.find_one({'_id': bill_id}):
            return bill_id


# Get current UTC timestamp in ISO format
def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


# ============== Bill Calculation ==============

# Calculate electric, water and total costs from meter readings
def calculate_bill(data):
    electric_old = float(data.get('electric_old', 0))
    electric_new = float(data.get('electric_new', 0))
    water_old = float(data.get('water_old', 0))
    water_new = float(data.get('water_new', 0))
    electric_price = float(data.get('electric_price', 3500))
    water_price = float(data.get('water_price', 15000))
    room_fee = float(data.get('room_fee', 0))
    other_fee = float(data.get('other_fee', 0))
    
    electric_usage = max(0, electric_new - electric_old)
    water_usage = max(0, water_new - water_old)
    
    electric_fee = electric_usage * electric_price
    water_fee = water_usage * water_price
    total = room_fee + electric_fee + water_fee + other_fee
    
    return {
        'electric_usage': electric_usage,
        'electric_fee': electric_fee,
        'water_usage': water_usage,
        'water_fee': water_fee,
        'room_fee': room_fee,
        'other_fee': other_fee,
        'total': total
    }


# Calculate fees for finalize draft bill
def calculate_finalize_fees(bill, electric_new, water_new, other_fee=None):
    electric_old = float(bill.get('electric_old', 0))
    water_old = float(bill.get('water_old', 0))
    electric_price = float(bill.get('electric_price', 3500))
    water_price = float(bill.get('water_price', 15000))
    room_fee = float(bill.get('room_fee', 0))
    other = float(other_fee if other_fee is not None else bill.get('other_fee', 0))
    
    electric_usage = max(0, float(electric_new) - electric_old)
    water_usage = max(0, float(water_new) - water_old)
    
    electric_fee = electric_usage * electric_price
    water_fee = water_usage * water_price
    total = room_fee + electric_fee + water_fee + other
    
    return {
        'electric_new': float(electric_new),
        'electric_fee': electric_fee,
        'water_new': float(water_new),
        'water_fee': water_fee,
        'other_fee': other,
        'total': total
    }


# ============== Bill Formatting ==============

# Format bill for API response
def format_bill(bill):
    return {
        '_id': bill['_id'],
        'contract_id': bill.get('contract_id', ''),
        'room_id': bill.get('room_id', ''),
        'user_id': bill.get('user_id', ''),
        'month': bill.get('month', ''),
        'room_fee': bill.get('room_fee', 0),
        'electric_old': bill.get('electric_old', 0),
        'electric_new': bill.get('electric_new', 0),
        'electric_fee': bill.get('electric_fee', 0),
        'water_old': bill.get('water_old', 0),
        'water_new': bill.get('water_new', 0),
        'water_fee': bill.get('water_fee', 0),
        'other_fee': bill.get('other_fee', 0),
        'total': bill.get('total', 0),
        'status': bill.get('status', 'pending'),
        'due_date': bill.get('due_date', ''),
        'paid_at': bill.get('paid_at'),
        'created_at': bill.get('created_at')
    }


# Format unpaid bill for internal API
def format_unpaid_bill(bill):
    return {
        '_id': bill['_id'],
        'contract_id': bill.get('contract_id', ''),
        'room_id': bill.get('room_id', ''),
        'user_id': bill.get('user_id', ''),
        'total_amount': bill.get('total', 0),
        'due_date': bill.get('due_date', ''),
        'status': bill.get('status', 'pending')
    }


# ============== Bill Document Creation ==============

# Create new bill document from data
def create_bill_document(data, amounts):
    timestamp = get_timestamp()
    return {
        '_id': generate_bill_id(),
        'contract_id': data['contract_id'],
        'room_id': data['room_id'],
        'user_id': data['user_id'],
        'month': data['month'],
        'room_fee': amounts['room_fee'],
        'electric_old': float(data['electric_old']),
        'electric_new': float(data['electric_new']),
        'electric_fee': amounts['electric_fee'],
        'water_old': float(data['water_old']),
        'water_new': float(data['water_new']),
        'water_fee': amounts['water_fee'],
        'other_fee': amounts['other_fee'],
        'total': amounts['total'],
        'status': 'pending',
        'due_date': data.get('due_date', ''),
        'paid_at': None,
        'created_at': timestamp
    }


# ============== Validation ==============

# Validate required fields for bill creation
def validate_bill_data(data):
    required = ['contract_id', 'room_id', 'user_id', 'month', 
                'electric_old', 'electric_new', 'water_old', 'water_new', 'room_fee']
    missing = [f for f in required if f not in data]
    return missing


# Check if bill already exists for contract and month
def check_duplicate_bill(contract_id, month):
    return bills_collection.find_one({
        'contract_id': contract_id,
        'month': month
    })


# ============== User Helpers ==============

# Get user ID from token payload
def get_user_id(current_user):
    return current_user.get('user_id') or current_user.get('_id')


# Check if user can access bill
def can_access_bill(current_user, bill):
    user_id = get_user_id(current_user)
    role = current_user.get('role', '')
    return role == 'admin' or bill['user_id'] == user_id


# ============== Service Communication ==============

def get_service_url(service_name):
    try:
        consul_url = f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(consul_url, timeout=5)
        if response.ok and response.json():
            service = response.json()[0]
            host = service.get('ServiceAddress') or service.get('Address') or service_name
            return f"http://{host}:{service['ServicePort']}"
        
        # Fallback to predefined ports if Consul fails
        service_ports = {
            'notification-service': 5010,
        }
        port = service_ports.get(service_name, 5001)
        return f"http://{service_name}:{port}"
    except Exception as e:
        print(f"Error getting service URL: {e}")
        service_ports = {'notification-service': 5010}
        port = service_ports.get(service_name, 5001)
        return f"http://{service_name}:{port}"


def send_notification(user_id, title, message, notification_type, metadata=None):
    try:
        notification_service_url = get_service_url('notification-service')
        if not notification_service_url:
            print("Notification service URL not found")
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

