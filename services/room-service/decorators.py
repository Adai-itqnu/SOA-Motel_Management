# Room Service - Authentication Decorators
from functools import wraps
from flask import request, jsonify
import jwt
from config import Config


# Extract JWT token from request headers
def get_token_from_request():
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    
    if not token:
        return None
    
    if token.lower().startswith('bearer '):
        token = token[7:]
    
    return token


# Decode and validate JWT token
def decode_token(token):
    try:
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, ('Token đã hết hạn!', 401)
    except jwt.InvalidTokenError:
        return None, ('Token không hợp lệ!', 401)


# Decorator to require valid JWT token
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = get_token_from_request()
        
        if not token:
            return jsonify({'message': 'Token không tồn tại!'}), 401
        
        payload, error = decode_token(token)
        if error:
            return jsonify({'message': error[0]}), error[1]
        
        # Pass the decoded token payload as current_user
        return f(payload, *args, **kwargs)
    
    return decorated


# Decorator to require admin role
def admin_required(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.get('role') != 'admin':
            return jsonify({'message': 'Yêu cầu quyền admin!'}), 403
        return f(current_user, *args, **kwargs)
    return decorated


# Decorator to require internal API key for service-to-service calls
def internal_api_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-Internal-Api-Key')
        if not api_key or api_key != Config.INTERNAL_API_KEY:
            return jsonify({'message': 'Unauthorized internal request'}), 403
        return f(*args, **kwargs)
    return decorated
