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


@app.route('/api/bookings/<booking_id>/pay-deposit', methods=['PUT'])
@token_required
def pay_deposit(current_user, booking_id):
    """Mark deposit as paid (cash payment)"""
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    user_id = current_user.get('user_id') or current_user.get('_id')
    if booking['user_id'] != user_id:
        return jsonify({'message': 'Không có quyền!'}), 403
    
    if booking['deposit_status'] == 'paid':
        return jsonify({'message': 'Đã thanh toán cọc rồi!'}), 400
    
    data = request.get_json() or {}
    
    bookings_collection.update_one(
        {'_id': booking_id},
        {'$set': {
            'deposit_status': 'paid',
            'deposit_paid_at': get_timestamp(),
            'payment_method': data.get('payment_method', 'cash'),
            'status': 'deposit_paid',
            'updated_at': get_timestamp()
        }}
    )
    
    return jsonify({'message': 'Thanh toán cọc thành công!'}), 200


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
    
    if booking['status'] in ['approved', 'cancelled']:
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


# ============== Admin Booking APIs ==============

@app.route('/api/bookings/<booking_id>/approve', methods=['PUT'])
@token_required
@admin_required
def approve_booking(current_user, booking_id):
    """Approve a booking (admin only)"""
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    if booking['status'] not in ['pending', 'deposit_paid']:
        return jsonify({'message': f"Không thể duyệt booking đã {booking['status']}!"}), 400
    
    # Check if deposit is paid
    if booking['deposit_status'] != 'paid':
        return jsonify({'message': 'Người đặt chưa thanh toán cọc!'}), 400
    
    data = request.get_json() or {}
    
    bookings_collection.update_one(
        {'_id': booking_id},
        {'$set': {
            'status': 'approved',
            'admin_note': data.get('admin_note', ''),
            'updated_at': get_timestamp()
        }}
    )
    
    return jsonify({
        'message': 'Duyệt booking thành công! Vui lòng tạo hợp đồng cho người thuê.',
        'booking_id': booking_id
    }), 200


@app.route('/api/bookings/<booking_id>/reject', methods=['PUT'])
@token_required
@admin_required
def reject_booking(current_user, booking_id):
    """Reject a booking (admin only)"""
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    if booking['status'] in ['approved', 'cancelled', 'rejected']:
        return jsonify({'message': f"Booking đã được {booking['status']}!"}), 400
    
    data = request.get_json() or {}
    
    update = {
        'status': 'rejected',
        'admin_note': data.get('reason', ''),
        'updated_at': get_timestamp()
    }
    
    # Refund deposit if paid
    if booking['deposit_status'] == 'paid':
        update['deposit_status'] = 'refunded'
    
    bookings_collection.update_one({'_id': booking_id}, {'$set': update})
    
    return jsonify({'message': 'Từ chối booking thành công!'}), 200


# ============== Entry Point ==============

if __name__ == '__main__':
    print(f"\n{'='*50}")
    print(f"  {Config.SERVICE_NAME.upper()}")
    print(f"  Port: {Config.SERVICE_PORT}")
    print(f"{'='*50}\n")
    
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)
