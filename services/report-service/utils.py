# Report Service - Utility Functions
import datetime
from model import bills_collection


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


def get_total_revenue():
# Calculate total revenue from paid bills
    
    # Try both 'total' and 'total_amount' fields for compatibility
    pipeline = [
        {'$match': {'status': 'paid'}},
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
