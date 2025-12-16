"""Bill Service - Utility Functions"""
import datetime
import uuid
from model import bills_collection


def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


def generate_bill_id():
    """Generate unique bill ID"""
    while True:
        bill_id = f"B{uuid.uuid4().hex[:8].upper()}"
        if not bills_collection.find_one({'_id': bill_id}):
            return bill_id


def calculate_bill_amounts(data):
    """Calculate electric, water and total costs"""
    electric_usage = data['electric_end'] - data['electric_start']
    water_usage = data['water_end'] - data['water_start']
    electric_cost = electric_usage * float(data['electric_price'])
    water_cost = water_usage * float(data['water_price'])
    room_price = float(data.get('room_price', 0))
    total_amount = room_price + electric_cost + water_cost
    
    return {
        'electric_usage': electric_usage,
        'water_usage': water_usage,
        'electric_cost': electric_cost,
        'water_cost': water_cost,
        'room_price': room_price,
        'total_amount': total_amount
    }


def create_bill_document(data, due_date):
    """Create a new bill document"""
    amounts = calculate_bill_amounts(data)
    
    return {
        '_id': generate_bill_id(),
        'tenant_id': data['tenant_id'],
        'room_id': data['room_id'],
        'month': data['month'],
        'room_price': amounts['room_price'],
        'electric_start': data['electric_start'],
        'electric_end': data['electric_end'],
        'water_start': data['water_start'],
        'water_end': data['water_end'],
        'electric_price': float(data['electric_price']),
        'water_price': float(data['water_price']),
        'total_amount': amounts['total_amount'],
        'status': 'unpaid',
        'payment_day': int(data.get('payment_day', 5)),
        'due_date': due_date,
        'created_at': get_timestamp()
    }


def format_bill_response(bill):
    """Format bill for API response"""
    if bill:
        bill['id'] = bill['_id']
    return bill


def get_user_id(current_user):
    """Get user ID from token payload"""
    return current_user.get('user_id') or current_user.get('id')
