# Report Service - Utility Functions
import datetime
import os
import requests
from model import bills_collection
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


# ============== External Service Calls ==============

def get_room_stats(token):
    """Get room statistics from room-service."""
    try:
        url = get_service_url('room-service')
        headers = {'Authorization': token} if token else {}
        response = requests.get(f"{url}/api/rooms/stats", headers=headers, timeout=10)
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"Error getting room stats: {e}")
    return None


def get_contracts(token, status=None):
    """Get contracts from contract-service."""
    try:
        url = get_service_url('contract-service')
        headers = {'Authorization': token} if token else {}
        endpoint = f"{url}/api/contracts"
        if status:
            endpoint += f"?status={status}"
        response = requests.get(endpoint, headers=headers, timeout=10)
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"Error getting contracts: {e}")
    return None


def get_contract_detail(contract_id, token):
    """Get contract detail from contract-service."""
    try:
        url = get_service_url('contract-service')
        headers = {'Authorization': token} if token else {}
        response = requests.get(f"{url}/api/contracts/{contract_id}", headers=headers, timeout=10)
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"Error getting contract detail: {e}")
    return None


def get_room_contracts(room_id, token):
    """Get contracts for a specific room."""
    try:
        url = get_service_url('contract-service')
        headers = {'Authorization': token} if token else {}
        response = requests.get(f"{url}/api/contracts?room_id={room_id}", headers=headers, timeout=10)
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"Error getting room contracts: {e}")
    return None


def get_room_detail(room_id, token):
    """Get room detail from room-service."""
    try:
        url = get_service_url('room-service')
        headers = {'Authorization': token} if token else {}
        response = requests.get(f"{url}/api/rooms/{room_id}", headers=headers, timeout=10)
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"Error getting room detail: {e}")
    return None


def get_payments(token, status=None):
    """Get payments from payment-service."""
    try:
        url = get_service_url('payment-service')
        headers = {'Authorization': token} if token else {}
        endpoint = f"{url}/api/payments"
        if status:
            endpoint += f"?status={status}"
        response = requests.get(endpoint, headers=headers, timeout=10)
        if response.ok:
            return response.json()
    except Exception as e:
        print(f"Error getting payments: {e}")
    return None

def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


def format_bill(bill):
# Format bill for response
    
    bill['id'] = bill['_id']
    return bill


def calculate_bill_amounts(data):
# Calculate bill amounts
    
    electric_used = data['electric_new'] - data['electric_old']
    water_used = data['water_new'] - data['water_old']
    
    electric_cost = electric_used * float(data.get('electric_price', 3500))
    water_cost = water_used * float(data.get('water_price', 20000))
    room_rent = float(data.get('room_rent', 0))
    other_fees = float(data.get('other_fees', 0))
    
    return {
        'electric_used': electric_used,
        'water_used': water_used,
        'electric_cost': electric_cost,
        'water_cost': water_cost,
        'room_rent': room_rent,
        'other_fees': other_fees,
        'total_amount': room_rent + electric_cost + water_cost + other_fees
    }


def get_bill_stats():
# Get bill statistics
    
    return {
        'total': bills_collection.count_documents({}),
        'paid': bills_collection.count_documents({'status': 'paid'}),
        'unpaid': bills_collection.count_documents({'status': 'unpaid'}),
        'partial': bills_collection.count_documents({'status': 'partial'})
    }


def get_total_revenue(year=None):
# Calculate total revenue from paid bills, optionally filtered by year
    
    match_query = {'status': 'paid'}
    
    # Filter by year if provided
    if year:
        year_str = str(year)
        match_query['$or'] = [
            {'month': {'$regex': f'^{year_str}'}},  # String format "2025-12"
            {'year': int(year)}  # Legacy numeric format
        ]
    
    # Try both 'total' and 'total_amount' fields for compatibility
    pipeline = [
        {'$match': match_query},
        {'$group': {'_id': None, 'total': {'$sum': {'$ifNull': ['$total', {'$ifNull': ['$total_amount', 0]}]}}}}
    ]
    result = list(bills_collection.aggregate(pipeline))
    return result[0]['total'] if result else 0


def get_total_debt():
# Calculate total debt from unpaid/partial bills
    
    # Calculate debt as total - paid_amount, or use debt_amount if exists
    pipeline = [
        {'$match': {'status': {'$in': ['unpaid', 'partial']}}},
        {'$project': {
            'debt': {'$subtract': [
                {'$ifNull': ['$total', {'$ifNull': ['$total_amount', 0]}]},
                {'$ifNull': ['$paid_amount', 0]}
            ]}
        }},
        {'$group': {'_id': None, 'total': {'$sum': '$debt'}}}
    ]
    result = list(bills_collection.aggregate(pipeline))
    return result[0]['total'] if result else 0


def get_revenue_by_month(year):
# Get revenue aggregated by month - handles string month format like '2025-12'
    
    year_str = str(year)
    
    # Match bills where month starts with the year (e.g., "2025-12" starts with "2025")
    pipeline = [
        {'$match': {
            'status': 'paid',
            '$or': [
                {'month': {'$regex': f'^{year_str}'}},  # String format "2025-12"
                {'year': int(year)}  # Legacy numeric format
            ]
        }},
        {'$project': {
            'total': {'$ifNull': ['$total', {'$ifNull': ['$total_amount', 0]}]},
            'month_num': {
                '$cond': {
                    'if': {'$eq': [{'$type': '$month'}, 'string']},
                    'then': {'$toInt': {'$substr': ['$month', 5, 2]}},  # Extract month from "2025-12"
                    'else': '$month'
                }
            }
        }},
        {'$group': {
            '_id': '$month_num',
            'revenue': {'$sum': '$total'},
            'bills_count': {'$sum': 1}
        }},
        {'$sort': {'_id': 1}}
    ]
    return list(bills_collection.aggregate(pipeline))


def get_deposits_by_month(payments, year):
# Calculate deposits by month from completed payments
    
    deposits_by_month = {}
    for payment in payments:
        try:
            # Only count completed room reservation deposits
            if payment.get('status') != 'completed':
                continue
            if payment.get('payment_type') != 'room_reservation_deposit':
                continue
            
            # Parse created_at timestamp
            created_str = payment.get('created_at', payment.get('updated_at', ''))
            if not created_str:
                continue
            
            created = datetime.datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            if created.year == int(year):
                month = created.month
                amount = float(payment.get('amount', payment.get('amount_vnd', 0)))
                deposits_by_month[month] = deposits_by_month.get(month, 0) + amount
        except Exception as e:
            print(f"Error processing payment for deposit: {e}")
            pass
    return deposits_by_month
