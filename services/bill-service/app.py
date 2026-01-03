from flask import Flask, request, jsonify
from flask_cors import CORS
import atexit

from config import Config
from model import bills_collection
from decorators import token_required, admin_required, internal_api_required
from service_registry import register_service, deregister_service
from utils import (
    generate_bill_id,
    get_timestamp,
    calculate_bill,
    calculate_finalize_fees,
    format_bill,
    format_unpaid_bill,
    create_bill_document,
    validate_bill_data,
    check_duplicate_bill,
    get_user_id,
    can_access_bill,
    send_notification
)


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
atexit.register(deregister_service)


# ============== Health Check ==============

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': Config.SERVICE_NAME}), 200


# ============== Bill APIs ==============

@app.route('/api/bills', methods=['GET'])
@token_required
# Get bills list (admin sees all, user sees own)
def get_bills(current_user):
    user_id = get_user_id(current_user)
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
# Get single bill details
def get_bill(current_user, bill_id):
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    if not can_access_bill(current_user, bill):
        return jsonify({'message': 'Không có quyền xem hóa đơn này!'}), 403
    
    return jsonify(format_bill(bill)), 200


@app.route('/api/bills/calculate', methods=['POST'])
@token_required
# Calculate bill preview
def preview_bill(current_user):
    data = request.get_json() or {}
    return jsonify(calculate_bill(data)), 200


@app.route('/api/bills', methods=['POST'])
@token_required
@admin_required
# Create a new bill (admin only)
def create_bill(current_user):
    data = request.get_json() or {}
    
    # Validate required fields
    missing = validate_bill_data(data)
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400
    
    # Check duplicate
    if check_duplicate_bill(data['contract_id'], data['month']):
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
    
    # Create bill document
    new_bill = create_bill_document(data, amounts)
    
    try:
        bills_collection.insert_one(new_bill)
        
        # Send notification to user
        send_notification(
            new_bill['user_id'],
            "Hóa đơn mới",
            f"Bạn có hóa đơn mới tháng {new_bill['month']} cần thanh toán.",
            "bill",
            {"bill_id": new_bill['_id']}
        )
        
        return jsonify({
            'message': 'Tạo hóa đơn thành công!',
            'bill': format_bill(new_bill)
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500


@app.route('/api/bills/<bill_id>', methods=['PUT'])
@token_required
@admin_required
# Update bill (admin only)
def update_bill(current_user, bill_id):
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
# Mark bill as paid
def pay_bill(current_user, bill_id):
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    if not can_access_bill(current_user, bill):
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
# Internal endpoint for other services to update bill status
def update_bill_status_internal(bill_id):
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
# Delete bill (admin only)
def delete_bill(current_user, bill_id):
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    if bill['status'] == 'paid':
        return jsonify({'message': 'Không thể xóa hóa đơn đã thanh toán!'}), 400
    
    bills_collection.delete_one({'_id': bill_id})
    return jsonify({'message': 'Xóa thành công!'}), 200


# ============== Admin APIs ==============

@app.route('/api/bills/generate-monthly', methods=['POST'])
@token_required
@admin_required
# Manually trigger monthly bill generation (admin only)
def trigger_generate_bills(current_user):
    from scheduler import trigger_bill_generation
    try:
        trigger_bill_generation()
        return jsonify({'message': 'Đã tạo hóa đơn tháng này thành công!'}), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500


@app.route('/api/bills/<bill_id>/finalize', methods=['PUT'])
@token_required
@admin_required
# Update draft bill with meter readings and change to pending status
def finalize_bill(current_user, bill_id):
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
    
    # Calculate fees using utility function
    fees = calculate_finalize_fees(bill, electric_new, water_new, data.get('other_fee'))
    
    # Update bill
    update_data = {
        **fees,
        'status': 'pending',
        'updated_at': get_timestamp()
    }
    
    bills_collection.update_one({'_id': bill_id}, {'$set': update_data})
    
    updated_bill = bills_collection.find_one({'_id': bill_id})
    
    # Send notification to user
    send_notification(
        updated_bill['user_id'],
        "Hóa đơn điện nước",
        f"Hóa đơn tháng {updated_bill['month']} đã được chốt số điện nước. Vui lòng kiểm tra và thanh toán.",
        "bill",
        {"bill_id": updated_bill['_id']}
    )
    
    return jsonify({
        'message': 'Cập nhật hóa đơn thành công! Đã chuyển sang trạng thái chờ thanh toán.',
        'bill': format_bill(updated_bill)
    }), 200


# ============== Internal APIs ==============

@app.route('/internal/bills/unpaid', methods=['GET'])
@internal_api_required
# Get unpaid bills for notification reminders
def internal_get_unpaid_bills():
    bills = list(bills_collection.find({
        'status': {'$in': ['pending', 'partial']}
    }))
    
    return jsonify({
        'bills': [format_unpaid_bill(b) for b in bills]
    }), 200


# ============== Entry Point ==============

if __name__ == '__main__':
    print(f"\n{'='*50}\n  {Config.SERVICE_NAME.upper()}\n  Port: {Config.SERVICE_PORT}\n{'='*50}\n")
    
    # Start scheduler for automatic bill generation
    from scheduler import start_scheduler
    scheduler = start_scheduler()
    atexit.register(scheduler.shutdown)
    
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)
