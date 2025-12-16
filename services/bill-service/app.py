"""Bill Service - Main Application"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import uuid
import atexit

from config import Config
from model import bills_collection
from decorators import token_required, admin_required, internal_api_required
from service_registry import register_service, deregister_service


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
atexit.register(deregister_service)


def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


def generate_bill_id():
    return f"BILL{uuid.uuid4().hex[:8].upper()}"


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


def calculate_bill(data):
    """Calculate bill amounts"""
    electric_usage = data.get('electric_new', 0) - data.get('electric_old', 0)
    water_usage = data.get('water_new', 0) - data.get('water_old', 0)
    
    electric_fee = electric_usage * data.get('electric_price', 3500)
    water_fee = water_usage * data.get('water_price', 15000)
    room_fee = data.get('room_fee', 0)
    other_fee = data.get('other_fee', 0)
    
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


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': Config.SERVICE_NAME}), 200


@app.route('/api/bills', methods=['GET'])
@token_required
def get_bills(current_user):
    """Get bills list (admin sees all, user sees own)"""
    user_id = current_user.get('user_id') or current_user.get('_id')
    role = current_user.get('role', '')
    
    query = {} if role == 'admin' else {'user_id': user_id}
    
    for param in ['room_id', 'contract_id', 'status', 'month']:
        value = request.args.get(param)
        if value:
            query[param] = value
    
    bills = list(bills_collection.find(query).sort('created_at', -1))
    
    return jsonify({
        'bills': [format_bill(b) for b in bills],
        'total': len(bills)
    }), 200


@app.route('/api/bills/<bill_id>', methods=['GET'])
@token_required
def get_bill(current_user, bill_id):
    """Get single bill details"""
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    user_id = current_user.get('user_id') or current_user.get('_id')
    role = current_user.get('role', '')
    
    if role != 'admin' and bill['user_id'] != user_id:
        return jsonify({'message': 'Không có quyền xem hóa đơn này!'}), 403
    
    return jsonify(format_bill(bill)), 200


@app.route('/api/bills/calculate', methods=['POST'])
@token_required
def preview_bill(current_user):
    """Calculate bill preview"""
    data = request.get_json() or {}
    return jsonify(calculate_bill(data)), 200


@app.route('/api/bills', methods=['POST'])
@token_required
@admin_required
def create_bill(current_user):
    """Create a new bill (admin only)"""
    data = request.get_json() or {}
    
    required = ['contract_id', 'room_id', 'user_id', 'month', 
                'electric_old', 'electric_new', 'water_old', 'water_new', 'room_fee']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400
    
    # Check duplicate
    existing = bills_collection.find_one({
        'contract_id': data['contract_id'],
        'month': data['month']
    })
    if existing:
        return jsonify({'message': 'Hóa đơn tháng này đã tồn tại!'}), 400
    
    # Calculate amounts
    amounts = calculate_bill({
        'electric_old': float(data['electric_old']),
        'electric_new': float(data['electric_new']),
        'water_old': float(data['water_old']),
        'water_new': float(data['water_new']),
        'electric_price': float(data.get('electric_price', 3500)),
        'water_price': float(data.get('water_price', 15000)),
        'room_fee': float(data['room_fee']),
        'other_fee': float(data.get('other_fee', 0))
    })
    
    timestamp = get_timestamp()
    bill_id = generate_bill_id()
    
    new_bill = {
        '_id': bill_id,
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
    
    try:
        bills_collection.insert_one(new_bill)
        return jsonify({
            'message': 'Tạo hóa đơn thành công!',
            'bill': format_bill(new_bill)
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500


@app.route('/api/bills/<bill_id>', methods=['PUT'])
@token_required
@admin_required
def update_bill(current_user, bill_id):
    """Update bill (admin only)"""
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    if bill['status'] == 'paid':
        return jsonify({'message': 'Không thể cập nhật hóa đơn đã thanh toán!'}), 400
    
    data = request.get_json() or {}
    
    allowed = ['electric_old', 'electric_new', 'water_old', 'water_new', 
               'room_fee', 'other_fee', 'due_date']
    update_fields = {k: data[k] for k in allowed if k in data}
    
    if not update_fields:
        return jsonify({'message': 'Không có dữ liệu cập nhật!'}), 400
    
    # Recalculate if meter fields changed
    if any(k in update_fields for k in ['electric_old', 'electric_new', 'water_old', 'water_new', 'room_fee']):
        merged = {**bill, **update_fields}
        amounts = calculate_bill({
            'electric_old': merged['electric_old'],
            'electric_new': merged['electric_new'],
            'water_old': merged['water_old'],
            'water_new': merged['water_new'],
            'electric_price': bill.get('electric_price', 3500),
            'water_price': bill.get('water_price', 15000),
            'room_fee': merged['room_fee'],
            'other_fee': merged.get('other_fee', 0)
        })
        update_fields['electric_fee'] = amounts['electric_fee']
        update_fields['water_fee'] = amounts['water_fee']
        update_fields['total'] = amounts['total']
    
    bills_collection.update_one({'_id': bill_id}, {'$set': update_fields})
    updated = bills_collection.find_one({'_id': bill_id})
    
    return jsonify({
        'message': 'Cập nhật thành công!',
        'bill': format_bill(updated)
    }), 200


@app.route('/api/bills/<bill_id>/pay', methods=['PUT'])
@token_required
def pay_bill(current_user, bill_id):
    """Mark bill as paid"""
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    user_id = current_user.get('user_id') or current_user.get('_id')
    role = current_user.get('role', '')
    
    # Only admin or bill owner can pay
    if role != 'admin' and bill['user_id'] != user_id:
        return jsonify({'message': 'Không có quyền!'}), 403
    
    if bill['status'] == 'paid':
        return jsonify({'message': 'Hóa đơn đã được thanh toán!'}), 400
    
    bills_collection.update_one(
        {'_id': bill_id},
        {'$set': {
            'status': 'paid',
            'paid_at': get_timestamp()
        }}
    )
    
    return jsonify({'message': 'Thanh toán thành công!'}), 200


@app.route('/api/bills/<bill_id>/status', methods=['PUT'])
@internal_api_required
def update_bill_status_internal(bill_id):
    """Internal endpoint for other services (e.g., payment-service) to update bill status."""
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404

    data = request.get_json() or {}
    status = (data.get('status') or '').strip()
    if status not in ['pending', 'paid']:
        return jsonify({'message': 'Trạng thái hóa đơn không hợp lệ!'}), 400

    update = {'status': status}
    if status == 'paid':
        update['paid_at'] = get_timestamp()
    else:
        update['paid_at'] = None

    bills_collection.update_one({'_id': bill_id}, {'$set': update})
    return jsonify({'message': 'Cập nhật trạng thái hóa đơn thành công!', 'bill_id': bill_id}), 200


@app.route('/api/bills/<bill_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_bill(current_user, bill_id):
    """Delete bill (admin only)"""
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    if bill['status'] == 'paid':
        return jsonify({'message': 'Không thể xóa hóa đơn đã thanh toán!'}), 400
    
    bills_collection.delete_one({'_id': bill_id})
    return jsonify({'message': 'Xóa thành công!'}), 200


# ============== Admin: Manual trigger for bill generation ==============

@app.route('/api/bills/generate-monthly', methods=['POST'])
@token_required
@admin_required
def trigger_generate_bills(current_user):
    """Manually trigger monthly bill generation (admin only)"""
    from scheduler import trigger_bill_generation
    try:
        trigger_bill_generation()
        return jsonify({'message': 'Đã tạo hóa đơn tháng này thành công!'}), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500


# ============== Admin: Finalize draft bill (update meters -> pending) ==============

@app.route('/api/bills/<bill_id>/finalize', methods=['PUT'])
@token_required
@admin_required
def finalize_bill(current_user, bill_id):
    """Update draft bill with meter readings and change to pending status"""
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    if bill['status'] != 'draft':
        return jsonify({'message': 'Chỉ có thể cập nhật hóa đơn ở trạng thái draft!'}), 400
    
    data = request.get_json() or {}
    
    electric_new = data.get('electric_new')
    water_new = data.get('water_new')
    
    if electric_new is None or water_new is None:
        return jsonify({'message': 'Vui lòng nhập số điện và nước mới!'}), 400
    
    # Calculate fees
    electric_old = bill.get('electric_old', 0)
    water_old = bill.get('water_old', 0)
    electric_price = float(bill.get('electric_price', 3500))
    water_price = float(bill.get('water_price', 15000))
    room_fee = float(bill.get('room_fee', 0))
    other_fee = float(data.get('other_fee', bill.get('other_fee', 0)))
    
    electric_usage = max(0, float(electric_new) - electric_old)
    water_usage = max(0, float(water_new) - water_old)
    
    electric_fee = electric_usage * electric_price
    water_fee = water_usage * water_price
    total = room_fee + electric_fee + water_fee + other_fee
    
    # Update bill
    update_data = {
        'electric_new': float(electric_new),
        'electric_fee': electric_fee,
        'water_new': float(water_new),
        'water_fee': water_fee,
        'other_fee': other_fee,
        'total': total,
        'status': 'pending',
        'updated_at': get_timestamp()
    }
    
    bills_collection.update_one({'_id': bill_id}, {'$set': update_data})
    
    updated_bill = bills_collection.find_one({'_id': bill_id})
    return jsonify({
        'message': 'Cập nhật hóa đơn thành công! Đã chuyển sang trạng thái chờ thanh toán.',
        'bill': format_bill(updated_bill)
    }), 200


# ============== Internal APIs ==============

@app.route('/internal/bills/unpaid', methods=['GET'])
@internal_api_required
def internal_get_unpaid_bills():
    """Get unpaid bills with due dates for notification reminders"""
    bills = list(bills_collection.find({
        'status': {'$in': ['pending', 'partial']}
    }))
    
    return jsonify({
        'bills': [{
            '_id': b['_id'],
            'contract_id': b.get('contract_id', ''),
            'room_id': b.get('room_id', ''),
            'tenant_id': b.get('user_id', ''),
            'total_amount': b.get('total', 0),
            'due_date': b.get('due_date', ''),
            'status': b.get('status', 'pending')
        } for b in bills]
    }), 200


if __name__ == '__main__':
    print(f"\n{'='*50}\n  {Config.SERVICE_NAME.upper()}\n  Port: {Config.SERVICE_PORT}\n{'='*50}\n")
    
    # Start scheduler for automatic bill generation
    from scheduler import start_scheduler
    scheduler = start_scheduler()
    atexit.register(scheduler.shutdown)
    
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)

