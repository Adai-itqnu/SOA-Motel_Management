# Payment Service - Decorators
from functools import wraps
import jwt
from flask import request, jsonify
from config import Config


def _get_bearer_token():
    # Extract bearer token from Authorization header
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    if not token:
        return None
    if token.lower().startswith('bearer '):
        return token[7:]
    return token


def token_required(fn):
    # Decorator to require valid JWT token
    @wraps(fn)
    def decorated(*args, **kwargs):
        token = _get_bearer_token()
        if not token:
            return jsonify({'message': 'Token không tồn tại!'}), 401
        
        try:
            payload = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token đã hết hạn!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token không hợp lệ!'}), 401
        
        return fn(payload, *args, **kwargs)
    
    return decorated


def admin_required(fn):
    # Decorator to require admin role
    @wraps(fn)
    def decorated(current_user, *args, **kwargs):
        if current_user.get('role') != 'admin':
            return jsonify({'message': 'Yêu cầu quyền admin!'}), 403
        return fn(current_user, *args, **kwargs)
    
    return decorated


def internal_api_required(fn):
    # Decorator to require internal API key
    @wraps(fn)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-Internal-Api-Key') or request.headers.get('X-Internal-Key')
        if api_key != Config.INTERNAL_API_KEY:
            return jsonify({'message': 'Unauthorized'}), 401
        return fn(*args, **kwargs)
    
    return decorated
