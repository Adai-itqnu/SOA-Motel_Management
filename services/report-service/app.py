"""Report Service - Main Application"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import atexit

from config import Config
from model import bills_collection
from decorators import token_required, admin_required
from services import (
    get_room_stats, get_contracts, get_contract_detail,
    get_room_contracts, get_room_detail
)
from utils import (
    get_timestamp, format_bill, calculate_bill_amounts,
    get_bill_stats, get_total_revenue, get_total_debt,
    get_revenue_by_month, get_deposits_by_month
)
from service_registry import register_service, deregister_service


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
atexit.register(deregister_service)


# ============== Health Check ==============

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': Config.SERVICE_NAME}), 200


# ============== Bill APIs ==============

@app.route('/api/bills', methods=['POST'])
@token_required
@admin_required
def create_bill(current_user):
    """Create a new bill"""
    data = request.get_json() or {}
    
    required = ['contract_id', 'room_id', 'month', 'year', 'electric_old', 'electric_new', 'water_old', 'water_new']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400
    
    # Check duplicate
    if bills_collection.find_one({
        'contract_id': data['contract_id'],
        'month': data['month'],
        'year': data['year']
    }):
        return jsonify({'message': 'Hóa đơn tháng này đã tồn tại!'}), 400
    
    amounts = calculate_bill_amounts(data)
    bill_count = bills_collection.count_documents({})
    
    new_bill = {
        '_id': f"B{bill_count + 1:05d}",
        'contract_id': data['contract_id'],
        'room_id': data['room_id'],
        'tenant_id': data.get('tenant_id', ''),
        'month': data['month'],
        'year': data['year'],
        'electric_old': data['electric_old'],
        'electric_new': data['electric_new'],
        'electric_used': amounts['electric_used'],
        'electric_price': float(data.get('electric_price', 3500)),
        'electric_cost': amounts['electric_cost'],
        'water_old': data['water_old'],
        'water_new': data['water_new'],
        'water_used': amounts['water_used'],
        'water_price': float(data.get('water_price', 20000)),
        'water_cost': amounts['water_cost'],
        'room_rent': amounts['room_rent'],
        'other_fees': amounts['other_fees'],
        'total_amount': amounts['total_amount'],
        'paid_amount': 0,
        'debt_amount': amounts['total_amount'],
        'status': 'unpaid',
        'due_date': data.get('due_date', ''),
        'notes': data.get('notes', ''),
        'created_at': get_timestamp(),
        'updated_at': get_timestamp()
    }
    
    try:
        bills_collection.insert_one(new_bill)
        return jsonify({
            'message': 'Tạo hóa đơn thành công!',
            'bill': format_bill(new_bill)
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500


@app.route('/api/bills/<bill_id>/pay', methods=['PUT'])
@token_required
@admin_required
def pay_bill(current_user, bill_id):
    """Process bill payment"""
    data = request.get_json() or {}
    
    if 'amount' not in data:
        return jsonify({'message': 'Thiếu số tiền!'}), 400
    
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    amount = float(data['amount'])
    new_paid = bill['paid_amount'] + amount
    new_debt = max(0, bill['total_amount'] - new_paid)
    
    status = 'paid' if new_debt <= 0 else ('partial' if new_paid > 0 else 'unpaid')
    
    try:
        bills_collection.update_one({'_id': bill_id}, {'$set': {
            'paid_amount': new_paid,
            'debt_amount': new_debt,
            'status': status,
            'payment_date': get_timestamp() if status == 'paid' else bill.get('payment_date', ''),
            'updated_at': get_timestamp()
        }})
        return jsonify({
            'message': 'Thanh toán thành công!',
            'paid_amount': new_paid,
            'debt_amount': new_debt,
            'status': status
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500


@app.route('/api/bills', methods=['GET'])
@token_required
@admin_required
def get_bills(current_user):
    """Get list of bills"""
    query = {}
    for param in ['status', 'room_id']:
        if request.args.get(param):
            query[param] = request.args.get(param)
    for param in ['month', 'year']:
        if request.args.get(param):
            query[param] = int(request.args.get(param))
    
    bills = list(bills_collection.find(query).sort('created_at', -1))
    for b in bills:
        format_bill(b)
    
    return jsonify({'bills': bills, 'total': len(bills)}), 200


# ============== Report APIs ==============

@app.route('/api/reports/overview', methods=['GET'])
@token_required
@admin_required
def get_overview(current_user):
    """Get overview report"""
    token = request.headers.get('Authorization')
    
    rooms = get_room_stats(token) or {'total': 0, 'available': 0, 'occupied': 0, 'occupancy_rate': 0}
    active_contracts = get_contracts(token, 'active')
    all_contracts = get_contracts(token)
    
    bill_stats = get_bill_stats()
    revenue_bills = get_total_revenue()
    
    # Calculate deposit revenue
    deposit_revenue = 0
    if all_contracts and all_contracts.get('contracts'):
        deposit_revenue = sum(float(c.get('deposit', 0)) for c in all_contracts['contracts'])
    
    total_revenue = revenue_bills + deposit_revenue
    total_debt = get_total_debt()
    
    return jsonify({
        'rooms': rooms,
        'contracts': {'active': active_contracts['total'] if active_contracts else 0},
        'bills': bill_stats,
        'finance': {
            'total_revenue': total_revenue,
            'total_debt': total_debt,
            'collection_rate': round((total_revenue / (total_revenue + total_debt) * 100) if (total_revenue + total_debt) > 0 else 0, 2)
        }
    }), 200


@app.route('/api/reports/revenue', methods=['GET'])
@token_required
@admin_required
def get_revenue(current_user):
    """Get monthly revenue report"""
    year = request.args.get('year', datetime.datetime.now().year)
    token = request.headers.get('Authorization')
    
    bills_by_month = get_revenue_by_month(year)
    contracts_data = get_contracts(token)
    deposits = get_deposits_by_month(contracts_data.get('contracts', []) if contracts_data else [], year)
    
    monthly_data = []
    for month in range(1, 13):
        month_bills = next((m for m in bills_by_month if m['_id'] == month), None)
        bills_rev = month_bills['revenue'] if month_bills else 0
        deps_rev = deposits.get(month, 0)
        
        monthly_data.append({
            'month': month,
            'revenue': bills_rev + deps_rev,
            'bills_revenue': bills_rev,
            'deposits_revenue': deps_rev,
            'bills_count': month_bills['bills_count'] if month_bills else 0
        })
    
    return jsonify({
        'year': int(year),
        'total_revenue': sum(m['revenue'] for m in monthly_data),
        'monthly_data': monthly_data
    }), 200


@app.route('/api/reports/debt', methods=['GET'])
@token_required
@admin_required
def get_debt(current_user):
    """Get debt report"""
    token = request.headers.get('Authorization')
    
    debt_bills = list(bills_collection.find({
        'status': {'$in': ['unpaid', 'partial']}
    }).sort('due_date', 1))
    
    now = datetime.datetime.now()
    overdue_count = 0
    
    for bill in debt_bills:
        format_bill(bill)
        
        # Get tenant info from contract
        if bill.get('contract_id'):
            contract = get_contract_detail(bill['contract_id'], token)
            if contract:
                bill['tenant_name'] = contract.get('tenant_info', {}).get('name', '')
                bill['tenant_phone'] = contract.get('tenant_info', {}).get('phone', '')
        
        # Calculate overdue days
        if bill.get('due_date'):
            try:
                due = datetime.datetime.fromisoformat(bill['due_date'])
                days = (now - due).days
                bill['days_overdue'] = days if days > 0 else 0
                if days > 0:
                    overdue_count += 1
            except:
                bill['days_overdue'] = 0
    
    return jsonify({
        'total_debt': sum(b['debt_amount'] for b in debt_bills),
        'total_bills': len(debt_bills),
        'overdue_bills': overdue_count,
        'details': debt_bills
    }), 200


@app.route('/api/reports/room/<room_id>', methods=['GET'])
@token_required
@admin_required
def get_room_report(current_user, room_id):
    """Get room-specific report"""
    token = request.headers.get('Authorization')
    
    room = get_room_detail(room_id, token)
    contracts = get_room_contracts(room_id, token)
    bills = list(bills_collection.find({'room_id': room_id}).sort('created_at', -1))
    
    for b in bills:
        format_bill(b)
    
    return jsonify({
        'room': room,
        'contracts': contracts.get('contracts', []) if contracts else [],
        'bills': bills,
        'statistics': {
            'total_bills': len(bills),
            'total_revenue': sum(b['total_amount'] for b in bills if b['status'] == 'paid'),
            'total_debt': sum(b['debt_amount'] for b in bills if b['status'] in ['unpaid', 'partial'])
        }
    }), 200


@app.route('/api/reports/export', methods=['GET'])
@token_required
@admin_required
def export_report(current_user):
    """Export report (placeholder)"""
    return jsonify({
        'message': 'Tính năng xuất Excel đang được phát triển',
        'report_type': request.args.get('type', 'overview')
    }), 501


# ============== Entry Point ==============

if __name__ == '__main__':
    print(f"\n{'='*50}\n  {Config.SERVICE_NAME.upper()}\n  Port: {Config.SERVICE_PORT}\n{'='*50}\n")
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)