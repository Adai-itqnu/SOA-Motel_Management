from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import jwt
from functools import wraps
import requests
from bson import ObjectId
from config import JWT_SECRET, SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT
from model import tenants_collection
from service_registry import register_service

app = Flask(__name__)
CORS(app)

# Load configuration
app.config['SECRET_KEY'] = JWT_SECRET
app.config['SERVICE_NAME'] = SERVICE_NAME
app.config['SERVICE_PORT'] = SERVICE_PORT

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
            current_user = data
            
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

# Helper function: Get service URL from Consul
def get_service_url(service_name):
    try:
        consul_url = f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(consul_url, timeout=5)
        if response.ok and response.json():
            service = response.json()[0]
            return f"http://{service['ServiceAddress']}:{service['ServicePort']}"
        return None
    except Exception as e:
        print(f"Error getting service URL: {e}")
        return None

# Helper function: Convert string to ObjectId
def to_object_id(id_value):
    """Convert string ID to ObjectId if needed"""
    if isinstance(id_value, ObjectId):
        return id_value
    if isinstance(id_value, str):
        try:
            return ObjectId(id_value)
        except Exception:
            return id_value  # Return as-is if conversion fails
    return id_value

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': app.config['SERVICE_NAME']}), 200

# ============== TENANT APIs ==============

# API Lấy danh sách người thuê (lấy từ users collection, role != 'admin')
@app.route('/api/tenants', methods=['GET'])
@token_required
@admin_required
def get_tenants(current_user):
    try:
        search = request.args.get('search', '').strip()
        status = request.args.get('status', '').strip()
        
        # Lấy tất cả users (trừ admin), có thể filter theo role
        query = {'role': {'$ne': 'admin'}}  # Lấy user và tenant, không lấy admin
        
        if search:
            # Kết hợp điều kiện search với điều kiện role
            search_conditions = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'phone': {'$regex': search, '$options': 'i'}},
                {'id_card': {'$regex': search, '$options': 'i'}},
                {'username': {'$regex': search, '$options': 'i'}},
                {'email': {'$regex': search, '$options': 'i'}}
            ]
            # Tạo query mới với $and để kết hợp cả role và search
            query = {
                '$and': [
                    {'role': {'$ne': 'admin'}},
                    {'$or': search_conditions}
                ]
            }
        if status:
            # Nếu đã có $and thì thêm vào, nếu không thì thêm trực tiếp
            if '$and' in query:
                query['$and'].append({'status': status})
            else:
                query['status'] = status
        
        tenants_cursor = tenants_collection.find(query).sort('created_at', -1)
        tenants = list(tenants_cursor)
        
        # Process tenants to format data
        result_tenants = []
        for tenant in tenants:
            tenant_dict = {}
            # Convert all fields to JSON-serializable format
            for key, value in tenant.items():
                # Bỏ qua password_hash
                if key == 'password_hash':
                    continue
                if isinstance(value, ObjectId):
                    tenant_dict[key] = str(value)
                elif isinstance(value, datetime.datetime):
                    tenant_dict[key] = value.isoformat()
                else:
                    tenant_dict[key] = value
            
            # Ensure 'id' field exists
            tenant_dict['id'] = tenant_dict.get('_id', '')
            # Đảm bảo có các trường tenant
            if 'id_card' not in tenant_dict:
                tenant_dict['id_card'] = ''
            if 'address' not in tenant_dict:
                tenant_dict['address'] = ''
            if 'status' not in tenant_dict:
                tenant_dict['status'] = 'active'
            
            result_tenants.append(tenant_dict)
        
        return jsonify({
            'tenants': result_tenants, 
            'total': len(result_tenants)
        }), 200
        
    except Exception as e:
        print(f"Error in get_tenants: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'message': f'Lỗi khi lấy danh sách người thuê: {str(e)}',
            'tenants': [],
            'total': 0
        }), 500

# API Lấy chi tiết người thuê
@app.route('/api/tenants/<tenant_id>', methods=['GET'])
@token_required
def get_tenant(current_user, tenant_id):
    tenant_id = to_object_id(tenant_id)
    tenant = tenants_collection.find_one({'_id': tenant_id})
    
    if not tenant:
        return jsonify({'message': 'Người thuê không tồn tại!'}), 404
    
    tenant['id'] = tenant['_id']
    # Bỏ password_hash khỏi response
    tenant.pop('password_hash', None)
    
    # Đảm bảo có các trường tenant
    if 'id_card' not in tenant:
        tenant['id_card'] = ''
    if 'address' not in tenant:
        tenant['address'] = ''
    if 'status' not in tenant:
        tenant['status'] = 'active'
    
    # Lấy danh sách hợp đồng của tenant từ contract-service (nếu cần)
    # Có thể gọi contract-service API sau nếu cần hiển thị contracts trong tenant detail
    tenant['contracts'] = []  # Tạm thời để trống, có thể gọi contract-service sau
    
    return jsonify(tenant), 200

# API Tạo người thuê mới (tạo user account với thông tin tenant)
@app.route('/api/tenants', methods=['POST'])
@token_required
@admin_required
def create_tenant(current_user):
    data = request.get_json()
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    
    # Validation
    required_fields = ['name', 'phone', 'id_card', 'address']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Kiểm tra CMND/CCCD đã tồn tại (nếu có)
    if data.get('id_card'):
        existing = tenants_collection.find_one({'id_card': data['id_card']})
        if existing:
            return jsonify({'message': 'CMND/CCCD đã tồn tại!'}), 400
    
    # Kiểm tra phone đã tồn tại
    existing_phone = tenants_collection.find_one({'phone': data['phone']})
    if existing_phone:
        return jsonify({'message': 'Số điện thoại đã được sử dụng!'}), 400
    
    # Tạo username tự động nếu không có
    username = data.get('username', '')
    if not username:
        phone_clean = data['phone'].replace(' ', '').replace('-', '')
        username = f"user_{phone_clean}"
        # Đảm bảo username unique
        counter = 1
        while tenants_collection.find_one({'username': username}):
            username = f"user_{phone_clean}_{counter}"
            counter += 1
    
    # Kiểm tra username đã tồn tại
    if tenants_collection.find_one({'username': username}):
        return jsonify({'message': 'Tên đăng nhập đã tồn tại!'}), 400
    
    # Tạo password mặc định
    password = data.get('password', '123456')
    
    # Tạo user account (dùng chung users collection)
    # Tìm user_id lớn nhất để tạo ID mới
    existing_users = list(tenants_collection.find({}, {'_id': 1}).sort('_id', -1).limit(1))
    if existing_users and existing_users[0].get('_id'):
        last_id = existing_users[0]['_id']
        if last_id.startswith('U'):
            try:
                last_num = int(last_id[1:])
                user_id = f"U{last_num + 1:03d}"
            except:
                user_count = tenants_collection.count_documents({})
                user_id = f"U{user_count + 1:03d}"
        else:
            user_count = tenants_collection.count_documents({})
            user_id = f"U{user_count + 1:03d}"
    else:
        user_count = tenants_collection.count_documents({})
        user_id = f"U{user_count + 1:03d}"
    
    # Import từ werkzeug để hash password
    from werkzeug.security import generate_password_hash
    
    new_user = {
        '_id': user_id,
        'username': username,
        'password_hash': generate_password_hash(password),
        'role': 'user',  # Tất cả tenant mới tạo đều là user
        'name': data['name'],
        'phone': data['phone'],
        'email': data.get('email', f"{username}@motel.local"),
        'id_card': data['id_card'],
        'address': data['address'],
        'date_of_birth': data.get('date_of_birth', ''),
        'status': 'active',
        'created_at': datetime.datetime.utcnow().isoformat(),
        'updated_at': datetime.datetime.utcnow().isoformat(),
        'last_login': None
    }
    
    try:
        tenants_collection.insert_one(new_user)
        new_user['id'] = new_user['_id']
        # Bỏ password_hash khỏi response
        new_user.pop('password_hash', None)
        return jsonify({
            'message': 'Tạo người thuê thành công!',
            'tenant': new_user,
            'user_id': user_id,
            'username': username
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo người thuê: {str(e)}'}), 500

# API Cập nhật người thuê
@app.route('/api/tenants/<tenant_id>', methods=['PUT'])
@token_required
@admin_required
def update_tenant(current_user, tenant_id):
    data = request.get_json()
    tenant_id = to_object_id(tenant_id)
    
    tenant = tenants_collection.find_one({'_id': tenant_id})
    if not tenant:
        return jsonify({'message': 'Người thuê không tồn tại!'}), 404
    
    # Kiểm tra CMND/CCCD trùng (nếu đổi và có giá trị)
    if 'id_card' in data and data['id_card'] and data['id_card'] != tenant.get('id_card', ''):
        existing = tenants_collection.find_one({'id_card': data['id_card']})
        if existing and existing['_id'] != tenant_id:
            return jsonify({'message': 'CMND/CCCD đã tồn tại!'}), 400
    
    # Kiểm tra phone trùng (nếu đổi)
    if 'phone' in data and data['phone'] != tenant.get('phone', ''):
        existing = tenants_collection.find_one({'phone': data['phone']})
        if existing and existing['_id'] != tenant_id:
            return jsonify({'message': 'Số điện thoại đã được sử dụng!'}), 400
    
    # Cập nhật các trường
    update_fields = {}
    allowed_fields = ['name', 'phone', 'id_card', 'address', 'email', 'date_of_birth', 'status']
    
    for field in allowed_fields:
        if field in data:
            update_fields[field] = data[field]
    
    update_fields['updated_at'] = datetime.datetime.utcnow().isoformat()
    
    try:
        tenants_collection.update_one(
            {'_id': tenant_id},
            {'$set': update_fields}
        )
        
        updated_tenant = tenants_collection.find_one({'_id': tenant_id})
        updated_tenant['id'] = updated_tenant['_id']
        # Bỏ password_hash khỏi response
        updated_tenant.pop('password_hash', None)
        
        return jsonify({
            'message': 'Cập nhật người thuê thành công!',
            'tenant': updated_tenant
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi cập nhật: {str(e)}'}), 500

# API Xóa người thuê (chỉ đánh dấu inactive, không xóa user account)
@app.route('/api/tenants/<tenant_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_tenant(current_user, tenant_id):
    tenant_id = to_object_id(tenant_id)
    tenant = tenants_collection.find_one({'_id': tenant_id})
    
    if not tenant:
        return jsonify({'message': 'Người thuê không tồn tại!'}), 404
    
    # Không cho xóa admin
    if tenant.get('role') == 'admin':
        return jsonify({'message': 'Không thể xóa tài khoản admin!'}), 400
    
    try:
        # Đánh dấu inactive thay vì xóa (để giữ lại user account)
        tenants_collection.update_one(
            {'_id': tenant_id},
            {
                '$set': {
                    'status': 'inactive',
                    'updated_at': datetime.datetime.utcnow().isoformat()
                }
            }
        )
        return jsonify({'message': 'Vô hiệu hóa người thuê thành công!'}), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi vô hiệu hóa người thuê: {str(e)}'}), 500

if __name__ == '__main__':
    register_service()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=True)