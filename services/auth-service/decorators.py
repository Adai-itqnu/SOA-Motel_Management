"""
Auth Service - Authentication Decorators
Reusable decorators for token and role-based authentication
"""
from functools import wraps
from flask import request, jsonify
import jwt
from config import Config
from model import users_collection


def get_token_from_request():
    """Extract JWT token from request headers"""
    # Support both 'Authorization' and 'authorization' (nginx may lowercase)
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    
    if not token:
        return None
    
    # Remove 'Bearer ' prefix (case insensitive)
    if token.lower().startswith('bearer '):
        token = token[7:]
    
    return token


def decode_token(token):
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, ('Token đã hết hạn!', 401)
    except jwt.InvalidTokenError:
        return None, ('Token không hợp lệ!', 401)


def token_required(f):
    """
    Decorator to require valid JWT token.
    Passes current_user as first argument to decorated function.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        
        if not token:
            return jsonify({'message': 'Token không tồn tại!'}), 401
        
        payload, error = decode_token(token)
        if error:
            return jsonify({'message': error[0]}), error[1]
        
        # Get user from database
        current_user = users_collection.find_one({'_id': payload.get('user_id')})
        
        if not current_user:
            return jsonify({'message': 'Người dùng không tồn tại!'}), 401
        
        # Check if user is active
        if current_user.get('status') == 'inactive':
            return jsonify({'message': 'Tài khoản đã bị vô hiệu hóa!'}), 403
        
        return f(current_user, *args, **kwargs)
    
    return decorated


def admin_required(f):
    """
    Decorator to require admin role.
    Must be used after @token_required.
    """
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.get('role') != 'admin':
            return jsonify({'message': 'Yêu cầu quyền admin!'}), 403
        return f(current_user, *args, **kwargs)
    return decorated
