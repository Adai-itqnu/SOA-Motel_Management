from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import datetime
import uuid
import requests
import jwt

from config import (
    JWT_SECRET,
    SERVICE_NAME,
    SERVICE_PORT,
    CONSUL_HOST,
    CONSUL_PORT,
    INTERNAL_API_KEY,
)
from model import notifications_collection
from service_registry import register_service

app = Flask(__name__)
CORS(app)

# Authentication helpers
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

def internal_api_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Internal-Api-Key')
        if not token or token != INTERNAL_API_KEY:
            return jsonify({'message': 'Unauthorized internal request'}), 403
        return f(*args, **kwargs)
    return decorated

# Consul helper
def get_service_url(service_name):
    try:
        consul_url = f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(consul_url, timeout=5)
        if response.ok and response.json():
            service = response.json()[0]
            return f"http://{service['ServiceAddress']}:{service['ServicePort']}"
        service_ports = {
            'bill-service': 5007,
            'booking-service': 5005,
            'notification-service': SERVICE_PORT
        }
        port = service_ports.get(service_name, 5000)
        return f"http://{service_name}:{port}"
    except Exception as exc:
        print(f"Error resolving service URL for {service_name}: {exc}")
        service_ports = {
            'bill-service': 5007,
            'booking-service': 5005,
            'notification-service': SERVICE_PORT
        }
        port = service_ports.get(service_name, 5000)
        return f"http://{service_name}:{port}"

def create_notification_record(data):
    notification = {
        '_id': data.get('_id') or f"N{uuid.uuid4().hex[:10]}",
        'user_id': str(data['user_id']),
        'title': data['title'],
        'message': data['message'],
        'type': data.get('type', 'general'),
        'status': 'unread',
        'metadata': data.get('metadata', {}),
        'created_at': datetime.datetime.utcnow().isoformat(),
        'read_at': None
    }
    notifications_collection.insert_one(notification)
    notification['id'] = notification['_id']
    return notification

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': SERVICE_NAME}), 200

# Internal endpoint: create notification
@app.route('/api/notifications', methods=['POST'])
@internal_api_required
def create_notification_internal():
    data = request.get_json() or {}
    required_fields = ['user_id', 'title', 'message', 'type']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    notification = create_notification_record(data)
    return jsonify({'message': 'Tạo thông báo thành công!', 'notification': notification}), 201

# User endpoint: list notifications
@app.route('/api/notifications', methods=['GET'])
@token_required
def get_notifications(current_user):
    user_id = current_user.get('user_id') or current_user.get('id')
    status_filter = request.args.get('status')
    query = {'user_id': str(user_id)}
    if status_filter:
        query['status'] = status_filter
    notifications = list(notifications_collection.find(query).sort('created_at', -1))
    for noti in notifications:
        noti['id'] = noti['_id']
    return jsonify({'notifications': notifications, 'total': len(notifications)}), 200

# User endpoint: mark as read
@app.route('/api/notifications/<notification_id>/read', methods=['PUT'])
@token_required
def mark_notification_read(current_user, notification_id):
    user_id = current_user.get('user_id') or current_user.get('id')
    notification = notifications_collection.find_one({'_id': notification_id})
    if not notification or notification.get('user_id') != str(user_id):
        return jsonify({'message': 'Thông báo không tồn tại!'}), 404
    notifications_collection.update_one(
        {'_id': notification_id},
        {'$set': {'status': 'read', 'read_at': datetime.datetime.utcnow().isoformat()}}
    )
    return jsonify({'message': 'Đã đánh dấu đọc thông báo.'}), 200

# Internal task: rent reminders
@app.route('/api/notifications/tasks/rent-reminders', methods=['POST'])
@internal_api_required
def run_rent_reminders():
    bill_service_url = get_service_url('bill-service')
    try:
        response = requests.get(
            f"{bill_service_url}/internal/bills/unpaid",
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY},
            timeout=10
        )
        if not response.ok:
            return jsonify({'message': 'Không thể lấy danh sách hóa đơn!'}), 500
        data = response.json()
    except Exception as exc:
        return jsonify({'message': f'Lỗi kết nối bill-service: {exc}'}), 500
    
    bills = data.get('bills', [])
    today = datetime.date.today()
    created = []
    for bill in bills:
        due_date_str = bill.get('due_date')
        if not due_date_str:
            continue
        try:
            due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        days_diff = (due_date - today).days
        notif_type = None
        message = ""
        if days_diff == 0:
            notif_type = 'rent_due_today'
            message = f"Hôm nay là hạn thanh toán hóa đơn {bill.get('_id')} với số tiền {bill.get('total_amount', 0):,.0f} VND."
        elif 1 <= days_diff <= 3:
            notif_type = 'rent_due_soon'
            message = f"Hóa đơn {bill.get('_id')} sẽ đến hạn vào {due_date_str}. Vui lòng thanh toán sớm để tránh trễ hạn."
        elif days_diff < 0:
            notif_type = 'rent_overdue'
            message = f"Hóa đơn {bill.get('_id')} đã quá hạn {abs(days_diff)} ngày. Vui lòng thanh toán ngay."
        else:
            continue
        
        # Avoid duplicate notifications for the same bill & type
        existing = notifications_collection.find_one({
            'type': notif_type,
            'metadata.bill_id': bill.get('_id')
        })
        if existing:
            continue
        
        notification = create_notification_record({
            'user_id': bill.get('tenant_id'),
            'title': 'Nhắc nhở thanh toán tiền nhà',
            'message': message,
            'type': notif_type,
            'metadata': {
                'bill_id': bill.get('_id'),
                'due_date': due_date_str,
                'days_diff': days_diff
            }
        })
        created.append(notification['_id'])
    
    return jsonify({'message': 'Đã chạy nhắc nhở tiền nhà', 'created': created}), 200

if __name__ == '__main__':
    import os
    register_service()
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=debug_mode)

