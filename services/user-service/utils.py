# User Service - Utility Functions
import datetime
from model import users_collection


# ============== Timestamp ==============

def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


# ============== User Helpers ==============

# Get user ID from token payload
def get_user_id(current_user):
    return current_user.get('user_id') or current_user.get('_id')


# Check if user can access another user's data
def can_access_user(current_user, target_user_id):
    user_id = get_user_id(current_user)
    role = current_user.get('role', '')
    return role == 'admin' or user_id == target_user_id


# ============== Formatting ==============

# Format user for API response
def format_user(user, include_sensitive=False):
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


# ============== Validation ==============

# Get allowed fields for user self-update
def get_user_update_fields(data, is_admin=False):
    if is_admin:
        allowed = ['fullname', 'phone', 'email', 'id_card', 'address', 'role', 'status']
    else:
        allowed = ['fullname', 'phone', 'id_card', 'address']
    return {k: data[k] for k in allowed if k in data}
