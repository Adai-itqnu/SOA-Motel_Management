# Contract Service - Main Application
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import atexit

from config import Config
from model import contracts_collection
from decorators import token_required, admin_required, internal_api_required
from service_registry import register_service, deregister_service
from services import get_service_url
from utils import (
    get_timestamp,
    generate_contract_id,
    get_user_id,
    can_access_contract,
    format_contract,
    validate_contract_dates,
    check_existing_active_contract,
    check_contract_exists,
    create_contract_document,
    create_auto_contract_document
)


app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
atexit.register(deregister_service)


# ============== Health Check ==============

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': Config.SERVICE_NAME}), 200


# ============== Internal API (service-to-service) ==============

@app.route('/internal/contracts', methods=['GET'])
@internal_api_required
# Get all contracts (for internal service calls like bill-service)
def get_contracts_internal():
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
# Get contracts list (admin sees all, user sees own)
def get_contracts(current_user):
    user_id = get_user_id(current_user)
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
# Get single contract details
def get_contract(current_user, contract_id):
    contract = contracts_collection.find_one({'_id': contract_id})
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    if not can_access_contract(current_user, contract):
        return jsonify({'message': 'Không có quyền xem hợp đồng này!'}), 403
    
    return jsonify(format_contract(contract)), 200


@app.route('/api/contracts', methods=['POST'])
@token_required
@admin_required
# Create a new contract (admin only)
def create_contract(current_user):
    data = request.get_json() or {}
    
    required = ['user_id', 'room_id', 'start_date', 'end_date', 'monthly_rent', 'deposit_amount']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400

    # Check one active contract per user
    if check_existing_active_contract(data['user_id']):
        return jsonify({'message': 'Người dùng đã có hợp đồng đang hoạt động!'}), 400
    
    # Validate dates
    start, end, error = validate_contract_dates(data['start_date'], data['end_date'])
    if error:
        return jsonify({'message': error}), 400
    
    new_contract = create_contract_document(data, data['user_id'])
    
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
# Create a contract from room reservation (admin only)
def create_contract_from_reservation(current_user):
    data = request.get_json() or {}
    room_id = data.get('room_id')
    if not room_id:
        return jsonify({'message': 'Thiếu room_id!'}), 400

    # Check one active contract per user
    user_user_id = data.get('user_id')
    if user_user_id and check_existing_active_contract(user_user_id):
        return jsonify({'message': 'Người dùng đã có hợp đồng đang hoạt động!'}), 400

    # Validate required fields
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    monthly_rent = data.get('monthly_rent')

    if not start_date or not end_date or monthly_rent is None:
        return jsonify({'message': 'Thiếu start_date, end_date hoặc monthly_rent!'}), 400

    # Validate dates
    start, end, error = validate_contract_dates(start_date, end_date)
    if error:
        return jsonify({'message': error}), 400

    room_service_url = get_service_url('room-service')
    if not room_service_url:
        return jsonify({'message': 'Không thể kết nối room-service!'}), 503

    # Fetch room info
    auth_header = request.headers.get('Authorization')
    try:
        resp = requests.get(
            f"{room_service_url}/api/rooms/{room_id}",
            headers={'Authorization': auth_header} if auth_header else {},
            timeout=8,
        )
    except Exception as e:
        return jsonify({'message': f'Lỗi gọi room-service: {str(e)}'}), 503

    if not resp.ok:
        return jsonify({'message': 'Không tìm thấy phòng!'}), 404

    room = resp.json() or {}
    if room.get('status') != 'reserved':
        return jsonify({'message': 'Phòng không ở trạng thái giữ (reserved)!'}), 400

    if (room.get('reservation_status') or '') != 'paid':
        return jsonify({'message': 'Phòng chưa được xác nhận cọc!'}), 400

    user_id = room.get('reserved_by_user_id')
    if not user_id:
        return jsonify({'message': 'Phòng chưa có người giữ!'}), 400

    deposit_amount = data.get('deposit_amount') or room.get('deposit', 0)

    timestamp = get_timestamp()
    contract_id = generate_contract_id()
    new_contract = {
        '_id': contract_id,
        'room_id': room_id,
        'user_id': str(user_id),
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

    # Occupy the room
    try:
        occ = requests.put(
            f"{room_service_url}/internal/rooms/{room_id}/occupy",
            json={'user_id': str(user_id), 'contract_id': contract_id},
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=8,
        )
        if not occ.ok:
            contracts_collection.delete_one({'_id': contract_id})
            return jsonify({'message': f"Không thể cập nhật phòng: {occ.text}"}), 502
    except Exception as e:
        contracts_collection.delete_one({'_id': contract_id})
        return jsonify({'message': f'Lỗi cập nhật phòng: {str(e)}'}), 502

    return jsonify({'message': 'Tạo hợp đồng thành công!', 'contract': format_contract(new_contract)}), 201


@app.route('/api/contracts/<contract_id>', methods=['PUT'])
@token_required
@admin_required
# Update contract (admin only)
def update_contract(current_user, contract_id):
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
# Terminate contract (admin only)
def terminate_contract(current_user, contract_id):
    contract = contracts_collection.find_one({'_id': contract_id})
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    if contract['status'] != 'active':
        return jsonify({'message': 'Hợp đồng đã kết thúc!'}), 400
    
    contracts_collection.update_one(
        {'_id': contract_id},
        {'$set': {'status': 'terminated', 'updated_at': get_timestamp()}}
    )

    # Vacate room
    room_service_url = get_service_url('room-service')
    if room_service_url:
        try:
            requests.put(
                f"{room_service_url}/internal/rooms/{contract['room_id']}/vacate",
                json={'contract_id': contract_id},
                headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
                timeout=8,
            )
        except:
            pass

    return jsonify({'message': 'Kết thúc hợp đồng thành công!'}), 200


@app.route('/api/contracts/<contract_id>/extend', methods=['PUT'])
@token_required
@admin_required
# Extend contract end date (admin only)
def extend_contract(current_user, contract_id):
    data = request.get_json() or {}
    
    if 'new_end_date' not in data:
        return jsonify({'message': 'Thiếu ngày kết thúc mới!'}), 400
    
    contract = contracts_collection.find_one({'_id': contract_id})
    if not contract:
        return jsonify({'message': 'Hợp đồng không tồn tại!'}), 404
    
    if contract['status'] != 'active':
        return jsonify({'message': 'Hợp đồng đã kết thúc!'}), 400
    
    _, _, error = validate_contract_dates(contract['end_date'], data['new_end_date'])
    if error:
        return jsonify({'message': 'Ngày mới phải sau ngày hiện tại!'}), 400
    
    contracts_collection.update_one(
        {'_id': contract_id},
        {'$set': {'end_date': data['new_end_date'], 'updated_at': get_timestamp()}}
    )
    
    return jsonify({'message': 'Gia hạn hợp đồng thành công!'}), 200


@app.route('/api/contracts/room/<room_id>', methods=['GET'])
@token_required
# Get all contracts for a room
def get_contracts_by_room(current_user, room_id):
    contracts = list(contracts_collection.find({'room_id': room_id}).sort('created_at', -1))
    return jsonify({
        'contracts': [format_contract(c) for c in contracts],
        'total': len(contracts)
    }), 200


@app.route('/api/contracts/user/<user_id>', methods=['GET'])
@token_required
# Get all contracts for a user
def get_contracts_by_user(current_user, user_id):
    current_user_id = get_user_id(current_user)
    role = current_user.get('role', '')
    
    if role != 'admin' and current_user_id != user_id:
        return jsonify({'message': 'Không có quyền!'}), 403
    
    contracts = list(contracts_collection.find({'user_id': user_id}).sort('created_at', -1))
    return jsonify({
        'contracts': [format_contract(c) for c in contracts],
        'total': len(contracts)
    }), 200


# ============== Internal API (Service-to-Service) ==============

@app.route('/internal/contracts/auto-create', methods=['POST'])
@internal_api_required
# Auto-create contract from paid room reservation
def auto_create_contract():
    data = request.get_json() or {}
    room_id = data.get('room_id')
    user_id = data.get('user_id')
    payment_id = data.get('payment_id')
    check_in_date = data.get('check_in_date')

    if not room_id or not user_id:
        return jsonify({'message': 'Missing room_id or user_id'}), 400

    # Check existing contract
    existing = check_contract_exists(room_id, user_id)
    if existing:
        return jsonify({'message': 'Contract already exists', 'contract': format_contract(existing)}), 200

    if check_existing_active_contract(str(user_id)):
        return jsonify({'message': 'User already has an active contract'}), 400

    # Get room info
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

    # Create contract
    new_contract = create_auto_contract_document(room_id, user_id, room, payment_id, check_in_date)

    try:
        contracts_collection.insert_one(new_contract)
    except Exception as e:
        return jsonify({'message': f'Error creating contract: {str(e)}'}), 500

    # Occupy the room
    try:
        occ = requests.put(
            f"{room_service_url}/internal/rooms/{room_id}/occupy",
            json={'user_id': str(user_id), 'contract_id': new_contract['_id']},
            headers={'X-Internal-Api-Key': Config.INTERNAL_API_KEY},
            timeout=8,
        )
        if not occ.ok:
            print(f"Warning: Failed to occupy room: {occ.text}")
    except Exception as e:
        print(f"Warning: Error occupying room: {e}")

    print(f"Auto-created contract {new_contract['_id']} for room {room_id}, user {user_id}")
    return jsonify({'message': 'Contract created', 'contract': format_contract(new_contract)}), 201


# ============== Entry Point ==============

if __name__ == '__main__':
    print(f"\n{'='*50}\n  {Config.SERVICE_NAME.upper()}\n  Port: {Config.SERVICE_PORT}\n{'='*50}\n")
    register_service()
    app.run(host='0.0.0.0', port=Config.SERVICE_PORT, debug=Config.DEBUG)
