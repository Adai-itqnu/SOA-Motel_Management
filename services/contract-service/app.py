from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import uuid
import jwt
from functools import wraps
import requests
from bson import ObjectId
from config import JWT_SECRET, SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT, INTERNAL_API_KEY
from model import contracts_collection
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

# Decorator for internal API calls
def internal_api_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('X-Internal-Api-Key')
        if not token or token != INTERNAL_API_KEY:
            return jsonify({'message': 'Unauthorized internal request'}), 403
        return f(*args, **kwargs)
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

# Helper function: Check if room exists and is available
def check_room_availability(room_id, token):
    try:
        room_service_url = get_service_url('room-service')
        if not room_service_url:
            return None, "Không thể kết nối tới Room Service"
        
        # Ensure token has Bearer prefix
        if token and not token.startswith('Bearer ') and not token.startswith('bearer '):
            auth_token = f'Bearer {token}'
        else:
            auth_token = token
        
        response = requests.get(
            f"{room_service_url}/api/rooms/{room_id}",
            headers={'Authorization': auth_token},
            timeout=5
        )
        
        if response.ok:
            room = response.json()
            return room, None
        else:
            return None, "Phòng không tồn tại"
    except Exception as e:
        return None, f"Lỗi kết nối Room Service: {str(e)}"

# Helper function: Update room status
def update_room_status(room_id, status, tenant_id, token):
    try:
        room_service_url = get_service_url('room-service')
        if not room_service_url:
            return False
        
        # Ensure token has Bearer prefix
        if token and not token.startswith('Bearer ') and not token.startswith('bearer '):
            auth_token = f'Bearer {token}'
        else:
            auth_token = token
        
        update_data = {'status': status}
        if tenant_id:
            update_data['tenant_id'] = str(tenant_id) if isinstance(tenant_id, ObjectId) else tenant_id
        
        response = requests.put(
            f"{room_service_url}/api/rooms/{room_id}",
            json=update_data,
            headers={
                'Authorization': auth_token,
                'Content-Type': 'application/json'
            },
            timeout=5
        )
        
        return response.ok
    except Exception as e:
        print(f"Error updating room status: {e}")
        return False

# Helper function: Get tenant info from tenant-service
def get_tenant_info(tenant_id, token):
    """Get tenant information from tenant-service"""
    try:
        tenant_service_url = get_service_url('tenant-service')
        if not tenant_service_url:
            return None
        
        # Ensure token has Bearer prefix
        if token and not token.startswith('Bearer ') and not token.startswith('bearer '):
            auth_token = f'Bearer {token}'
        else:
            auth_token = token
        
        # Convert tenant_id to string if ObjectId
        tenant_id_str = str(tenant_id) if isinstance(tenant_id, ObjectId) else tenant_id
        
        response = requests.get(
            f"{tenant_service_url}/api/tenants/{tenant_id_str}",
            headers={'Authorization': auth_token},
            timeout=5
        )
        
        if response.ok:
            return response.json()
        return None
    except Exception as e:
        print(f"Error getting tenant info: {e}")
        return None

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': SERVICE_NAME}), 200

# ============== CONTRACT APIs ==============

# API Lấy danh sách hợp đồng
@app.route('/api/contracts', methods=['GET'])
@token_required
@admin_required
def get_contracts(current_user):
    try:
        status = request.args.get('status', '').strip()
        room_id = request.args.get('room_id', '').strip()
        
        query = {}
        if status:
            query['status'] = status
        if room_id:
            query['room_id'] = room_id
        
        # Find contracts with query
        contracts_cursor = contracts_collection.find(query).sort('created_at', -1)
        contracts = list(contracts_cursor)
        
        # Process contracts to add tenant info and format data
        result_contracts = []
        token = request.headers.get('Authorization') or request.headers.get('authorization')
        
        for contract in contracts:
            contract_dict = {}
            # Convert all fields to JSON-serializable format
            for key, value in contract.items():
                if isinstance(value, ObjectId):
                    contract_dict[key] = str(value)
                elif isinstance(value, datetime.datetime):
                    contract_dict[key] = value.isoformat()
                else:
                    contract_dict[key] = value
            
            # Ensure 'id' field exists
            contract_dict['id'] = contract_dict.get('_id', '')
            
            # Lấy thông tin tenant từ tenant-service
            contract_tenant_id = contract.get('tenant_id')
            if contract_tenant_id:
                contract_tenant_id = to_object_id(contract_tenant_id)
                tenant = get_tenant_info(contract_tenant_id, token)
                if tenant:
                    contract_dict['tenant_name'] = tenant.get('name', '')
                    contract_dict['tenant_phone'] = tenant.get('phone', '')
                else:
                    contract_dict['tenant_name'] = ''
                    contract_dict['tenant_phone'] = ''
            else:
                contract_dict['tenant_name'] = ''
                contract_dict['tenant_phone'] = ''
            
            result_contracts.append(contract_dict)
        
        return jsonify({
            'contracts': result_contracts, 
            'total': len(result_contracts)
        }), 200
        
    except Exception as e:
        print(f"Error in get_contracts: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'message': f'Lỗi khi lấy danh sách hợp đồng: {str(e)}',
            'contracts': [],
            'total': 0
        }), 500

# API Lấy chi tiết hợp đồng
@app.route('/api/contracts/<contract_id>', methods=['GET'])
@token_required
def get_contract(current_user, contract_id):
    contract = contracts_collection.find_one({'_id': contract_id})
    
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    contract['id'] = contract['_id']
    
    # Lấy thông tin tenant từ tenant-service
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    contract_tenant_id = contract.get('tenant_id')
    if contract_tenant_id:
        contract_tenant_id = to_object_id(contract_tenant_id)
        tenant = get_tenant_info(contract_tenant_id, token)
        if tenant:
            contract['tenant_info'] = {
                'id': str(tenant.get('id', tenant.get('_id', ''))),
                'name': tenant.get('name', ''),
                'phone': tenant.get('phone', ''),
                'id_card': tenant.get('id_card', ''),
                'address': tenant.get('address', '')
            }
        else:
            contract['tenant_info'] = {
                'id': '',
                'name': '',
                'phone': '',
                'id_card': '',
                'address': ''
            }
    else:
        contract['tenant_info'] = {
            'id': '',
            'name': '',
            'phone': '',
            'id_card': '',
            'address': ''
        }
    
    # Convert ObjectId to string
    if isinstance(contract.get('tenant_id'), ObjectId):
        contract['tenant_id'] = str(contract['tenant_id'])
    
    return jsonify(contract), 200

# API Tạo hợp đồng mới
@app.route('/api/contracts', methods=['POST'])
@token_required
@admin_required
def create_contract(current_user):
    data = request.get_json()
    # Get token from header (try both cases)
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    
    if not token:
        return jsonify({'message': 'Token không tồn tại!'}), 401
    
    # Validation
    required_fields = ['tenant_id', 'room_id', 'start_date', 'end_date', 'monthly_rent', 'deposit']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Kiểm tra tenant tồn tại
    tenant_id = to_object_id(data['tenant_id'])
    tenant = get_tenant_info(tenant_id, token)
    if not tenant:
        return jsonify({'message': 'Người thuê không tồn tại!'}), 404
    
    # Kiểm tra phòng có available không
    room, error = check_room_availability(data['room_id'], token)
    if error:
        return jsonify({'message': error}), 400
    
    if room['status'] != 'available':
        return jsonify({'message': 'Phòng không còn trống!'}), 400
    
    # Kiểm tra ngày hợp lệ
    try:
        start_date = datetime.datetime.fromisoformat(data['start_date'])
        end_date = datetime.datetime.fromisoformat(data['end_date'])
        
        if end_date <= start_date:
            return jsonify({'message': 'Ngày kết thúc phải sau ngày bắt đầu!'}), 400
    except:
        return jsonify({'message': 'Định dạng ngày không hợp lệ!'}), 400
    
    # Tạo contract_id sử dụng UUID (thread-safe)
    contract_id = f"C{uuid.uuid4().hex[:8].upper()}"
    
    # Đảm bảo contract_id không trùng (retry nếu cần)
    while contracts_collection.find_one({'_id': contract_id}):
        contract_id = f"C{uuid.uuid4().hex[:8].upper()}"
    
    new_contract = {
        '_id': contract_id,
        'tenant_id': tenant_id,  # Sử dụng tenant_id đã convert
        'room_id': data['room_id'],
        'start_date': data['start_date'],
        'end_date': data['end_date'],
        'monthly_rent': float(data['monthly_rent']),
        'deposit': float(data['deposit']),
        'electric_price': float(data.get('electric_price', 3500)),
        'water_price': float(data.get('water_price', 20000)),
        'status': 'active',  # active | expired | terminated
        'payment_day': int(data.get('payment_day', 5)),  # Ngày thanh toán hàng tháng
        'notes': data.get('notes', ''),
        'created_at': datetime.datetime.utcnow().isoformat(),
        'updated_at': datetime.datetime.utcnow().isoformat()
    }
    
    try:
        # Tạo hợp đồng
        contracts_collection.insert_one(new_contract)
        
        # Cập nhật trạng thái phòng
        update_success = update_room_status(
            data['room_id'], 
            'occupied', 
            tenant_id,  # Sử dụng tenant_id đã convert
            token
        )
        
        if not update_success:
            # Rollback nếu cập nhật phòng thất bại
            contracts_collection.delete_one({'_id': contract_id})
            return jsonify({'message': 'Không thể cập nhật trạng thái phòng!'}), 500
        
        new_contract['id'] = new_contract['_id']
        return jsonify({
            'message': 'Tạo hợp đồng thành công!',
            'contract': new_contract
        }), 201
        
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo hợp đồng: {str(e)}'}), 500

# API Kết thúc hợp đồng
@app.route('/api/contracts/<contract_id>/terminate', methods=['PUT'])
@token_required
@admin_required
def terminate_contract(current_user, contract_id):
    # Get token from header (try both cases)
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    
    if not token:
        return jsonify({'message': 'Token không tồn tại!'}), 401
    
    contract = contracts_collection.find_one({'_id': contract_id})
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    if contract['status'] != 'active':
        return jsonify({'message': 'Hợp đồng đã kết thúc!'}), 400
    
    try:
        # Cập nhật trạng thái hợp đồng
        contracts_collection.update_one(
            {'_id': contract_id},
            {
                '$set': {
                    'status': 'terminated',
                    'end_date': datetime.datetime.utcnow().isoformat(),
                    'updated_at': datetime.datetime.utcnow().isoformat()
                }
            }
        )
        
        # Cập nhật trạng thái phòng về available
        update_room_status(contract['room_id'], 'available', None, token)
        
        return jsonify({'message': 'Kết thúc hợp đồng thành công!'}), 200
        
    except Exception as e:
        return jsonify({'message': f'Lỗi kết thúc hợp đồng: {str(e)}'}), 500

# API Gia hạn hợp đồng
@app.route('/api/contracts/<contract_id>/extend', methods=['PUT'])
@token_required
@admin_required
def extend_contract(current_user, contract_id):
    data = request.get_json()
    
    if 'new_end_date' not in data:
        return jsonify({'message': 'Thiếu ngày kết thúc mới!'}), 400
    
    contract = contracts_collection.find_one({'_id': contract_id})
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    if contract['status'] != 'active':
        return jsonify({'message': 'Chỉ có thể gia hạn hợp đồng đang hoạt động!'}), 400
    
    try:
        new_end_date = datetime.datetime.fromisoformat(data['new_end_date'])
        old_end_date = datetime.datetime.fromisoformat(contract['end_date'])
        
        if new_end_date <= old_end_date:
            return jsonify({'message': 'Ngày kết thúc mới phải sau ngày kết thúc hiện tại!'}), 400
        
        contracts_collection.update_one(
            {'_id': contract_id},
            {
                '$set': {
                    'end_date': data['new_end_date'],
                    'updated_at': datetime.datetime.utcnow().isoformat()
                }
            }
        )
        
        return jsonify({'message': 'Gia hạn hợp đồng thành công!'}), 200
        
    except:
        return jsonify({'message': 'Định dạng ngày không hợp lệ!'}), 400

# API Lấy hợp đồng theo phòng
@app.route('/api/contracts/room/<room_id>', methods=['GET'])
@token_required
def get_contracts_by_room(current_user, room_id):
    contracts = list(contracts_collection.find({'room_id': room_id}).sort('created_at', -1))
    
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    for contract in contracts:
        contract['id'] = contract['_id']
        contract_tenant_id = contract.get('tenant_id')
        if contract_tenant_id:
            contract_tenant_id = to_object_id(contract_tenant_id)
            tenant = get_tenant_info(contract_tenant_id, token)
            if tenant:
                contract['tenant_name'] = tenant.get('name', '')
                contract['tenant_phone'] = tenant.get('phone', '')
            else:
                contract['tenant_name'] = ''
                contract['tenant_phone'] = ''
        else:
            contract['tenant_name'] = ''
            contract['tenant_phone'] = ''
    
    return jsonify({'contracts': contracts, 'total': len(contracts)}), 200

if __name__ == '__main__':
    import os
    register_service()
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=debug_mode)

