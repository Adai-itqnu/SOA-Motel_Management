"""
Auth Service - Main Application
Handles authentication: login, register, JWT, password hashing
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
import uuid
import re
import atexit
import requests

from config import Config
from model import users_collection
from service_registry import register_service, deregister_service


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
atexit.register(deregister_service)


# ============== Utility Functions ==============

def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


def generate_user_id():
    return f"USR{uuid.uuid4().hex[:8].upper()}"


def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone):
    if not phone:
        return True
    pattern = r'^(0|\+84)[0-9]{9,10}$'
    return bool(re.match(pattern, phone))


def send_welcome_notification(user_id, fullname):
    """Send welcome notification to new user via notification-service"""
    try:
        response = requests.post(
            f"{Config.NOTIFICATION_SERVICE_URL}/api/notifications/welcome",
            json={
                'user_id': user_id,
                'fullname': fullname
            },
            headers={
                'X-Internal-Key': Config.INTERNAL_API_KEY
            },
            timeout=5
        )
        return response.status_code == 201
    except Exception as e:
        print(f"Failed to send welcome notification: {e}")
        return False


def format_user_response(user):
    return {
        'id': user['_id'],
        'username': user.get('username', ''),
        'email': user.get('email', ''),
        'phone': user.get('phone', ''),
        'fullname': user.get('fullname', ''),
        'role': user.get('role', 'user'),
        'status': user.get('status', 'active')
    }


# ============== Health Check ==============

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': Config.SERVICE_NAME}), 200


# ============== Authentication APIs ==============

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user account"""
    data = request.get_json() or {}
    
    # Validate required fields
    required = ['username', 'password', 'email', 'fullname']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400
    
    # Validate email
    if not validate_email(data['email']):
        return jsonify({'message': 'Email không hợp lệ!'}), 400
    
    # Validate phone if provided
    if data.get('phone') and not validate_phone(data['phone']):
        return jsonify({'message': 'Số điện thoại không hợp lệ!'}), 400
    
    # Validate password length
    if len(data['password']) < 6:
        return jsonify({'message': 'Mật khẩu phải có ít nhất 6 ký tự!'}), 400
    
    # Check duplicates
    if users_collection.find_one({'username': data['username']}):
        return jsonify({'message': 'Tên đăng nhập đã tồn tại!'}), 400
    
    if users_collection.find_one({'email': data['email']}):
        return jsonify({'message': 'Email đã được sử dụng!'}), 400
    
    # First user becomes admin
    is_first = users_collection.count_documents({}) == 0
    role = 'admin' if is_first else 'user'
    
    # Create user
    timestamp = get_timestamp()
    new_user = {
        '_id': generate_user_id(),
        'username': data['username'],
        'email': data['email'],
        'phone': data.get('phone', ''),
        'password': generate_password_hash(data['password']),
        'role': role,
        'fullname': data['fullname'],
        'id_card': '',
        'address': '',
        'status': 'active',
        'created_at': timestamp,
        'updated_at': timestamp
    }
    
    try:
        users_collection.insert_one(new_user)
        
        # Send welcome notification
        send_welcome_notification(new_user['_id'], new_user['fullname'])
        
        return jsonify({
            'message': 'Đăng ký thành công!',
            'user_id': new_user['_id'],
            'role': role
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi đăng ký: {str(e)}'}), 500


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login with username or email"""
    data = request.get_json() or {}
    
    login_id = data.get('username') or data.get('email')
    password = data.get('password')
    
    if not login_id or not password:
        return jsonify({'message': 'Thiếu thông tin đăng nhập!'}), 400
    
    # Find user by username or email
    user = users_collection.find_one({
        '$or': [
            {'username': login_id},
            {'email': login_id}
        ]
    })
    
    if not user:
        return jsonify({'message': 'Tài khoản không tồn tại!'}), 401
    
    if not check_password_hash(user['password'], password):
        return jsonify({'message': 'Mật khẩu không đúng!'}), 401
    
    if user.get('status') == 'inactive':
        return jsonify({'message': 'Tài khoản đã bị khóa!'}), 403
    
    # Generate JWT token
    token = jwt.encode({
        'user_id': user['_id'],
        'username': user['username'],
        'role': user['role'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=Config.JWT_EXPIRY_HOURS)
    }, Config.JWT_SECRET, algorithm='HS256')
    
    return jsonify({
        'message': 'Đăng nhập thành công!',
        'token': token,
        'user': format_user_response(user)
    }), 200


@app.route('/api/auth/verify', methods=['GET'])
def verify():
    """Verify JWT token"""
    auth_header = request.headers.get('Authorization') or request.headers.get('authorization')
    
    if not auth_header:
        return jsonify({'valid': False, 'message': 'Không có token!'}), 401
    
    try:
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return jsonify({'valid': False, 'message': 'Token format sai!'}), 401
        
        token = parts[1]
        data = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
        
        user = users_collection.find_one({'_id': data.get('user_id')})
        if not user:
            return jsonify({'valid': False, 'message': 'User không tồn tại!'}), 401
        
        return jsonify({
            'valid': True,
            'user': format_user_response(user)
        }), 200
        
    except jwt.ExpiredSignatureError:
        return jsonify({'valid': False, 'message': 'Token hết hạn!'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'valid': False, 'message': 'Token không hợp lệ!'}), 401


@app.route('/api/auth/change-password', methods=['PUT'])
def change_password():
    """Change password (requires valid token)"""
    auth_header = request.headers.get('Authorization') or request.headers.get('authorization')
    
    if not auth_header:
        return jsonify({'message': 'Không có token!'}), 401
    
    try:
        parts = auth_header.split()
        token = parts[1] if len(parts) == 2 else parts[0]
        data = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
        user_id = data.get('user_id')
    except:
        return jsonify({'message': 'Token không hợp lệ!'}), 401
    
    body = request.get_json() or {}
    old_password = body.get('old_password')
    new_password = body.get('new_password')
    
    if not old_password or not new_password:
        return jsonify({'message': 'Thiếu mật khẩu cũ hoặc mới!'}), 400
    
    if len(new_password) < 6:
        return jsonify({'message': 'Mật khẩu mới phải có ít nhất 6 ký tự!'}), 400
    
    user = users_collection.find_one({'_id': user_id})
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    if not check_password_hash(user['password'], old_password):
        return jsonify({'message': 'Mật khẩu cũ không đúng!'}), 401
    
    users_collection.update_one(
        {'_id': user_id},
        {'$set': {
            'password': generate_password_hash(new_password),
            'updated_at': get_timestamp()
        }}
    )
    
    return jsonify({'message': 'Đổi mật khẩu thành công!'}), 200


# ============== Entry Point ==============

if __name__ == '__main__':
    print(f"\n{'='*50}")
    print(f"  {Config.SERVICE_NAME.upper()}")
    print(f"  Port: {Config.SERVICE_PORT}")
    print(f"{'='*50}\n")
    
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)