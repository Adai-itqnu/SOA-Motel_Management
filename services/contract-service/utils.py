"""Contract Service - Utility Functions"""
import datetime
import uuid
from bson import ObjectId
from model import contracts_collection

def get_timestamp():
    return datetime.datetime.utcnow().isoformat()

def generate_contract_id():
    while True:
        cid = f"C{uuid.uuid4().hex[:8].upper()}"
        if not contracts_collection.find_one({'_id': cid}):
            return cid

def to_object_id(id_value):
    if isinstance(id_value, ObjectId):
        return id_value
    if isinstance(id_value, str) and ObjectId.is_valid(id_value):
        return ObjectId(id_value)
    return id_value

def format_contract(contract, tenant_info=None):
    result = {}
    for k, v in contract.items():
        if isinstance(v, ObjectId):
            result[k] = str(v)
        elif isinstance(v, datetime.datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    result['id'] = result.get('_id', '')
    result['tenant_name'] = tenant_info.get('name', '') if tenant_info else ''
    result['tenant_phone'] = tenant_info.get('phone', '') if tenant_info else ''
    return result

def create_contract_doc(data, tenant_id):
    ts = get_timestamp()
    return {
        '_id': generate_contract_id(),
        'tenant_id': tenant_id,
        'room_id': data['room_id'],
        'start_date': data['start_date'],
        'end_date': data['end_date'],
        'monthly_rent': float(data['monthly_rent']),
        'deposit': float(data['deposit']),
        'electric_price': float(data.get('electric_price', 3500)),
        'water_price': float(data.get('water_price', 20000)),
        'payment_day': int(data.get('payment_day', 5)),
        'notes': data.get('notes', ''),
        'status': 'active',
        'created_at': ts,
        'updated_at': ts
    }
