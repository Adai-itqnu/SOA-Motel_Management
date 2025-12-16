"""Contract Service - Main Application"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import uuid
import requests
import atexit
from config import Config
from model import contracts_collection
from decorators import token_required, admin_required, internal_api_required
from service_registry import register_service, deregister_service
from services import get_service_url

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
atexit.register(deregister_service)


def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


def generate_contract_id():
    return f"CTR{uuid.uuid4().hex[:8].upper()}"


def format_contract(contract):
    return {
        '_id': contract['_id'],
        'room_id': contract.get('room_id', ''),
        'user_id': contract.get('user_id', ''),
        'start_date': contract.get('start_date', ''),
        'end_date': contract.get('end_date', ''),
        'monthly_rent': contract.get('monthly_rent', 0),
        'deposit_amount': contract.get('deposit_amount', 0),
        'deposit_status': contract.get('deposit_status', 'pending'),
        'payment_day': contract.get('payment_day', 5),
        'status': contract.get('status', 'active'),
        'notes': contract.get('notes', ''),
        'created_at': contract.get('created_at'),
        'updated_at': contract.get('updated_at')
    }


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': Config.SERVICE_NAME}), 200


# ============== Internal API (service-to-service) ==============

@app.route('/internal/contracts', methods=['GET'])
@internal_api_required
def get_contracts_internal():
    """Get all contracts (for internal service calls like bill-service)"""
    query = {}
    
    if request.args.get('status'):
        query['status'] = request.args.get('status')
    if request.args.get('room_id'):
        query['room_id'] = request.args.get('room_id')
    
    contracts = list(contracts_collection.find(query).sort('created_at', -1))
    
    return jsonify({
        'contracts': [format_contract(c) for c in contracts],
        'total': len(contracts)
    }), 200


# ============== External API (JWT required) ==============

@app.route('/api/contracts', methods=['GET'])
@token_required
def get_contracts(current_user):
    """Get contracts list (admin sees all, user sees own)"""
    user_id = current_user.get('user_id') or current_user.get('_id')
    role = current_user.get('role', '')
    
    query = {} if role == 'admin' else {'user_id': user_id}
    
    if request.args.get('status'):
        query['status'] = request.args.get('status')
    if request.args.get('room_id'):
        query['room_id'] = request.args.get('room_id')
    
    contracts = list(contracts_collection.find(query).sort('created_at', -1))
    
    return jsonify({
        'contracts': [format_contract(c) for c in contracts],
        'total': len(contracts)
    }), 200


@app.route('/api/contracts/<contract_id>', methods=['GET'])
@token_required
def get_contract(current_user, contract_id):
    """Get single contract details"""
    contract = contracts_collection.find_one({'_id': contract_id})
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    user_id = current_user.get('user_id') or current_user.get('_id')
    role = current_user.get('role', '')
    
    if role != 'admin' and contract['user_id'] != user_id:
        return jsonify({'message': 'Không có quyền xem hợp đồng này!'}), 403
    
    return jsonify(format_contract(contract)), 200


@app.route('/api/contracts', methods=['POST'])
@token_required
@admin_required
def create_contract(current_user):
    """Create a new contract (admin only)"""
    data = request.get_json() or {}
    
    required = ['user_id', 'room_id', 'start_date', 'end_date', 'monthly_rent', 'deposit_amount']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400

    # Enforce: one active contract per user
    existing_active = contracts_collection.find_one({
        'user_id': data['user_id'],
        'status': 'active'
    })
    if existing_active:
        return jsonify({'message': 'Người dùng đã có hợp đồng đang hoạt động, không thể tạo thêm!'}), 400
    
    # Validate dates
    try:
        start = datetime.datetime.fromisoformat(data['start_date'])
        end = datetime.datetime.fromisoformat(data['end_date'])
        if end <= start:
            return jsonify({'message': 'Ngày kết thúc phải sau ngày bắt đầu!'}), 400
    except:
        return jsonify({'message': 'Định dạng ngày không hợp lệ (YYYY-MM-DD)!'}), 400
    
    timestamp = get_timestamp()
    contract_id = generate_contract_id()
    
    new_contract = {
        '_id': contract_id,
        'room_id': data['room_id'],
        'user_id': data['user_id'],
        'start_date': data['start_date'],
        'end_date': data['end_date'],
        'monthly_rent': float(data['monthly_rent']),
        'deposit_amount': float(data['deposit_amount']),
        'deposit_status': data.get('deposit_status', 'paid'),
        'payment_day': int(data.get('payment_day', 5)),
        'status': 'active',
        'notes': data.get('notes', ''),
        'created_at': timestamp,
        'updated_at': timestamp
    }
    
    try:
        contracts_collection.insert_one(new_contract)
        return jsonify({
            'message': 'Tạo hợp đồng thành công!',
            'contract': format_contract(new_contract)
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi: {str(e)}'}), 500


@app.route('/api/contracts/from-reservation', methods=['POST'])
@token_required
@admin_required
def create_contract_from_reservation(current_user):
    """Create a contract by attaching the tenant who already paid room deposit (admin only)."""
    data = request.get_json() or {}
    room_id = data.get('room_id')
    if not room_id:
        return jsonify({'message': 'Thiếu room_id!'}), 400

    # One active contract per user guard
    tenant_user_id = data.get('user_id')
    if tenant_user_id:
        existing_active = contracts_collection.find_one({
            'user_id': tenant_user_id,
            'status': 'active'
        })
        if existing_active:
            return jsonify({'message': 'Người dùng đã có hợp đồng đang hoạt động, không thể tạo thêm!'}), 400

    # Required by contract model
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    monthly_rent = data.get('monthly_rent')

    if not start_date or not end_date or monthly_rent is None:
        return jsonify({'message': 'Thiếu start_date, end_date hoặc monthly_rent!'}), 400

    # Validate dates
    try:
        start = datetime.datetime.fromisoformat(start_date)
        end = datetime.datetime.fromisoformat(end_date)
        if end <= start:
            return jsonify({'message': 'Ngày kết thúc phải sau ngày bắt đầu!'}), 400
    except Exception:
        return jsonify({'message': 'Định dạng ngày không hợp lệ (YYYY-MM-DD)!'}), 400

    room_service_url = get_service_url('room-service')
    if not room_service_url:
        return jsonify({'message': 'Không thể kết nối room-service!'}), 503

    # Fetch room to get reserved tenant
    auth_header = request.headers.get('Authorization') or request.headers.get('authorization')
    try:
        resp = requests.get(
            f"{room_service_url}/api/rooms/{room_id}",
            headers={'Authorization': auth_header} if auth_header else {},
            timeout=8,
        )
    except Exception as e:
        return jsonify({'message': f'Lỗi gọi room-service: {str(e)}'}), 503

    if not resp.ok:
        return jsonify({'message': 'Không tìm thấy phòng hoặc không thể lấy thông tin phòng!'}), 404

    room = resp.json() or {}
    if room.get('status') != 'reserved':
        return jsonify({'message': 'Phòng không ở trạng thái giữ (reserved)!'}), 400

    if (room.get('reservation_status') or '') != 'paid':
        return jsonify({'message': 'Phòng chưa được xác nhận cọc (reservation_status != paid)!'}), 400

    tenant_id = room.get('reserved_by_tenant_id')
    if not tenant_id:
        return jsonify({'message': 'Phòng chưa có người giữ (reserved_by_tenant_id)!'}), 400

    # Prefer room deposit; allow override from request
    deposit_amount = data.get('deposit_amount')
    if deposit_amount is None:
        deposit_amount = room.get('deposit', 0)

    timestamp = get_timestamp()
    contract_id = generate_contract_id()
    new_contract = {
        '_id': contract_id,
        'room_id': room_id,
        'user_id': str(tenant_id),
        'start_date': start_date,
        'end_date': end_date,
        'monthly_rent': float(monthly_rent),
        'deposit_amount': float(deposit_amount),
        'deposit_status': 'paid',
        'payment_day': int(data.get('payment_day', 5)),
        'status': 'active',
        'notes': data.get('notes', ''),
        'created_at': timestamp,
        'updated_at': timestamp,
    }

    try:
        contracts_collection.insert_one(new_contract)
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo hợp đồng: {str(e)}'}), 500

    # Occupy the room via internal API key (service-to-service)
    try:
        occ = requests.put(
            f"{room_service_url}/internal/rooms/{room_id}/occupy",
            json={'tenant_id': str(tenant_id), 'contract_id': contract_id},
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=8,
        )
        if not occ.ok:
            # Rollback contract if room transition fails
            contracts_collection.delete_one({'_id': contract_id})
            return jsonify({'message': f"Không thể cập nhật trạng thái phòng: {occ.text}"}), 502
    except Exception as e:
        contracts_collection.delete_one({'_id': contract_id})
        return jsonify({'message': f'Lỗi cập nhật phòng: {str(e)}'}), 502

    return jsonify({'message': 'Tạo hợp đồng thành công!', 'contract': format_contract(new_contract)}), 201


@app.route('/api/contracts/<contract_id>', methods=['PUT'])
@token_required
@admin_required
def update_contract(current_user, contract_id):
    """Update contract (admin only)"""
    contract = contracts_collection.find_one({'_id': contract_id})
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    data = request.get_json() or {}
    
    allowed = ['monthly_rent', 'deposit_amount', 'deposit_status', 'payment_day', 'notes']
    update_fields = {k: data[k] for k in allowed if k in data}
    
    if not update_fields:
        return jsonify({'message': 'Không có dữ liệu cập nhật!'}), 400
    
    update_fields['updated_at'] = get_timestamp()
    
    contracts_collection.update_one({'_id': contract_id}, {'$set': update_fields})
    updated = contracts_collection.find_one({'_id': contract_id})
    
    return jsonify({
        'message': 'Cập nhật hợp đồng thành công!',
        'contract': format_contract(updated)
    }), 200


@app.route('/api/contracts/<contract_id>/terminate', methods=['PUT'])
@token_required
@admin_required
def terminate_contract(current_user, contract_id):
    """Terminate contract (admin only)"""
    contract = contracts_collection.find_one({'_id': contract_id})
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    if contract['status'] != 'active':
        return jsonify({'message': 'Hợp đồng đã kết thúc!'}), 400
    
    contracts_collection.update_one(
        {'_id': contract_id},
        {'$set': {
            'status': 'terminated',
            'updated_at': get_timestamp()
        }}
    )

    # Vacate room so it becomes available again
    room_service_url = get_service_url('room-service')
    if room_service_url:
        try:
            requests.put(
                f"{room_service_url}/internal/rooms/{contract['room_id']}/vacate",
                json={'contract_id': contract_id},
                headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
                timeout=8,
            )
        except Exception:
            pass

    return jsonify({'message': 'Kết thúc hợp đồng thành công!'}), 200


@app.route('/api/contracts/<contract_id>/extend', methods=['PUT'])
@token_required
@admin_required
def extend_contract(current_user, contract_id):
    """Extend contract end date (admin only)"""
    data = request.get_json() or {}
    
    if 'new_end_date' not in data:
        return jsonify({'message': 'Thiếu ngày kết thúc mới!'}), 400
    
    contract = contracts_collection.find_one({'_id': contract_id})
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    if contract['status'] != 'active':
        return jsonify({'message': 'Hợp đồng đã kết thúc!'}), 400
    
    try:
        new_end = datetime.datetime.fromisoformat(data['new_end_date'])
        old_end = datetime.datetime.fromisoformat(contract['end_date'])
        if new_end <= old_end:
            return jsonify({'message': 'Ngày mới phải sau ngày hiện tại!'}), 400
    except:
        return jsonify({'message': 'Định dạng ngày không hợp lệ!'}), 400
    
    contracts_collection.update_one(
        {'_id': contract_id},
        {'$set': {
            'end_date': data['new_end_date'],
            'updated_at': get_timestamp()
        }}
    )
    
    return jsonify({'message': 'Gia hạn hợp đồng thành công!'}), 200


@app.route('/api/contracts/room/<room_id>', methods=['GET'])
@token_required
def get_contracts_by_room(current_user, room_id):
    """Get all contracts for a room"""
    contracts = list(contracts_collection.find({'room_id': room_id}).sort('created_at', -1))
    return jsonify({
        'contracts': [format_contract(c) for c in contracts],
        'total': len(contracts)
    }), 200


@app.route('/api/contracts/user/<user_id>', methods=['GET'])
@token_required
def get_contracts_by_user(current_user, user_id):
    """Get all contracts for a user"""
    current_user_id = current_user.get('user_id') or current_user.get('_id')
    role = current_user.get('role', '')
    
    # Only admin or the user themselves can view
    if role != 'admin' and current_user_id != user_id:
        return jsonify({'message': 'Không có quyền!'}), 403
    
    contracts = list(contracts_collection.find({'user_id': user_id}).sort('created_at', -1))
    return jsonify({
        'contracts': [format_contract(c) for c in contracts],
        'total': len(contracts)
    }), 200


# ============== Internal API (Service-to-Service) ==============

from decorators import internal_api_required

@app.route('/internal/contracts/auto-create', methods=['POST'])
@internal_api_required
def auto_create_contract():
    """Auto-create contract from paid room reservation (called by payment-service)"""
    data = request.get_json() or {}
    room_id = data.get('room_id')
    tenant_id = data.get('tenant_id')
    payment_id = data.get('payment_id')
    check_in_date = data.get('check_in_date')  # From booking

    if not room_id or not tenant_id:
        return jsonify({'message': 'Missing room_id or tenant_id'}), 400

    # Check if contract already exists for this room or tenant (one active per tenant)
    existing = contracts_collection.find_one({
        'room_id': room_id,
        'user_id': str(tenant_id),
        'status': 'active'
    })
    if existing:
        return jsonify({'message': 'Contract already exists', 'contract': format_contract(existing)}), 200

    existing_for_tenant = contracts_collection.find_one({
        'user_id': str(tenant_id),
        'status': 'active'
    })
    if existing_for_tenant:
        return jsonify({'message': 'Tenant already has an active contract'}), 400

    # Get room info for price
    room_service_url = get_service_url('room-service')
    if not room_service_url:
        return jsonify({'message': 'Cannot connect to room-service'}), 503

    try:
        resp = requests.get(
            f"{room_service_url}/api/rooms/{room_id}",
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=8,
        )
    except Exception as e:
        return jsonify({'message': f'Error calling room-service: {str(e)}'}), 503

    if not resp.ok:
        return jsonify({'message': 'Room not found'}), 404

    room = resp.json() or {}

    # Calculate dates
    if check_in_date:
        try:
            start = datetime.datetime.fromisoformat(check_in_date)
        except:
            start = datetime.datetime.utcnow()
    else:
        start = datetime.datetime.utcnow()
    
    # Contract for 12 months by default
    end = start + datetime.timedelta(days=365)

    timestamp = get_timestamp()
    contract_id = generate_contract_id()
    
    new_contract = {
        '_id': contract_id,
        'room_id': room_id,
        'user_id': str(tenant_id),
        'start_date': start.strftime('%Y-%m-%d'),
        'end_date': end.strftime('%Y-%m-%d'),
        'monthly_rent': float(room.get('price', 0)),
        'deposit_amount': float(room.get('deposit', 0)),
        'deposit_status': 'paid',
        'deposit_payment_id': payment_id,
        'payment_day': 5,  # Default: 5th of each month
        'status': 'active',
        'notes': 'Hợp đồng tự động tạo sau thanh toán cọc thành công',
        'created_at': timestamp,
        'updated_at': timestamp,
    }

    try:
        contracts_collection.insert_one(new_contract)
    except Exception as e:
        return jsonify({'message': f'Error creating contract: {str(e)}'}), 500

    # Occupy the room
    try:
        occ = requests.put(
            f"{room_service_url}/internal/rooms/{room_id}/occupy",
            json={'tenant_id': str(tenant_id), 'contract_id': contract_id},
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=8,
        )
        if not occ.ok:
            print(f"Warning: Failed to occupy room: {occ.text}")
    except Exception as e:
        print(f"Warning: Error occupying room: {e}")

    print(f"Auto-created contract {contract_id} for room {room_id}, tenant {tenant_id}")
    return jsonify({'message': 'Contract created', 'contract': format_contract(new_contract)}), 201


if __name__ == '__main__':
    print(f"\n{'='*50}\n  {Config.SERVICE_NAME.upper()}\n  Port: {Config.SERVICE_PORT}\n{'='*50}\n")
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)

