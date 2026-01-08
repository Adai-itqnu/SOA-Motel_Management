# Contract Service - Utility Functions
import datetime
import uuid
import os
import requests
from bson import ObjectId
from model import contracts_collection
from config import CONSUL_HOST, CONSUL_PORT


# ============== Service Discovery ==============

def get_service_url(service_name):
    """Get service URL dynamically from Consul."""
    try:
        consul_url = f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(consul_url, timeout=5)
        if response.ok and response.json():
            service = response.json()[0]
            host = service.get('ServiceAddress') or service.get('Address') or service_name
            port = service.get('ServicePort')
            if host and port:
                return f"http://{host}:{port}"
    except Exception as e:
        print(f"[Consul] Error getting {service_name} URL: {e}")
    
    fallback_port = os.getenv(f"{service_name.upper().replace('-', '_')}_PORT", "80")
    return f"http://{service_name}:{fallback_port}"


# ============== Timestamp & ID ==============

def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


def generate_contract_id():
    while True:
        cid = f"CTR{uuid.uuid4().hex[:8].upper()}"
        if not contracts_collection.find_one({'_id': cid}):
            return cid


# ============== User Helpers ==============

def get_user_id(current_user):
    return current_user.get('user_id') or current_user.get('_id')


def can_access_contract(current_user, contract):
    user_id = get_user_id(current_user)
    role = current_user.get('role', '')
    return role == 'admin' or contract['user_id'] == user_id


# ============== Formatting ==============

def format_contract(contract):
    return {
        '_id': contract['_id'],
        'room_id': contract.get('room_id', ''),
        'user_id': contract.get('user_id', ''),
        'start_date': contract.get('start_date', ''),
        'end_date': contract.get('end_date', ''),
        'monthly_rent': contract.get('monthly_rent', 0),
        'deposit_amount': contract.get('deposit_amount', 0),
        'deposit_status': contract.get('deposit_status', 'pending'),
        'deposit_payment_id': contract.get('deposit_payment_id'),
        'payment_day': contract.get('payment_day', 5),
        'status': contract.get('status', 'active'),
        'notes': contract.get('notes', ''),
        'created_at': contract.get('created_at'),
        'updated_at': contract.get('updated_at')
    }


# ============== Validation ==============

def validate_contract_dates(start_date, end_date):
    try:
        start = datetime.datetime.fromisoformat(start_date)
        end = datetime.datetime.fromisoformat(end_date)
        if end <= start:
            return None, None, 'Ngày kết thúc phải sau ngày bắt đầu!'
        return start, end, None
    except:
        return None, None, 'Định dạng ngày không hợp lệ (YYYY-MM-DD)!'


def check_existing_active_contract(user_id):
    return contracts_collection.find_one({
        'user_id': user_id,
        'status': 'active'
    })


def check_contract_exists(room_id, user_id):
    return contracts_collection.find_one({
        'room_id': room_id,
        'user_id': str(user_id),
        'status': 'active'
    })


# ============== Document Creation ==============

def create_contract_document(data, user_id):
    timestamp = get_timestamp()
    return {
        '_id': generate_contract_id(),
        'room_id': data['room_id'],
        'user_id': str(user_id),
        'start_date': data['start_date'],
        'end_date': data['end_date'],
        'monthly_rent': float(data['monthly_rent']),
        'deposit_amount': float(data.get('deposit_amount', 0)),
        'deposit_status': data.get('deposit_status', 'paid'),
        'payment_day': int(data.get('payment_day', 5)),
        'status': 'active',
        'notes': data.get('notes', ''),
        'created_at': timestamp,
        'updated_at': timestamp
    }


def create_auto_contract_document(room_id, user_id, room_data, payment_id, check_in_date=None):
    if check_in_date:
        try:
            start = datetime.datetime.fromisoformat(check_in_date)
        except:
            start = datetime.datetime.utcnow()
    else:
        start = datetime.datetime.utcnow()
    
    end = start + datetime.timedelta(days=365)
    timestamp = get_timestamp()
    
    return {
        '_id': generate_contract_id(),
        'room_id': room_id,
        'user_id': str(user_id),
        'start_date': start.strftime('%Y-%m-%d'),
        'end_date': end.strftime('%Y-%m-%d'),
        'monthly_rent': float(room_data.get('price', 0)),
        'deposit_amount': float(room_data.get('deposit', 0)),
        'deposit_status': 'paid',
        'deposit_payment_id': payment_id,
        'payment_day': 5,
        'status': 'active',
        'notes': 'Hợp đồng tự động tạo sau thanh toán cọc thành công',
        'created_at': timestamp,
        'updated_at': timestamp,
    }


# ============== ObjectId Helpers ==============

def to_object_id(id_value):
    if isinstance(id_value, ObjectId):
        return id_value
    if isinstance(id_value, str) and ObjectId.is_valid(id_value):
        return ObjectId(id_value)
    return id_value
