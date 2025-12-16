"""
User Service - Main Application
CRUD operations for user management
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import atexit

from config import Config
from model import users_collection
from decorators import token_required, admin_required
from service_registry import register_service, deregister_service


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
atexit.register(deregister_service)


def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


def format_user(user, include_sensitive=False):
    """Format user for API response"""
    response = {
        '_id': user['_id'],
        'username': user.get('username', ''),
        'email': user.get('email', ''),
        'phone': user.get('phone', ''),
        'fullname': user.get('fullname', ''),
        'role': user.get('role', 'user'),
        'status': user.get('status', 'active'),
        'created_at': user.get('created_at'),
        'updated_at': user.get('updated_at')
    }
    
    if include_sensitive:
        response['id_card'] = user.get('id_card', '')
        response['address'] = user.get('address', '')
    
    return response


# ============== Health Check ==============

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': Config.SERVICE_NAME}), 200


# ============== User Profile APIs ==============

@app.route('/api/users/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    """Get current logged-in user's profile"""
    user_id = current_user.get('user_id') or current_user.get('_id')
    user = users_collection.find_one({'_id': user_id})
    
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    return jsonify(format_user(user, include_sensitive=True)), 200


@app.route('/api/users/me', methods=['PUT'])
@token_required
def update_current_user(current_user):
    """Update current user's profile"""
    user_id = current_user.get('user_id') or current_user.get('_id')
    data = request.get_json() or {}
    
    # Allowed fields for user to update themselves
    allowed = ['fullname', 'phone', 'id_card', 'address']
    update_fields = {k: data[k] for k in allowed if k in data}
    
    if not update_fields:
        return jsonify({'message': 'Không có dữ liệu cập nhật!'}), 400
    
    update_fields['updated_at'] = get_timestamp()
    
    users_collection.update_one({'_id': user_id}, {'$set': update_fields})
    updated = users_collection.find_one({'_id': user_id})
    
    return jsonify({
        'message': 'Cập nhật thành công!',
        'user': format_user(updated, include_sensitive=True)
    }), 200


# ============== Admin User Management APIs ==============

@app.route('/api/users', methods=['GET'])
@token_required
@admin_required
def get_all_users(current_user):
    """Get all users with search and filter (admin only)"""
    query = {}
    
    # Filter by role
    if request.args.get('role'):
        query['role'] = request.args.get('role')
    
    # Filter by status
    if request.args.get('status'):
        query['status'] = request.args.get('status')
    
    # Search by keyword (fullname, email, phone, username)
    search = request.args.get('search', '').strip()
    if search:
        query['$or'] = [
            {'fullname': {'$regex': search, '$options': 'i'}},
            {'email': {'$regex': search, '$options': 'i'}},
            {'phone': {'$regex': search, '$options': 'i'}},
            {'username': {'$regex': search, '$options': 'i'}},
            {'id_card': {'$regex': search, '$options': 'i'}}
        ]
    
    # Pagination
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    skip = (page - 1) * limit
    
    total = users_collection.count_documents(query)
    users = list(users_collection.find(query).sort('created_at', -1).skip(skip).limit(limit))
    
    return jsonify({
        'users': [format_user(u, include_sensitive=True) for u in users],
        'total': total,
        'page': page,
        'limit': limit,
        'pages': (total + limit - 1) // limit
    }), 200


@app.route('/api/users/<user_id>', methods=['GET'])
@token_required
def get_user(current_user, user_id):
    """Get user by ID"""
    user = users_collection.find_one({'_id': user_id})
    
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    current_id = current_user.get('user_id') or current_user.get('_id')
    role = current_user.get('role', '')
    
    # Only admin or the user themselves can see full info
    include_sensitive = (role == 'admin' or current_id == user_id)
    
    return jsonify(format_user(user, include_sensitive=include_sensitive)), 200


@app.route('/api/users/<user_id>', methods=['PUT'])
@token_required
@admin_required
def update_user(current_user, user_id):
    """Update user (admin only)"""
    user = users_collection.find_one({'_id': user_id})
    
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    data = request.get_json() or {}
    
    # Admin can update more fields
    allowed = ['fullname', 'phone', 'email', 'id_card', 'address', 'role', 'status']
    update_fields = {k: data[k] for k in allowed if k in data}
    
    if not update_fields:
        return jsonify({'message': 'Không có dữ liệu cập nhật!'}), 400
    
    update_fields['updated_at'] = get_timestamp()
    
    users_collection.update_one({'_id': user_id}, {'$set': update_fields})
    updated = users_collection.find_one({'_id': user_id})
    
    return jsonify({
        'message': 'Cập nhật user thành công!',
        'user': format_user(updated, include_sensitive=True)
    }), 200


@app.route('/api/users/<user_id>/status', methods=['PUT'])
@token_required
@admin_required
def update_user_status(current_user, user_id):
    """Activate/deactivate user (admin only)"""
    user = users_collection.find_one({'_id': user_id})
    
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    data = request.get_json() or {}
    new_status = data.get('status')
    
    if new_status not in ['active', 'inactive']:
        return jsonify({'message': 'Status không hợp lệ!'}), 400
    
    users_collection.update_one(
        {'_id': user_id},
        {'$set': {'status': new_status, 'updated_at': get_timestamp()}}
    )
    
    return jsonify({'message': f"Đã {'kích hoạt' if new_status == 'active' else 'vô hiệu hóa'} user!"}), 200


@app.route('/api/users/<user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, user_id):
    """Delete user (admin only)"""
    user = users_collection.find_one({'_id': user_id})
    
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    # Don't allow deleting admin
    if user.get('role') == 'admin':
        return jsonify({'message': 'Không thể xóa admin!'}), 400
    
    users_collection.delete_one({'_id': user_id})
    
    return jsonify({'message': 'Xóa user thành công!'}), 200


# ============== Internal APIs ==============

@app.route('/internal/users', methods=['GET'])
def internal_get_all_users():
    """Get all users (internal API for service-to-service communication)"""
    # Verify internal API key
    api_key = request.headers.get('X-Internal-Key') or request.headers.get('X-Internal-Api-Key')
    if api_key != Config.INTERNAL_API_KEY:
        return jsonify({'message': 'Unauthorized'}), 401
    
    users = list(users_collection.find({'status': 'active'}))
    
    return jsonify({
        'users': [format_user(u, include_sensitive=False) for u in users]
    }), 200


# ============== Entry Point ==============

if __name__ == '__main__':
    print(f"\n{'='*50}")
    print(f"  {Config.SERVICE_NAME.upper()}")
    print(f"  Port: {Config.SERVICE_PORT}")
    print(f"{'='*50}\n")
    
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)
