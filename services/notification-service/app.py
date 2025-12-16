"""Notification Service - Main Application"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import atexit

from config import Config
from model import notifications_collection
from decorators import token_required, admin_required, internal_api_required
from services import fetch_unpaid_bills
from utils import (
    get_timestamp, create_notification_document,
    format_notification, get_user_id, check_duplicate_notification
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


# ============== Admin API: Send Notification ==============

@app.route('/api/notifications/send', methods=['POST'])
@token_required
@admin_required
def send_notification(current_user):
    """Send notification to user(s) - Admin only"""
    data = request.get_json() or {}
    
    # Validate required fields
    if not data.get('title') or not data.get('message'):
        return jsonify({'message': 'Thiếu tiêu đề hoặc nội dung!'}), 400
    
    broadcast = data.get('broadcast', False)
    user_id = data.get('user_id')
    
    if not broadcast and not user_id:
        return jsonify({'message': 'Thiếu user_id!'}), 400
    
    created = []
    
    if broadcast:
        # Get all users from user-service (internal call)
        import requests
        try:
            headers = {'X-Internal-Key': Config.INTERNAL_API_KEY}
            resp = requests.get(f"{Config.USER_SERVICE_URL}/internal/users", headers=headers, timeout=5)
            if resp.status_code == 200:
                users = resp.json().get('users', [])
                for user in users:
                    notification = create_notification_document({
                        'user_id': user.get('_id') or user.get('id'),
                        'title': data['title'],
                        'message': data['message'],
                        'type': data.get('type', 'info'),
                        'metadata': {'persistent': True, 'broadcast': True}
                    })
                    created.append(notification['_id'])
            else:
                return jsonify({'message': 'Không thể lấy danh sách người dùng!'}), 500
        except Exception as e:
            return jsonify({'message': f'Lỗi gửi thông báo: {str(e)}'}), 500
    else:
        notification = create_notification_document({
            'user_id': user_id,
            'title': data['title'],
            'message': data['message'],
            'type': data.get('type', 'info'),
            'metadata': {'persistent': True, 'broadcast': False}
        })
        created.append(notification['_id'])
    
    return jsonify({
        'message': f'Đã gửi {len(created)} thông báo!',
        'created': created
    }), 201


# ============== Admin API: List All Notifications ==============

@app.route('/api/notifications/admin', methods=['GET'])
@token_required
@admin_required
def get_all_notifications(current_user):
    """Get all notifications - Admin only"""
    query = {}
    
    user_id = request.args.get('user_id')
    if user_id:
        query['user_id'] = user_id
    
    notif_type = request.args.get('type')
    if notif_type:
        query['type'] = notif_type
    
    limit = int(request.args.get('limit', 100))
    
    notifications = list(notifications_collection.find(query).sort('created_at', -1).limit(limit))
    for n in notifications:
        format_notification(n)
    
    return jsonify({
        'notifications': notifications,
        'total': len(notifications)
    }), 200


# ============== Internal API: Create Notification ==============

@app.route('/api/notifications', methods=['POST'])
@internal_api_required
def create_notification():
    """Create notification (internal API)"""
    data = request.get_json() or {}
    
    required = ['user_id', 'title', 'message', 'type']
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400
    
    notification = create_notification_document(data)
    return jsonify({
        'message': 'Tạo thông báo thành công!',
        'notification': notification
    }), 201


# ============== Internal API: Welcome Notification ==============

@app.route('/api/notifications/welcome', methods=['POST'])
@internal_api_required
def create_welcome_notification():
    """Create welcome notification for new user"""
    data = request.get_json() or {}
    
    user_id = data.get('user_id')
    user_name = data.get('fullname') or data.get('user_name', 'bạn')
    
    if not user_id:
        return jsonify({'message': 'Thiếu user_id!'}), 400
    
    notification = create_notification_document({
        'user_id': user_id,
        'title': 'Chào mừng đến với MotelHDK! 🎉',
        'message': f'Xin chào {user_name}! Cảm ơn bạn đã đăng ký tài khoản. Hãy khám phá các phòng trọ phù hợp với nhu cầu của bạn.',
        'type': 'welcome',
        'metadata': {'persistent': True}
    })
    
    return jsonify({
        'message': 'Đã tạo thông báo chào mừng!',
        'notification': notification
    }), 201


# ============== User APIs ==============

@app.route('/api/notifications', methods=['GET'])
@token_required
def get_notifications(current_user):
    """Get user's notifications"""
    user_id = get_user_id(current_user)
    status_filter = request.args.get('status')
    
    query = {'user_id': user_id}
    if status_filter:
        query['status'] = status_filter
    
    notifications = list(notifications_collection.find(query).sort('created_at', -1))
    for n in notifications:
        format_notification(n)
    
    return jsonify({
        'notifications': notifications,
        'total': len(notifications)
    }), 200


@app.route('/api/notifications/<notification_id>/read', methods=['PUT'])
@token_required
def mark_as_read(current_user, notification_id):
    """Mark notification as read"""
    user_id = get_user_id(current_user)
    
    notification = notifications_collection.find_one({'_id': notification_id})
    if not notification or notification.get('user_id') != user_id:
        return jsonify({'message': 'Thông báo không tồn tại!'}), 404
    
    notifications_collection.update_one(
        {'_id': notification_id},
        {'$set': {'status': 'read', 'read_at': get_timestamp()}}
    )
    return jsonify({'message': 'Đã đánh dấu đọc thông báo.'}), 200


@app.route('/api/notifications/read', methods=['PUT'])
@token_required
def mark_all_as_read(current_user):
    """Mark all notifications as read"""
    user_id = get_user_id(current_user)
    
    result = notifications_collection.update_many(
        {'user_id': user_id, 'status': 'unread'},
        {'$set': {'status': 'read', 'read_at': get_timestamp(), 'metadata.read': True}}
    )
    
    return jsonify({
        'message': f'Đã đánh dấu {result.modified_count} thông báo là đã đọc.'
    }), 200


# ============== Internal Task: Rent Reminders ==============

@app.route('/api/notifications/tasks/rent-reminders', methods=['POST'])
@internal_api_required
def run_rent_reminders():
    """Generate rent reminder notifications"""
    bills = fetch_unpaid_bills()
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
        
        # Determine notification type
        if days_diff == 0:
            notif_type = 'rent_due_today'
            message = f"Hôm nay là hạn thanh toán hóa đơn {bill.get('_id')} ({bill.get('total_amount', 0):,.0f} VND)."
        elif 1 <= days_diff <= 3:
            notif_type = 'rent_due_soon'
            message = f"Hóa đơn {bill.get('_id')} sẽ đến hạn vào {due_date_str}."
        elif days_diff < 0:
            notif_type = 'rent_overdue'
            message = f"Hóa đơn {bill.get('_id')} đã quá hạn {abs(days_diff)} ngày."
        else:
            continue
        
        # Check duplicate
        if check_duplicate_notification(notif_type, bill.get('_id')):
            continue
        
        # Create notification
        notification = create_notification_document({
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
    
    return jsonify({
        'message': 'Đã chạy nhắc nhở tiền nhà',
        'created': created
    }), 200


# ============== Entry Point ==============

if __name__ == '__main__':
    print(f"\n{'='*50}\n  {Config.SERVICE_NAME.upper()}\n  Port: {Config.SERVICE_PORT}\n{'='*50}\n")
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)
