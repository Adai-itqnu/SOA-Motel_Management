"""
User Service Decorators
JWT token validation and role checks
"""
from functools import wraps
from flask import request, jsonify
import jwt
from config import Config


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization') or request.headers.get('authorization')
        
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
        
        if not token:
            return jsonify({'message': 'Token không tìm thấy!'}), 401
        
        try:
            data = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
            current_user = {
                'user_id': data.get('user_id'),
                '_id': data.get('user_id'),
                'username': data.get('username'),
                'role': data.get('role', 'user')
            }
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token đã hết hạn!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token không hợp lệ!'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.get('role') != 'admin':
            return jsonify({'message': 'Chỉ admin mới có quyền!'}), 403
        return f(current_user, *args, **kwargs)
    
    return decorated
