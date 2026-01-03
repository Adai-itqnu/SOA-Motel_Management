import datetime
import re
from model import users_collection


def generate_user_id():
    # Find the highest existing ID
    last_user = users_collection.find_one(
        {'_id': {'$regex': '^U\\d+$'}},
        sort=[('_id', -1)]
    )
    
    if last_user:
        try:
            last_num = int(last_user['_id'][1:])
            return f"U{last_num + 1:03d}"
        except (ValueError, IndexError):
            pass
    
    # Fallback: count documents + 1
    count = users_collection.count_documents({})
    return f"U{count + 1:03d}"


# Validate email format
def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


# Validate Vietnamese phone number
def validate_phone(phone):
    if not phone:
        return True  # Phone is optional
    pattern = r'^(0|\+84)[0-9]{9,10}$'
    return bool(re.match(pattern, phone))


# Validate Vietnamese ID card (CCCD/CMND)
def validate_id_card(id_card):
    if not id_card:
        return True  # ID card is optional
    # CCCD: 12 digits, CMND: 9 digits
    return bool(re.match(r'^\d{9}$|^\d{12}$', id_card))


# Check if a field value already exists
def check_duplicate_field(field_name, value, exclude_user_id=None):
    if not value:
        return False
    
    query = {field_name: value}
    if exclude_user_id:
        query['_id'] = {'$ne': exclude_user_id}
    
    return users_collection.find_one(query) is not None


# Get current UTC timestamp in ISO format
def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


# Format user data for API response
def format_user_response(user, include_sensitive=False):
    response = {
        'id': user['_id'],
        'username': user['username'],
        'email': user.get('email', ''),
        'phone': user.get('phone', ''),
        'fullname': user.get('fullname', ''),
        'role': user.get('role', 'user'),
        'status': user.get('status', 'active'),
        'created_at': user.get('created_at'),
        'updated_at': user.get('updated_at')
    }
    
    if include_sensitive:
        response.update({
            'id_card': user.get('id_card', ''),
            'address': user.get('address', '')
        })
    
    return response
