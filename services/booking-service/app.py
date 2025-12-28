"""
Booking Service - Main Application
Handles room booking requests with deposit payment
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import atexit

from config import Config
from model import bookings_collection
from decorators import token_required, admin_required, internal_api_required
from utils import (
    get_timestamp, generate_booking_id, format_booking_response
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


# ============== User Booking APIs ==============

@app.route('/api/bookings', methods=['POST'])
@token_required
def create_booking(current_user):
    """Create a new booking request"""
    data = request.get_json() or {}
    
    # Validate required fields
    required = ['room_id', 'check_in_date']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400
    
    # Get user info
    user_id = current_user.get('user_id') or current_user.get('_id')
    if not user_id:
        return jsonify({'message': 'Không tìm thấy thông tin user!'}), 400
    
    # Create booking document matching new schema
    timestamp = get_timestamp()
    booking_id = generate_booking_id()
    
    new_booking = {
        '_id': booking_id,
        'room_id': data['room_id'],
        'user_id': user_id,
        'check_in_date': data['check_in_date'],
        'message': data.get('message', ''),
        'deposit_amount': float(data.get('deposit_amount', 0)),
        'deposit_status': 'pending',
        'deposit_paid_at': None,
        'payment_method': data.get('payment_method', 'cash'),
        'status': 'pending',
        'admin_note': '',
        'created_at': timestamp,
        'updated_at': timestamp
    }
    
    try:
        bookings_collection.insert_one(new_booking)
        return jsonify({
            'message': 'Đặt phòng thành công! Vui lòng thanh toán cọc để giữ phòng.',
            'booking': format_booking_response(new_booking)
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo booking: {str(e)}'}), 500


@app.route('/api/bookings', methods=['GET'])
@token_required
def get_bookings(current_user):
    """Get bookings list (user sees own, admin sees all)"""
    user_id = current_user.get('user_id') or current_user.get('_id')
    role = current_user.get('role', '')
    
    query = {} if role == 'admin' else {'user_id': user_id}
    
    status = request.args.get('status', '').strip()
    if status:
        query['status'] = status
    
    bookings = list(bookings_collection.find(query).sort('created_at', -1))
    
    return jsonify({
        'bookings': [format_booking_response(b) for b in bookings],
        'total': len(bookings)
    }), 200


@app.route('/api/bookings/<booking_id>', methods=['GET'])
@token_required
def get_booking(current_user, booking_id):
    """Get single booking details"""
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    user_id = current_user.get('user_id') or current_user.get('_id')
    role = current_user.get('role', '')
    
    # Check permission
    if role != 'admin' and booking['user_id'] != user_id:
        return jsonify({'message': 'Không có quyền xem booking này!'}), 403
    
    return jsonify(format_booking_response(booking)), 200


@app.route('/api/bookings/<booking_id>/deposit-status', methods=['PUT'])
@internal_api_required
def update_deposit_status_internal(booking_id):
    """Internal endpoint for payment-service to update deposit status (e.g., VNPay IPN)."""
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404

    data = request.get_json() or {}
    status = (data.get('status') or '').strip()
    transaction_id = data.get('transaction_id')
    payment_id = data.get('payment_id')

    if status not in ['paid', 'failed', 'refunded', 'pending']:
        return jsonify({'message': 'Trạng thái deposit không hợp lệ!'}), 400

    update = {
        'deposit_status': status,
        'updated_at': get_timestamp(),
    }

    if transaction_id:
        update['deposit_transaction_id'] = transaction_id
    if payment_id:
        update['deposit_payment_id'] = payment_id

    # Only set paid metadata when success
    if status == 'paid':
        update['deposit_paid_at'] = get_timestamp()
        update['payment_method'] = 'vnpay'
        update['status'] = 'deposit_paid'

    bookings_collection.update_one({'_id': booking_id}, {'$set': update})
    return jsonify({'message': 'Cập nhật trạng thái cọc thành công!', 'booking_id': booking_id}), 200


@app.route('/api/bookings/<booking_id>/cancel', methods=['PUT'])
@token_required
def cancel_booking(current_user, booking_id):
    """Cancel own booking"""
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    user_id = current_user.get('user_id') or current_user.get('_id')
    if booking['user_id'] != user_id:
        return jsonify({'message': 'Không có quyền hủy booking này!'}), 403
    
    if booking['status'] in ['checked_in', 'cancelled']:
        return jsonify({'message': f"Không thể hủy booking đã {booking['status']}!"}), 400
    
    update = {
        'status': 'cancelled',
        'updated_at': get_timestamp()
    }
    
    # Refund deposit if paid
    if booking['deposit_status'] == 'paid':
        update['deposit_status'] = 'refunded'
    
    bookings_collection.update_one({'_id': booking_id}, {'$set': update})
    return jsonify({'message': 'Hủy booking thành công!'}), 200


# ============== User Check-in APIs ==============

import requests

def get_service_url(service_name):
    """Get service URL from Consul or fallback to environment"""
    import os
    # Fallback to environment variables
    service_map = {
        'contract-service': os.getenv('CONTRACT_SERVICE_URL', 'http://contract-service:5006'),
        'room-service': os.getenv('ROOM_SERVICE_URL', 'http://room-service:5002'),
        'payment-service': os.getenv('PAYMENT_SERVICE_URL', 'http://payment-service:5007'),
    }
    return service_map.get(service_name)


@app.route('/api/bookings/<booking_id>/check-in', methods=['POST'])
@token_required
def check_in_booking(current_user, booking_id):
    """User confirms check-in, system auto-creates contract"""
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    user_id = current_user.get('user_id') or current_user.get('_id')
    if booking['user_id'] != user_id:
        return jsonify({'message': 'Không có quyền check-in booking này!'}), 403
    
    # Check if deposit is paid
    if booking.get('deposit_status') != 'paid' and booking.get('status') != 'deposit_paid':
        return jsonify({'message': 'Bạn chưa thanh toán cọc!'}), 400
    
    # Check if already checked in
    if booking.get('status') == 'checked_in':
        return jsonify({'message': 'Bạn đã check-in rồi!'}), 400
    
    # Call contract-service to auto-create contract
    contract_service_url = get_service_url('contract-service')
    if not contract_service_url:
        return jsonify({'message': 'Không thể kết nối contract-service!'}), 503
    
    try:
        resp = requests.post(
            f"{contract_service_url}/internal/contracts/auto-create",
            json={
                'room_id': booking['room_id'],
                'tenant_id': str(user_id),
                'payment_id': booking.get('deposit_payment_id'),
                'check_in_date': booking.get('check_in_date')
            },
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=10,
        )
        
        if not resp.ok:
            error_msg = resp.json().get('message', 'Lỗi tạo hợp đồng') if resp.headers.get('content-type', '').startswith('application/json') else resp.text
            return jsonify({'message': error_msg}), resp.status_code
        
    except Exception as e:
        return jsonify({'message': f'Lỗi kết nối: {str(e)}'}), 503
    
    # Update booking status
    bookings_collection.update_one(
        {'_id': booking_id},
        {'$set': {
            'status': 'checked_in',
            'checked_in_at': get_timestamp(),
            'updated_at': get_timestamp()
        }}
    )
    
    return jsonify({
        'message': 'Check-in thành công! Hợp đồng đã được tạo tự động.',
        'booking_id': booking_id
    }), 200


@app.route('/api/bookings/check-in-from-payment', methods=['POST'])
@token_required
def check_in_from_payment(current_user):
    """Check-in directly from payment when no booking record exists"""
    data = request.get_json() or {}
    payment_id = data.get('payment_id')
    room_id = data.get('room_id')
    check_in_date = data.get('check_in_date')
    
    if not payment_id or not room_id:
        return jsonify({'message': 'Thiếu payment_id hoặc room_id!'}), 400
    
    user_id = current_user.get('user_id') or current_user.get('_id')
    
    # Check if already has active contract
    contract_service_url = get_service_url('contract-service')
    if not contract_service_url:
        return jsonify({'message': 'Không thể kết nối contract-service!'}), 503
    
    # Call contract-service to auto-create contract
    try:
        resp = requests.post(
            f"{contract_service_url}/internal/contracts/auto-create",
            json={
                'room_id': room_id,
                'tenant_id': str(user_id),
                'payment_id': payment_id,
                'check_in_date': check_in_date
            },
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=10,
        )
        
        if not resp.ok:
            error_msg = 'Lỗi tạo hợp đồng'
            try:
                error_msg = resp.json().get('message', error_msg)
            except:
                error_msg = resp.text or error_msg
            return jsonify({'message': error_msg}), resp.status_code
        
    except Exception as e:
        return jsonify({'message': f'Lỗi kết nối: {str(e)}'}), 503
    
    # Create a booking record for history
    timestamp = get_timestamp()
    booking_id = generate_booking_id()
    
    new_booking = {
        '_id': booking_id,
        'room_id': room_id,
        'user_id': user_id,
        'check_in_date': check_in_date or timestamp[:10],
        'deposit_amount': 0,  # We don't have this info here
        'deposit_status': 'paid',
        'deposit_payment_id': payment_id,
        'payment_method': 'vnpay',
        'status': 'checked_in',
        'checked_in_at': timestamp,
        'admin_note': 'Check-in từ thanh toán VNPay',
        'created_at': timestamp,
        'updated_at': timestamp
    }
    
    try:
        bookings_collection.insert_one(new_booking)
    except Exception as e:
        print(f"Warning: Could not create booking record: {e}")
    
    return jsonify({
        'message': 'Check-in thành công! Hợp đồng đã được tạo tự động.',
        'booking_id': booking_id
    }), 200


# ============== Internal APIs ==============

@app.route('/internal/bookings/create-from-payment', methods=['POST'])
@internal_api_required
def create_booking_from_payment():
    """Create booking record when room deposit payment is successful (called by payment-service)."""
    data = request.get_json() or {}
    
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    
    if not room_id or not user_id:
        return jsonify({'message': 'Missing room_id or user_id'}), 400
    
    # Check if booking already exists for this room and user
    existing = bookings_collection.find_one({
        'room_id': room_id,
        'user_id': user_id,
        'status': {'$in': ['pending', 'deposit_paid']}
    })
    if existing:
        # Update existing booking
        bookings_collection.update_one(
            {'_id': existing['_id']},
            {'$set': {
                'deposit_status': 'paid',
                'deposit_payment_id': data.get('deposit_payment_id'),
                'deposit_amount': data.get('deposit_amount', 0),
                'payment_method': data.get('payment_method', 'vnpay'),
                'status': 'deposit_paid',
                'check_in_date': data.get('check_in_date') or existing.get('check_in_date'),
                'updated_at': get_timestamp()
            }}
        )
        return jsonify({'message': 'Booking updated', 'booking_id': existing['_id']}), 200
    
    # Create new booking
    timestamp = get_timestamp()
    booking_id = generate_booking_id()
    
    new_booking = {
        '_id': booking_id,
        'room_id': room_id,
        'user_id': user_id,
        'check_in_date': data.get('check_in_date') or timestamp[:10],
        'deposit_amount': data.get('deposit_amount', 0),
        'deposit_status': 'paid',
        'deposit_paid_at': timestamp,
        'deposit_payment_id': data.get('deposit_payment_id'),
        'payment_method': data.get('payment_method', 'vnpay'),
        'status': 'deposit_paid',
        'created_at': timestamp,
        'updated_at': timestamp
    }
    
    try:
        bookings_collection.insert_one(new_booking)
        return jsonify({'message': 'Booking created', 'booking_id': booking_id}), 201
    except Exception as e:
        return jsonify({'message': f'Error creating booking: {str(e)}'}), 500


# ============== Entry Point ==============

if __name__ == '__main__':
    print(f"\n{'='*50}")
    print(f"  {Config.SERVICE_NAME.upper()}")
    print(f"  Port: {Config.SERVICE_PORT}")
    print(f"{'='*50}\n")
    
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)
