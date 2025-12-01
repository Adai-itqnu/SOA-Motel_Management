from flask import Blueprint, request, jsonify, redirect
import hashlib
import urllib.parse
import datetime
from config import (
    VNPAY_TMN_CODE, VNPAY_HASH_SECRET, VNPAY_URL, VNPAY_RETURN_URL,
    INTERNAL_API_KEY, JWT_SECRET
)
from model import payments_collection
from utils import update_booking_deposit_status, send_notification, update_bill_status_if_paid, fetch_service_data
import jwt
from functools import wraps

# Token authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization') or request.headers.get('authorization')
        
        if not token:
            return jsonify({'message': 'Token không tồn tại!'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            elif token.startswith('bearer '):
                token = token[7:]
            
            data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            current_user = data
            
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token đã hết hạn!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token không hợp lệ!'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

payment_bp = Blueprint('payment', __name__)

# --- Helper Functions ---

def vnpay_generate_url(order_id, amount, order_info, return_url=None):
    if not VNPAY_TMN_CODE or not VNPAY_HASH_SECRET:
        return None
    
    if return_url is None:
        return_url = VNPAY_RETURN_URL
    
    vnp_params = {
        'vnp_Version': '2.1.0',
        'vnp_Command': 'pay',
        'vnp_TmnCode': VNPAY_TMN_CODE,
        'vnp_Amount': int(amount) * 100,
        'vnp_CurrCode': 'VND',
        'vnp_TxnRef': order_id,
        'vnp_OrderInfo': order_info,
        'vnp_OrderType': 'other',
        'vnp_Locale': 'vn',
        'vnp_ReturnUrl': return_url,
        'vnp_IpAddr': request.remote_addr or '127.0.0.1',
        'vnp_CreateDate': datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    }
    
    sorted_params = sorted(vnp_params.items())
    query_string = urllib.parse.urlencode(sorted_params)
    
    sign_data = query_string
    if VNPAY_HASH_SECRET:
        sign_data += '&' + VNPAY_HASH_SECRET
    secure_hash = hashlib.sha512(sign_data.encode('utf-8')).hexdigest()
    
    return VNPAY_URL + '?' + query_string + '&vnp_SecureHash=' + secure_hash

def vnpay_validate_signature(vnp_params):
    if not VNPAY_HASH_SECRET:
        return False
    
    params_copy = dict(vnp_params)
    vnp_secure_hash = params_copy.pop('vnp_SecureHash', '')
    
    sorted_params = sorted(params_copy.items())
    query_string = urllib.parse.urlencode(sorted_params)
    
    sign_data = query_string
    if VNPAY_HASH_SECRET:
        sign_data += '&' + VNPAY_HASH_SECRET
    secure_hash = hashlib.sha512(sign_data.encode('utf-8')).hexdigest()
    
    return secure_hash == vnp_secure_hash


# --- VNPAY Routes ---

@payment_bp.route('/vnpay/create', methods=['POST'])
@token_required
def vnpay_create(current_user):
    data = request.get_json()
    payment_id = data.get('payment_id')
    amount = data.get('amount')
    order_info = data.get('order_info')
    return_url = data.get('return_url')

    if not all([payment_id, amount, order_info]):
        return jsonify({'message': 'Missing required fields'}), 400

    payment_url = vnpay_generate_url(payment_id, amount, order_info, return_url)
    if not payment_url:
        return jsonify({'message': 'Failed to generate VNPAY URL'}), 500

    # Update payment method
    payments_collection.update_one(
        {'_id': payment_id},
        {'$set': {'method': 'vnpay', 'status': 'pending'}}
    )

    return jsonify({'payment_url': payment_url, 'payment_id': payment_id})

@payment_bp.route('/vnpay/ipn', methods=['GET'])
def vnpay_ipn():
    vnp_params = request.args.to_dict()
    
    if not vnpay_validate_signature(vnp_params):
        return jsonify({'RspCode': '97', 'Message': 'Invalid Signature'})

    payment_id = vnp_params.get('vnp_TxnRef')
    response_code = vnp_params.get('vnp_ResponseCode')
    transaction_id = vnp_params.get('vnp_TransactionNo')
    amount = int(vnp_params.get('vnp_Amount', 0)) / 100

    payment = payments_collection.find_one({'_id': payment_id})
    if not payment:
        return jsonify({'RspCode': '01', 'Message': 'Order not found'})
    
    if payment['status'] == 'completed':
        return jsonify({'RspCode': '02', 'Message': 'Order already confirmed'})

    if response_code == '00':
        # Success
        payments_collection.update_one(
            {'_id': payment_id},
            {'$set': {'status': 'completed', 'transaction_id': transaction_id, 'vnpay_response': vnp_params}}
        )
        
        # Logic xử lý sau khi thanh toán thành công
        payment_type = payment.get('payment_type')
        
        # Handle bill payment
        if payment.get('bill_id'):
            token = None # Internal call
            bill_data = fetch_service_data('bill-service', f"/api/bills/{payment['bill_id']}", token)
            if bill_data:
                bill = bill_data if isinstance(bill_data, dict) else bill_data.get('bill', bill_data)
                update_bill_status_if_paid(payment['bill_id'], bill.get('total_amount', 0))

        # Handle deposit payment (booking)
        if payment_type == 'booking' and payment.get('booking_id'):
            update_booking_deposit_status(payment['booking_id'], 'paid', transaction_id)
            send_notification(
                payment.get('tenant_id'),
                "Thanh toán cọc thành công",
                f"Bạn đã giữ phòng thành công cho booking {payment['booking_id']}. Đơn đặt phòng của bạn đang chờ admin duyệt.",
                "deposit_paid",
                {'booking_id': payment['booking_id'], 'payment_id': payment_id}
            )
        
        # NEW: Handle first month rent payment
        if payment_type == 'first_month_rent' and payment.get('booking_id'):
            # Call booking service to finalize booking
            from utils import call_service_api
            result = call_service_api(
                'booking-service',
                'PUT',
                f"/api/bookings/{payment['booking_id']}/finalize",
                {
                    'payment_id': payment_id,
                    'transaction_id': transaction_id
                }
            )
            if not result:
                print(f"Failed to finalize booking {payment['booking_id']}")

        return jsonify({'RspCode': '00', 'Message': 'Confirm Success'})
    else:
        # Failed
        payments_collection.update_one(
            {'_id': payment_id},
            {'$set': {'status': 'failed', 'transaction_id': transaction_id, 'vnpay_response': vnp_params}}
        )
        return jsonify({'RspCode': '00', 'Message': 'Confirm Success'}) # IPN vẫn trả về success để vnpay không gọi lại

@payment_bp.route('/vnpay/return', methods=['GET'])
def vnpay_return():
    # Endpoint này thường redirect về frontend
    vnp_params = request.args.to_dict()
    if vnpay_validate_signature(vnp_params):
        if vnp_params.get('vnp_ResponseCode') == '00':
            return jsonify({'message': 'Payment successful', 'data': vnp_params})
        else:
            return jsonify({'message': 'Payment failed', 'data': vnp_params})
    else:
        return jsonify({'message': 'Invalid signature'})
