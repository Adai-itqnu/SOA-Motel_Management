from flask import Flask, request, jsonify
from flask_cors import CORS
import atexit

from config import Config
from model import users_collection
from decorators import token_required, admin_required
from service_registry import register_service, deregister_service
from utils import (
    get_timestamp,
    get_user_id,
    can_access_user,
    format_user,
    get_user_update_fields
)


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
atexit.register(deregister_service)


# ============== Health Check ==============

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': Config.SERVICE_NAME}), 200


# ============== User Profile APIs ==============

@app.route('/api/users/me', methods=['GET'])
@token_required
# Get current logged-in user's profile
def get_current_user(current_user):
    user_id = get_user_id(current_user)
    user = users_collection.find_one({'_id': user_id})
    
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    return jsonify(format_user(user, include_sensitive=True)), 200


@app.route('/api/users/me', methods=['PUT'])
@token_required
# Update current user's profile
def update_current_user(current_user):
    user_id = get_user_id(current_user)
    data = request.get_json() or {}
    
    update_fields = get_user_update_fields(data, is_admin=False)
    
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
# Get all users with search and filter (admin only)
def get_all_users(current_user):
    query = {}
    
    if request.args.get('role'):
        query['role'] = request.args.get('role')
    
    if request.args.get('status'):
        query['status'] = request.args.get('status')
    
    search = request.args.get('search', '').strip()
    if search:
        query['$or'] = [
            {'fullname': {'$regex': search, '$options': 'i'}},
            {'email': {'$regex': search, '$options': 'i'}},
            {'phone': {'$regex': search, '$options': 'i'}},
            {'username': {'$regex': search, '$options': 'i'}},
            {'id_card': {'$regex': search, '$options': 'i'}}
        ]
    
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
# Get user by ID
def get_user(current_user, user_id):
    user = users_collection.find_one({'_id': user_id})
    
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    include_sensitive = can_access_user(current_user, user_id)
    
    return jsonify(format_user(user, include_sensitive=include_sensitive)), 200


@app.route('/api/users/<user_id>', methods=['PUT'])
@token_required
@admin_required
# Update user (admin only)
def update_user(current_user, user_id):
    user = users_collection.find_one({'_id': user_id})
    
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    data = request.get_json() or {}
    update_fields = get_user_update_fields(data, is_admin=True)
    
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
# Activate/deactivate user (admin only)
def update_user_status(current_user, user_id):
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
# Delete user (admin only)
def delete_user(current_user, user_id):
    user = users_collection.find_one({'_id': user_id})
    
    if not user:
        return jsonify({'message': 'User không tồn tại!'}), 404
    
    if user.get('role') == 'admin':
        return jsonify({'message': 'Không thể xóa admin!'}), 400
    
    users_collection.delete_one({'_id': user_id})
    
    return jsonify({'message': 'Xóa user thành công!'}), 200


# ============== Internal APIs ==============

@app.route('/internal/users', methods=['GET'])
# Get all users (internal API)
def internal_get_all_users():
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
