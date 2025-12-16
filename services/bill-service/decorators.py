"""Bill Service - Authentication Decorators"""
from functools import wraps
from flask import request, jsonify
import jwt
from config import Config

def get_token():
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    if token and token.lower().startswith('bearer '):
        token = token[7:]
    return token

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token()
        if not token:
            return jsonify({'message': 'Token không tồn tại!'}), 401
        try:
            payload = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
            return f(payload, *args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token đã hết hạn!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token không hợp lệ!'}), 401
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.get('role') != 'admin':
            return jsonify({'message': 'Yêu cầu quyền admin!'}), 403
        return f(current_user, *args, **kwargs)
    return decorated

def internal_api_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-Internal-Api-Key')
        if not api_key or api_key != Config.INTERNAL_API_KEY:
            return jsonify({'message': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated
