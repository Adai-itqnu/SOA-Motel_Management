from flask import Flask, request, jsonify
from flask_cors import CORS
import atexit

from config import Config
from model import bookings_collection
from decorators import token_required, admin_required, internal_api_required
from utils import (
    get_timestamp,
    generate_booking_id,
    format_booking_response,
    get_user_id,
    can_access_booking,
    is_booking_owner,
    validate_booking_data,
    can_cancel_booking,
    is_deposit_paid,
    is_checked_in,
    create_booking_document,
    create_checkin_booking_document,
    create_booking_from_payment_data,
    find_pending_booking,
    get_service_url
)
from service_registry import register_service, deregister_service
import requests


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
# Create a new booking request
def create_booking(current_user):
    data = request.get_json() or {}
    
    # Validate required fields
    missing = validate_booking_data(data)
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400
    
    # Get user info
    user_id = get_user_id(current_user)
    if not user_id:
        return jsonify({'message': 'Không tìm thấy thông tin user!'}), 400
    
    # Create booking document
    new_booking = create_booking_document(data, user_id)
    
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
# Get bookings list (user sees own, admin sees all)
def get_bookings(current_user):
    user_id = get_user_id(current_user)
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
# Get single booking details
def get_booking(current_user, booking_id):
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    if not can_access_booking(current_user, booking):
        return jsonify({'message': 'Không có quyền xem booking này!'}), 403
    
    return jsonify(format_booking_response(booking)), 200


@app.route('/api/bookings/<booking_id>/deposit', methods=['PUT'])
@internal_api_required
# Internal endpoint for payment-service to update deposit status
def update_deposit_status_internal(booking_id):
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404

    data = request.get_json() or {}
    status = (data.get('status') or '').strip()
    
    if status not in ['paid', 'failed', 'refunded', 'pending']:
        return jsonify({'message': 'Trạng thái deposit không hợp lệ!'}), 400

    update = {
        'deposit_status': status,
        'updated_at': get_timestamp(),
    }

    if data.get('transaction_id'):
        update['deposit_transaction_id'] = data['transaction_id']
    if data.get('payment_id'):
        update['deposit_payment_id'] = data['payment_id']

    if status == 'paid':
        update['deposit_paid_at'] = get_timestamp()
        update['payment_method'] = 'vnpay'
        update['status'] = 'deposit_paid'

    bookings_collection.update_one({'_id': booking_id}, {'$set': update})
    return jsonify({'message': 'Cập nhật trạng thái cọc thành công!', 'booking_id': booking_id}), 200


@app.route('/api/bookings/<booking_id>/cancel', methods=['PUT'])
@token_required
# Cancel own booking
def cancel_booking(current_user, booking_id):
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    if not is_booking_owner(current_user, booking):
        return jsonify({'message': 'Không có quyền hủy booking này!'}), 403
    
    if not can_cancel_booking(booking):
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

@app.route('/api/bookings/<booking_id>/check-in', methods=['POST'])
@token_required
# User confirms check-in, system auto-creates contract
def check_in_booking(current_user, booking_id):
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    if not is_booking_owner(current_user, booking):
        return jsonify({'message': 'Không có quyền check-in booking này!'}), 403
    
    if not is_deposit_paid(booking):
        return jsonify({'message': 'Bạn chưa thanh toán cọc!'}), 400
    
    if is_checked_in(booking):
        return jsonify({'message': 'Bạn đã check-in rồi!'}), 400
    
    # Call contract-service to auto-create contract
    contract_service_url = get_service_url('contract-service')
    if not contract_service_url:
        return jsonify({'message': 'Không thể kết nối contract-service!'}), 503
    
    user_id = get_user_id(current_user)
    
    try:
        resp = requests.post(
            f"{contract_service_url}/internal/contracts/auto-create",
            json={
                'room_id': booking['room_id'],
                'user_id': str(user_id),
                'payment_id': booking.get('deposit_payment_id'),
                'check_in_date': booking.get('check_in_date')
            },
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=10,
        )
        
        if not resp.ok:
            try:
                error_msg = resp.json().get('message', 'Lỗi tạo hợp đồng')
            except:
                error_msg = resp.text or 'Lỗi tạo hợp đồng'
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


@app.route('/api/bookings/checkin-payment', methods=['POST'])
@token_required
# Check-in directly from payment when no booking record exists
def check_in_from_payment(current_user):
    data = request.get_json() or {}
    payment_id = data.get('payment_id')
    room_id = data.get('room_id')
    check_in_date = data.get('check_in_date')
    
    if not payment_id or not room_id:
        return jsonify({'message': 'Thiếu payment_id hoặc room_id!'}), 400
    
    user_id = get_user_id(current_user)
    
    # Call contract-service to auto-create contract
    contract_service_url = get_service_url('contract-service')
    if not contract_service_url:
        return jsonify({'message': 'Không thể kết nối contract-service!'}), 503
    
    try:
        resp = requests.post(
            f"{contract_service_url}/internal/contracts/auto-create",
            json={
                'room_id': room_id,
                'user_id': str(user_id),
                'payment_id': payment_id,
                'check_in_date': check_in_date
            },
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=10,
        )
        
        if not resp.ok:
            try:
                error_msg = resp.json().get('message', 'Lỗi tạo hợp đồng')
            except:
                error_msg = resp.text or 'Lỗi tạo hợp đồng'
            return jsonify({'message': error_msg}), resp.status_code
        
    except Exception as e:
        return jsonify({'message': f'Lỗi kết nối: {str(e)}'}), 503
    
    # Create a booking record for history
    new_booking = create_checkin_booking_document(room_id, user_id, payment_id, check_in_date)
    
    try:
        bookings_collection.insert_one(new_booking)
    except Exception as e:
        print(f"Warning: Could not create booking record: {e}")
    
    return jsonify({
        'message': 'Check-in thành công! Hợp đồng đã được tạo tự động.',
        'booking_id': new_booking['_id']
    }), 200


# ============== Internal APIs ==============

@app.route('/internal/bookings/create-from-payment', methods=['POST'])
@internal_api_required
# Create booking record when room deposit payment is successful
def create_booking_from_payment():
    data = request.get_json() or {}
    
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    
    if not room_id or not user_id:
        return jsonify({'message': 'Missing room_id or user_id'}), 400
    
    # Check if booking already exists for this room and user
    existing = find_pending_booking(room_id, user_id)
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
    new_booking = create_booking_from_payment_data(data)
    
    try:
        bookings_collection.insert_one(new_booking)
        return jsonify({'message': 'Booking created', 'booking_id': new_booking['_id']}), 201
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
