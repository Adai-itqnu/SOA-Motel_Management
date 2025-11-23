from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
from config import JWT_SECRET, SERVICE_NAME, SERVICE_PORT
from model import users_collection
from service_registry import register_service

app = Flask(__name__)
CORS(app)

# Load configuration
app.config['SECRET_KEY'] = JWT_SECRET
app.config['SERVICE_NAME'] = SERVICE_NAME
app.config['SERVICE_PORT'] = SERVICE_PORT

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': app.config['SERVICE_NAME']}), 200

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
            current_user = users_collection.find_one({'_id': data['user_id']})
            
            if not current_user:
                return jsonify({'message': 'Người dùng không tồn tại!'}), 401
                
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


# API Đăng ký
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    # Validation
    required_fields = ['username', 'password', 'email', 'name', 'phone']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Kiểm tra username đã tồn tại
    if users_collection.find_one({'username': data['username']}):
        return jsonify({'message': 'Tên đăng nhập đã tồn tại!'}), 400
    
    # Kiểm tra email đã tồn tại
    if users_collection.find_one({'email': data['email']}):
        return jsonify({'message': 'Email đã được sử dụng!'}), 400
    
    # Kiểm tra user đầu tiên -> admin
    user_count = users_collection.count_documents({})
    role = 'admin' if user_count == 0 else 'user'
    
    # Tạo user mới
    new_user = {
        '_id': f"U{user_count + 1:03d}",
        'username': data['username'],
        'password_hash': generate_password_hash(data['password']),
        'role': role,
        'name': data['name'],
        'email': data['email'],
        'phone': data['phone'],
        'created_at': datetime.datetime.utcnow().isoformat(),
        'last_login': None
    }
    
    try:
        users_collection.insert_one(new_user)
        return jsonify({
            'message': 'Đăng ký thành công!',
            'user_id': new_user['_id'],
            'role': role
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi đăng ký: {str(e)}'}), 500

# API Đăng nhập
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if 'username' not in data or 'password' not in data:
        return jsonify({'message': 'Thiếu username hoặc password!'}), 400
    
    user = users_collection.find_one({'username': data['username']})
    
    if not user:
        return jsonify({'message': 'Tên đăng nhập hoặc mật khẩu không đúng!'}), 401
    
    if not check_password_hash(user['password_hash'], data['password']):
        return jsonify({'message': 'Tên đăng nhập hoặc mật khẩu không đúng!'}), 401
    
    # Cập nhật last_login
    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {'last_login': datetime.datetime.utcnow().isoformat()}}
    )
    
    # Tạo JWT token
    token = jwt.encode({
        'user_id': user['_id'],
        'username': user['username'],
        'role': user['role'],
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }, app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({
        'message': 'Đăng nhập thành công!',
        'token': token,
        'user': {
            'id': user['_id'],
            'username': user['username'],
            'name': user['name'],
            'email': user['email'],
            'role': user['role']
        }
    }), 200

# API Verify token
@app.route('/api/auth/verify', methods=['GET'])
@token_required
def verify_token(current_user):
    return jsonify({
        'valid': True,
        'user': {
            'id': current_user['_id'],
            'username': current_user['username'],
            'name': current_user['name'],
            'email': current_user['email'],
            'role': current_user['role']
        }
    }), 200

# API Get current user
@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    return jsonify({
        'id': current_user['_id'],
        'username': current_user['username'],
        'name': current_user['name'],
        'email': current_user['email'],
        'phone': current_user['phone'],
        'role': current_user['role'],
        'created_at': current_user['created_at'],
        'last_login': current_user['last_login']
    }), 200

# API Đổi mật khẩu
@app.route('/api/auth/change-password', methods=['PUT'])
@token_required
def change_password(current_user):
    data = request.get_json()
    
    if 'old_password' not in data or 'new_password' not in data:
        return jsonify({'message': 'Thiếu mật khẩu cũ hoặc mật khẩu mới!'}), 400
    
    if not check_password_hash(current_user['password_hash'], data['old_password']):
        return jsonify({'message': 'Mật khẩu cũ không đúng!'}), 401
    
    users_collection.update_one(
        {'_id': current_user['_id']},
        {'$set': {'password_hash': generate_password_hash(data['new_password'])}}
    )
    
    return jsonify({'message': 'Đổi mật khẩu thành công!'}), 200

# API Lấy danh sách users (chỉ admin)
@app.route('/api/auth/users', methods=['GET'])
@token_required
@admin_required
def get_users(current_user):
    users = list(users_collection.find({}, {'password_hash': 0}))
    
    # Convert ObjectId to string
    for user in users:
        if '_id' in user:
            user['id'] = user['_id']
    
    return jsonify({'users': users}), 200

if __name__ == '__main__':
    register_service()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=True)