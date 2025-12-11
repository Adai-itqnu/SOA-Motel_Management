from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import uuid
import jwt
from functools import wraps
import requests
import hashlib
import urllib.parse
from config import JWT_SECRET, SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT, VNPAY_TMN_CODE, VNPAY_HASH_SECRET, VNPAY_URL, VNPAY_RETURN_URL, INTERNAL_API_KEY
from model import payments_collection
from service_registry import register_service

app = Flask(__name__)
CORS(app)

from routes import payment_bp
app.register_blueprint(payment_bp, url_prefix='/api/payments')

# Load configuration
app.config['SECRET_KEY'] = JWT_SECRET
app.config['SERVICE_NAME'] = SERVICE_NAME
app.config['SERVICE_PORT'] = SERVICE_PORT

# Decorator xác thực token
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Try both 'Authorization' and 'authorization' (nginx may lowercase headers)
        token = request.headers.get('Authorization') or request.headers.get('authorization')
        
        if not token:
            return jsonify({'message': 'Token không tồn tại!'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            elif token.startswith('bearer '):
                token = token[7:]
            
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data
            
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token đã hết hạn!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token không hợp lệ!'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

# Decorator kiểm tra quyền admin
def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.get('role') != 'admin':
            return jsonify({'message': 'Yêu cầu quyền admin!'}), 403
        return f(current_user, *args, **kwargs)
    return decorated

from utils import (
    get_service_url, fetch_service_data, call_service_api,
    update_booking_deposit_status, send_notification,
    calculate_total_paid, update_bill_status_if_paid
)



# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': app.config['SERVICE_NAME']}), 200

# API Tạo thanh toán mới
@app.route('/api/payments', methods=['POST'])
@token_required
def create_payment(current_user):
    data = request.get_json()
    
    # Validation
    required_fields = ['bill_id', 'tenant_id', 'amount', 'method', 'payment_date']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Validate method
    valid_methods = ['cash', 'bank_transfer', 'momo', 'vnpay']
    if data['method'] not in valid_methods:
        return jsonify({'message': f'Phương thức thanh toán không hợp lệ! Chỉ chấp nhận: {", ".join(valid_methods)}'}), 400
    
    # Validate amount
    amount = float(data['amount'])
    if amount <= 0:
        return jsonify({'message': 'Số tiền phải lớn hơn 0!'}), 400
    
    # Validate status (nếu có)
    if 'status' in data:
        valid_statuses = ['pending', 'completed', 'failed']
        if data['status'] not in valid_statuses:
            return jsonify({'message': f'Status không hợp lệ! Chỉ chấp nhận: {", ".join(valid_statuses)}'}), 400
    else:
        data['status'] = 'pending'
    
    # Lấy thông tin hóa đơn từ bill-service
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    bill_data = fetch_service_data('bill-service', f"/api/bills/{data['bill_id']}", token)
    
    if not bill_data:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    bill = bill_data if isinstance(bill_data, dict) else bill_data.get('bill', bill_data)
    
    # Kiểm tra bill status
    if bill.get('status') == 'paid':
        return jsonify({'message': 'Hóa đơn đã được thanh toán đầy đủ!'}), 400
    
    # Kiểm tra số tiền thanh toán không vượt quá số tiền còn lại
    total_paid = calculate_total_paid(data['bill_id'])
    remaining_amount = bill['total_amount'] - total_paid
    
    if amount > remaining_amount:
        return jsonify({
            'message': f'Số tiền thanh toán ({amount:,.0f}) vượt quá số tiền còn lại ({remaining_amount:,.0f})!'
        }), 400
    
    # Tạo payment_id sử dụng UUID (thread-safe)
    payment_id = f"P{uuid.uuid4().hex[:8].upper()}"
    
    # Đảm bảo không trùng (retry nếu cần)
    while payments_collection.find_one({'_id': payment_id}):
        payment_id = f"P{uuid.uuid4().hex[:8].upper()}"
    
    new_payment = {
        '_id': payment_id,
        'bill_id': data['bill_id'],
        'tenant_id': data['tenant_id'],
        'amount': amount,
        'method': data['method'],
        'payment_date': data['payment_date'],
        'status': data['status']
    }
    
    try:
        payments_collection.insert_one(new_payment)
        new_payment['id'] = new_payment['_id']
        
        # Nếu status là completed, kiểm tra và cập nhật bill status
        if data['status'] == 'completed':
            update_bill_status_if_paid(data['bill_id'], bill['total_amount'])
        
        return jsonify({
            'message': 'Tạo thanh toán thành công!',
            'payment': new_payment
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo thanh toán: {str(e)}'}), 500

# API Lấy danh sách thanh toán
@app.route('/api/payments', methods=['GET'])
@token_required
def get_payments(current_user):
    bill_id = request.args.get('bill_id')
    tenant_id = request.args.get('tenant_id')
    payment_date = request.args.get('payment_date')
    status = request.args.get('status')
    
    query = {}
    
    # Filter theo bill_id
    if bill_id:
        query['bill_id'] = bill_id
    
    # Filter theo tenant_id
    if tenant_id:
        query['tenant_id'] = tenant_id
    
    # Filter theo payment_date
    if payment_date:
        query['payment_date'] = payment_date
    
    # Filter theo status
    if status:
        query['status'] = status
    
    # Nếu là user thường, chỉ cho xem thanh toán của mình
    if current_user.get('role') != 'admin':
        query['tenant_id'] = current_user.get('user_id') or current_user.get('id')
    
    payments = list(payments_collection.find(query).sort('payment_date', -1))
    
    # Convert ObjectId
    for payment in payments:
        payment['id'] = payment['_id']
    
    return jsonify({'payments': payments, 'total': len(payments)}), 200

# API Lấy chi tiết thanh toán
@app.route('/api/payments/<payment_id>', methods=['GET'])
@token_required
def get_payment(current_user, payment_id):
    payment = payments_collection.find_one({'_id': payment_id})
    
    if not payment:
        return jsonify({'message': 'Thanh toán không tồn tại!'}), 404
    
    # Nếu là user thường, chỉ cho xem thanh toán của mình
    if current_user.get('role') != 'admin':
        if payment['tenant_id'] != (current_user.get('user_id') or current_user.get('id')):
            return jsonify({'message': 'Không có quyền xem thanh toán này!'}), 403
    
    payment['id'] = payment['_id']
    return jsonify(payment), 200

# API Lấy tất cả thanh toán của một hóa đơn
@app.route('/api/payments/bill/<bill_id>', methods=['GET'])
@token_required
def get_payments_by_bill(current_user, bill_id):
    payments = list(payments_collection.find({'bill_id': bill_id}).sort('payment_date', -1))
    
    # Tính tổng thanh toán
    total_paid = calculate_total_paid(bill_id)
    
    # Lấy thông tin hóa đơn
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    bill_data = fetch_service_data('bill-service', f"/api/bills/{bill_id}", token)
    
    bill = bill_data if isinstance(bill_data, dict) else bill_data.get('bill', bill_data) if bill_data else {}
    total_amount = bill.get('total_amount', 0)
    remaining_amount = total_amount - total_paid
    
    # Convert ObjectId
    for payment in payments:
        payment['id'] = payment['_id']
    
    return jsonify({
        'payments': payments,
        'total': len(payments),
        'total_paid': total_paid,
        'total_amount': total_amount,
        'remaining_amount': remaining_amount
    }), 200

# API Cập nhật thanh toán
@app.route('/api/payments/<payment_id>', methods=['PUT'])
@token_required
@admin_required
def update_payment(current_user, payment_id):
    payment = payments_collection.find_one({'_id': payment_id})
    
    if not payment:
        return jsonify({'message': 'Thanh toán không tồn tại!'}), 404
    
    data = request.get_json()
    
    # Cập nhật các trường có thể thay đổi
    update_fields = {}
    
    if 'amount' in data:
        amount = float(data['amount'])
        if amount <= 0:
            return jsonify({'message': 'Số tiền phải lớn hơn 0!'}), 400
        update_fields['amount'] = amount
    
    if 'status' in data:
        valid_statuses = ['pending', 'completed', 'failed']
        if data['status'] not in valid_statuses:
            return jsonify({'message': f'Status không hợp lệ! Chỉ chấp nhận: {", ".join(valid_statuses)}'}), 400
        update_fields['status'] = data['status']
    
    if 'method' in data:
        valid_methods = ['cash', 'bank_transfer', 'momo', 'vnpay']
        if data['method'] not in valid_methods:
            return jsonify({'message': f'Phương thức thanh toán không hợp lệ! Chỉ chấp nhận: {", ".join(valid_methods)}'}), 400
        update_fields['method'] = data['method']
    
    if 'payment_date' in data:
        update_fields['payment_date'] = data['payment_date']
    
    if not update_fields:
        return jsonify({'message': 'Không có trường nào để cập nhật!'}), 400
    
    try:
        payments_collection.update_one(
            {'_id': payment_id},
            {'$set': update_fields}
        )
        
        updated_payment = payments_collection.find_one({'_id': payment_id})
        updated_payment['id'] = updated_payment['_id']
        
        # Nếu status chuyển thành completed, kiểm tra và cập nhật bill status
        if 'status' in update_fields and update_fields['status'] == 'completed':
            # Lấy thông tin hóa đơn
            token = request.headers.get('Authorization') or request.headers.get('authorization')
            bill_data = fetch_service_data('bill-service', f"/api/bills/{payment['bill_id']}", token)
            if bill_data:
                bill = bill_data if isinstance(bill_data, dict) else bill_data.get('bill', bill_data)
                update_bill_status_if_paid(payment['bill_id'], bill.get('total_amount', 0))
        
        return jsonify({
            'message': 'Cập nhật thanh toán thành công!',
            'payment': updated_payment
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi cập nhật thanh toán: {str(e)}'}), 500

# API Thống kê thanh toán
@app.route('/api/payments/statistics', methods=['GET'])
@token_required
@admin_required
def get_payment_statistics(current_user):
    # Tổng số thanh toán
    total_payments = payments_collection.count_documents({})
    
    # Tổng số tiền đã thanh toán (completed)
    pipeline_total = [
        {'$match': {'status': 'completed'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ]
    result_total = list(payments_collection.aggregate(pipeline_total))
    total_amount = result_total[0]['total'] if result_total else 0
    
    # Thống kê theo status
    pipeline_status = [
        {'$group': {
            '_id': '$status',
            'count': {'$sum': 1},
            'total_amount': {'$sum': '$amount'}
        }}
    ]
    status_stats = list(payments_collection.aggregate(pipeline_status))
    
    # Thống kê theo phương thức thanh toán
    pipeline_method = [
        {'$group': {
            '_id': '$method',
            'count': {'$sum': 1},
            'total_amount': {'$sum': '$amount'}
        }}
    ]
    method_stats = list(payments_collection.aggregate(pipeline_method))
    
    # Thống kê theo ngày (30 ngày gần nhất)
    from datetime import datetime, timedelta
    thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    recent_payments = payments_collection.count_documents({
        'payment_date': {'$gte': thirty_days_ago},
        'status': 'completed'
    })
    
    pipeline_recent = [
        {'$match': {'payment_date': {'$gte': thirty_days_ago}, 'status': 'completed'}},
        {'$group': {'_id': None, 'total': {'$sum': '$amount'}}}
    ]
    result_recent = list(payments_collection.aggregate(pipeline_recent))
    recent_amount = result_recent[0]['total'] if result_recent else 0
    
    return jsonify({
        'total_payments': total_payments,
        'total_amount': total_amount,
        'recent_payments_30days': recent_payments,
        'recent_amount_30days': recent_amount,
        'by_status': {stat['_id']: {'count': stat['count'], 'total_amount': stat['total_amount']} for stat in status_stats},
        'by_method': {stat['_id']: {'count': stat['count'], 'total_amount': stat['total_amount']} for stat in method_stats}
    }), 200

# API Tạo payment cho tiền cọc (booking/contract)
@app.route('/api/payments/deposit', methods=['POST'])
@token_required
def create_deposit_payment(current_user):
    data = request.get_json()
    
    # Validation
    required_fields = ['amount', 'payment_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Validate payment_type
    if data['payment_type'] not in ['booking', 'contract']:
        return jsonify({'message': 'payment_type phải là "booking" hoặc "contract"!'}), 400
    
    # Validate booking_id hoặc contract_id
    if data['payment_type'] == 'booking':
        if 'booking_id' not in data:
            return jsonify({'message': 'Thiếu trường booking_id!'}), 400
    else:
        if 'contract_id' not in data:
            return jsonify({'message': 'Thiếu trường contract_id!'}), 400
    
    # Validate amount
    amount = float(data['amount'])
    if amount <= 0:
        return jsonify({'message': 'Số tiền phải lớn hơn 0!'}), 400
    
    # Lấy tenant_id từ current_user
    tenant_id = current_user.get('user_id') or current_user.get('id')
    if not tenant_id:
        return jsonify({'message': 'Không tìm thấy tenant_id!'}), 400
    
    # Tạo payment_id sử dụng UUID (thread-safe)
    payment_id = f"P{uuid.uuid4().hex[:8].upper()}"
    
    # Đảm bảo không trùng (retry nếu cần)
    while payments_collection.find_one({'_id': payment_id}):
        payment_id = f"P{uuid.uuid4().hex[:8].upper()}"
    
    # Tạo payment record
    new_payment = {
        '_id': payment_id,
        'tenant_id': tenant_id,
        'amount': amount,
        'method': 'vnpay',  # Mặc định dùng VNpay cho deposit
        'payment_date': datetime.datetime.now().strftime('%Y-%m-%d'),
        'status': 'pending',
        'payment_type': data['payment_type'],
        'booking_id': data.get('booking_id'),
        'contract_id': data.get('contract_id'),
        'bill_id': None  # Deposit không liên kết với bill
    }
    
    try:
        payments_collection.insert_one(new_payment)
        new_payment['id'] = new_payment['_id']
        
        return jsonify({
            'message': 'Tạo payment tiền cọc thành công!',
            'payment': new_payment
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo payment: {str(e)}'}), 500



if __name__ == '__main__':
    import os
    register_service()
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=debug_mode)

