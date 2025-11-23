from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import jwt
from functools import wraps
import requests
from config import JWT_SECRET, SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT
from model import tenants_collection, contracts_collection
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

# Helper function: Check if room exists and is available
def check_room_availability(room_id, token):
    try:
        room_service_url = get_service_url('room-service')
        if not room_service_url:
            return None, "Không thể kết nối tới Room Service"
        
        response = requests.get(
            f"{room_service_url}/api/rooms/{room_id}",
            headers={'Authorization': f'Bearer {token}'},
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
        
        response = requests.put(
            f"{room_service_url}/api/rooms/{room_id}",
            json={'status': status, 'tenant_id': tenant_id},
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            },
            timeout=5
        )
        
        return response.ok
    except Exception as e:
        print(f"Error updating room status: {e}")
        return False

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': app.config['SERVICE_NAME']}), 200

# ============== TENANT APIs ==============

# API Lấy danh sách người thuê
@app.route('/api/tenants', methods=['GET'])
@token_required
@admin_required
def get_tenants(current_user):
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    
    query = {}
    if search:
        query['$or'] = [
            {'name': {'$regex': search, '$options': 'i'}},
            {'phone': {'$regex': search, '$options': 'i'}},
            {'id_card': {'$regex': search, '$options': 'i'}}
        ]
    if status:
        query['status'] = status
    
    tenants = list(tenants_collection.find(query).sort('created_at', -1))
    
    for tenant in tenants:
        tenant['id'] = tenant['_id']
    
    return jsonify({'tenants': tenants, 'total': len(tenants)}), 200

# API Lấy chi tiết người thuê
@app.route('/api/tenants/<tenant_id>', methods=['GET'])
@token_required
def get_tenant(current_user, tenant_id):
    tenant = tenants_collection.find_one({'_id': tenant_id})
    
    if not tenant:
        return jsonify({'message': 'Người thuê không tồn tại!'}), 404
    
    tenant['id'] = tenant['_id']
    
    # Lấy danh sách hợp đồng của tenant
    contracts = list(contracts_collection.find({'tenant_id': tenant_id}).sort('start_date', -1))
    for contract in contracts:
        contract['id'] = contract['_id']
    
    tenant['contracts'] = contracts
    
    return jsonify(tenant), 200

# API Tạo người thuê mới
@app.route('/api/tenants', methods=['POST'])
@token_required
@admin_required
def create_tenant(current_user):
    data = request.get_json()
    
    # Validation
    required_fields = ['name', 'phone', 'id_card', 'address']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Kiểm tra CMND/CCCD đã tồn tại
    if tenants_collection.find_one({'id_card': data['id_card']}):
        return jsonify({'message': 'CMND/CCCD đã tồn tại!'}), 400
    
    # Tạo tenant_id tự động
    tenant_count = tenants_collection.count_documents({})
    tenant_id = f"T{tenant_count + 1:04d}"
    
    new_tenant = {
        '_id': tenant_id,
        'name': data['name'],
        'phone': data['phone'],
        'id_card': data['id_card'],
        'address': data['address'],
        'email': data.get('email', ''),
        'date_of_birth': data.get('date_of_birth', ''),
        'status': 'active',  # active | inactive
        'created_at': datetime.datetime.utcnow().isoformat(),
        'updated_at': datetime.datetime.utcnow().isoformat()
    }
    
    try:
        tenants_collection.insert_one(new_tenant)
        new_tenant['id'] = new_tenant['_id']
        return jsonify({
            'message': 'Tạo người thuê thành công!',
            'tenant': new_tenant
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo người thuê: {str(e)}'}), 500

# API Cập nhật người thuê
@app.route('/api/tenants/<tenant_id>', methods=['PUT'])
@token_required
@admin_required
def update_tenant(current_user, tenant_id):
    data = request.get_json()
    
    tenant = tenants_collection.find_one({'_id': tenant_id})
    if not tenant:
        return jsonify({'message': 'Người thuê không tồn tại!'}), 404
    
    # Kiểm tra CMND/CCCD trùng (nếu đổi)
    if 'id_card' in data and data['id_card'] != tenant['id_card']:
        if tenants_collection.find_one({'id_card': data['id_card']}):
            return jsonify({'message': 'CMND/CCCD đã tồn tại!'}), 400
    
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
        
        return jsonify({
            'message': 'Cập nhật người thuê thành công!',
            'tenant': updated_tenant
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi cập nhật: {str(e)}'}), 500

# API Xóa người thuê
@app.route('/api/tenants/<tenant_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_tenant(current_user, tenant_id):
    tenant = tenants_collection.find_one({'_id': tenant_id})
    
    if not tenant:
        return jsonify({'message': 'Người thuê không tồn tại!'}), 404
    
    # Kiểm tra có hợp đồng đang active không
    active_contract = contracts_collection.find_one({
        'tenant_id': tenant_id,
        'status': 'active'
    })
    
    if active_contract:
        return jsonify({'message': 'Không thể xóa người thuê đang có hợp đồng!'}), 400
    
    try:
        tenants_collection.delete_one({'_id': tenant_id})
        return jsonify({'message': 'Xóa người thuê thành công!'}), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi xóa người thuê: {str(e)}'}), 500

# ============== CONTRACT APIs ==============

# API Lấy danh sách hợp đồng
@app.route('/api/contracts', methods=['GET'])
@token_required
@admin_required
def get_contracts(current_user):
    status = request.args.get('status', '')
    room_id = request.args.get('room_id', '')
    
    query = {}
    if status:
        query['status'] = status
    if room_id:
        query['room_id'] = room_id
    
    contracts = list(contracts_collection.find(query).sort('created_at', -1))
    
    for contract in contracts:
        contract['id'] = contract['_id']
        # Lấy thông tin tenant
        tenant = tenants_collection.find_one({'_id': contract['tenant_id']})
        if tenant:
            contract['tenant_name'] = tenant['name']
            contract['tenant_phone'] = tenant['phone']
    
    return jsonify({'contracts': contracts, 'total': len(contracts)}), 200

# API Lấy chi tiết hợp đồng
@app.route('/api/contracts/<contract_id>', methods=['GET'])
@token_required
def get_contract(current_user, contract_id):
    contract = contracts_collection.find_one({'_id': contract_id})
    
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    contract['id'] = contract['_id']
    
    # Lấy thông tin tenant
    tenant = tenants_collection.find_one({'_id': contract['tenant_id']})
    if tenant:
        contract['tenant_info'] = {
            'id': tenant['_id'],
            'name': tenant['name'],
            'phone': tenant['phone'],
            'id_card': tenant['id_card'],
            'address': tenant['address']
        }
    
    return jsonify(contract), 200

# API Tạo hợp đồng mới
@app.route('/api/contracts', methods=['POST'])
@token_required
@admin_required
def create_contract(current_user):
    data = request.get_json()
    token = request.headers.get('Authorization')
    
    # Validation
    required_fields = ['tenant_id', 'room_id', 'start_date', 'end_date', 'monthly_rent', 'deposit']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Kiểm tra tenant tồn tại
    tenant = tenants_collection.find_one({'_id': data['tenant_id']})
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
    
    # Tạo contract_id tự động
    contract_count = contracts_collection.count_documents({})
    contract_id = f"C{contract_count + 1:04d}"
    
    new_contract = {
        '_id': contract_id,
        'tenant_id': data['tenant_id'],
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
            data['tenant_id'],
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
    token = request.headers.get('Authorization')
    
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
    
    for contract in contracts:
        contract['id'] = contract['_id']
        tenant = tenants_collection.find_one({'_id': contract['tenant_id']})
        if tenant:
            contract['tenant_name'] = tenant['name']
            contract['tenant_phone'] = tenant['phone']
    
    return jsonify({'contracts': contracts, 'total': len(contracts)}), 200

if __name__ == '__main__':
    register_service()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=True)