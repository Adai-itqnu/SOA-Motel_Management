# Room Service - Main Application
# Handles room management operations
from flask import Flask, request, jsonify
from flask_cors import CORS
import atexit
import base64

from config import Config
from model import rooms_collection
from decorators import token_required, admin_required, internal_api_required
from utils import (
    generate_room_id,
    get_timestamp,
    format_room_response,
    check_duplicate_room_name,
    cleanup_expired_reservations
)
from service_registry import register_service, deregister_service

# APScheduler for background jobs
from apscheduler.schedulers.background import BackgroundScheduler


# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Register cleanup on exit
atexit.register(deregister_service)


# ============== Background Scheduler ==============
# Auto cleanup expired reservations every 5 minutes

def scheduled_cleanup_job():
    """Background job to cleanup expired room reservations."""
    try:
        cleaned = cleanup_expired_reservations()
        if cleaned:
            print(f"[Scheduler] Auto-cleaned {len(cleaned)} expired reservations: {cleaned}")
    except Exception as e:
        print(f"[Scheduler] Error during cleanup: {e}")


# Initialize scheduler (only in main process, not in reloader)
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    scheduled_cleanup_job,
    'interval',
    minutes=5,  # Run every 5 minutes
    id='cleanup_expired_reservations',
    replace_existing=True
)


def start_scheduler():
    """Start the background scheduler if not already running."""
    if not scheduler.running:
        scheduler.start()
        print(f"[Scheduler] Started - will cleanup expired reservations every 5 minutes")


# Shutdown scheduler on exit
atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler.running else None)


# ============== Health Check ==============

@app.route('/health', methods=['GET'])
# Health check endpoint
def health_check():
    return jsonify({
        'status': 'healthy',
        'service': Config.SERVICE_NAME,
        'timestamp': get_timestamp()
    }), 200


# ============== Public APIs ==============

@app.route('/api/rooms', methods=['GET'])
# Get list of rooms with optional filters
def get_rooms():
    status_filter = request.args.get('status')
    search = request.args.get('search')
    
    query = {}
    
    if status_filter and status_filter in Config.ALLOWED_STATUSES:
        query['status'] = status_filter
    
    if search:
        query['name'] = {'$regex': search, '$options': 'i'}
    
    rooms = list(rooms_collection.find(query).sort('name', 1))
    
    return jsonify({
        'rooms': [format_room_response(r) for r in rooms],
        'total': len(rooms)
    }), 200


@app.route('/api/rooms/<room_id>', methods=['GET'])
# Get room details by ID
def get_room(room_id):
    room = rooms_collection.find_one({'_id': room_id})
    
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404
    
    return jsonify(format_room_response(room)), 200


@app.route('/api/rooms/available', methods=['GET'])
# Get list of available rooms (for users)
def get_available_rooms():
    rooms = list(rooms_collection.find({
        'status': Config.STATUS_AVAILABLE
    }).sort('price', 1))
    
    # Don't include sensitive data for public endpoint
    return jsonify({
        'rooms': [format_room_response(r, include_sensitive=False) for r in rooms],
        'total': len(rooms)
    }), 200


@app.route('/api/rooms/public/<room_id>', methods=['GET'])
# Get room detail for user UI with full images but no sensitive fields
def get_public_room_detail(room_id):
    room = rooms_collection.find_one({'_id': room_id})
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404

    data = format_room_response(room, include_sensitive=False)
    images = room.get('images') or []
    if not isinstance(images, list):
        images = []
    data['images'] = images
    return jsonify(data), 200


# ============== Admin APIs ==============

@app.route('/api/rooms', methods=['POST'])
@token_required
@admin_required
# Create a new room (admin only)
def create_room(current_user):
    data = request.get_json() or {}
    
    # Validate required fields
    required_fields = ['name', 'price', 'room_type']
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({'message': f"Thiếu trường: {', '.join(missing)}"}), 400
    
    # Check duplicate name
    if check_duplicate_room_name(data['name']):
        return jsonify({'message': 'Tên phòng đã tồn tại!'}), 400
    
    # Create room document
    timestamp = get_timestamp()

    amenities = data.get('amenities') or []
    if isinstance(amenities, str):
        amenities = [a.strip() for a in amenities.split(',') if a.strip()]
    if not isinstance(amenities, list):
        amenities = []

    images = data.get('images') or []
    if not isinstance(images, list):
        images = []
    # Normalize images to a safe structure (base64 string only)
    normalized_images = []
    for img in images:
        if not isinstance(img, dict):
            continue
        content_type = (img.get('content_type') or 'image/jpeg').strip()
        filename = (img.get('filename') or '').strip()
        data_b64 = img.get('data_b64') or img.get('data')
        if not data_b64:
            continue
        # Validate base64 payload (best-effort)
        try:
            base64.b64decode(str(data_b64), validate=True)
        except Exception:
            continue
        normalized_images.append({'filename': filename, 'content_type': content_type, 'data_b64': str(data_b64)})

    new_room = {
        '_id': generate_room_id(),
        'name': data['name'],
        'room_type': data['room_type'],
        'price': float(data['price']),
        'deposit': float(data.get('deposit', 0)),
        'electricity_price': float(data.get('electricity_price') or data.get('electric_price', Config.DEFAULT_ELECTRIC_PRICE)),
        'water_price': float(data.get('water_price', Config.DEFAULT_WATER_PRICE)),
        'description': data.get('description', ''),
        'area': float(data.get('area') or data.get('area_m2', 0) or 0),
        'floor': int(data.get('floor', 1) or 1),
        'amenities': amenities,
        'images': normalized_images,
        'status': Config.STATUS_AVAILABLE,
        'current_contract_id': None,
        'reserved_by_user_id': None,
        'reserved_payment_id': None,
        'reservation_status': None,
        'reserved_at': None,
        'created_at': timestamp,
        'updated_at': timestamp
    }
    
    try:
        rooms_collection.insert_one(new_room)
        return jsonify({
            'message': 'Tạo phòng thành công!',
            'room': format_room_response(new_room)
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo phòng: {str(e)}'}), 500


@app.route('/api/rooms/<room_id>', methods=['PUT'])
@token_required
@admin_required
# Update room information (admin only)
def update_room(current_user, room_id):
    data = request.get_json() or {}
    
    room = rooms_collection.find_one({'_id': room_id})
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404
    
    # Check duplicate name if changing
    if data.get('name') and data['name'] != room['name']:
        if check_duplicate_room_name(data['name'], room_id):
            return jsonify({'message': 'Tên phòng đã tồn tại!'}), 400
    
    # Build update fields
    allowed_fields = [
        'name', 'price', 'status', 'room_type', 'description',
        'deposit', 'electricity_price', 'electric_price', 'water_price', 'current_contract_id',
        'area', 'area_m2', 'floor', 'amenities', 'images'
    ]
    
    update_fields = {}
    for field in allowed_fields:
        if field in data:
            value = data[field]
            # Type conversion
            if field in ['price', 'deposit', 'electricity_price', 'electric_price', 'water_price', 'area', 'area_m2']:
                value = float(value)
            elif field == 'floor':
                value = int(value or 1)
            elif field == 'amenities':
                if isinstance(value, str):
                    value = [a.strip() for a in value.split(',') if a.strip()]
                if not isinstance(value, list):
                    value = []
            elif field == 'images':
                if not isinstance(value, list):
                    value = []
                normalized_images = []
                for img in value:
                    if not isinstance(img, dict):
                        continue
                    content_type = (img.get('content_type') or 'image/jpeg').strip()
                    filename = (img.get('filename') or '').strip()
                    data_b64 = img.get('data_b64') or img.get('data')
                    if not data_b64:
                        continue
                    try:
                        base64.b64decode(str(data_b64), validate=True)
                    except Exception:
                        continue
                    normalized_images.append({'filename': filename, 'content_type': content_type, 'data_b64': str(data_b64)})
                value = normalized_images
            update_fields[field] = value
    
    if not update_fields:
        return jsonify({'message': 'Không có dữ liệu cập nhật!'}), 400
    
    update_fields['updated_at'] = get_timestamp()
    
    try:
        rooms_collection.update_one({'_id': room_id}, {'$set': update_fields})
        updated_room = rooms_collection.find_one({'_id': room_id})
        
        return jsonify({
            'message': 'Cập nhật phòng thành công!',
            'room': format_room_response(updated_room)
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi cập nhật: {str(e)}'}), 500


@app.route('/api/rooms/<room_id>', methods=['DELETE'])
@token_required
@admin_required
# Delete a room (admin only)
def delete_room(current_user, room_id):
    room = rooms_collection.find_one({'_id': room_id})
    
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404
    
    if room.get('status') == Config.STATUS_OCCUPIED:
        return jsonify({'message': 'Không thể xóa phòng đang có người thuê!'}), 400
    
    try:
        rooms_collection.delete_one({'_id': room_id})
        return jsonify({'message': 'Xóa phòng thành công!'}), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi xóa phòng: {str(e)}'}), 500


@app.route('/api/rooms/stats', methods=['GET'])
@token_required
# Get room statistics
def get_room_stats(current_user):
    total = rooms_collection.count_documents({})
    available = rooms_collection.count_documents({'status': Config.STATUS_AVAILABLE})
    occupied = rooms_collection.count_documents({'status': Config.STATUS_OCCUPIED})
    maintenance = rooms_collection.count_documents({'status': Config.STATUS_MAINTENANCE})
    reserved = rooms_collection.count_documents({'status': Config.STATUS_RESERVED})
    
    occupancy_rate = round((occupied / total * 100) if total > 0 else 0, 2)
    
    return jsonify({
        'total': total,
        'available': available,
        'occupied': occupied,
        'maintenance': maintenance,
        'reserved': reserved,
        'occupancy_rate': occupancy_rate
    }), 200


# ============== Internal APIs ==============

@app.route('/internal/rooms/<room_id>/status', methods=['PUT'])
@internal_api_required
# Internal API for other services to update room status
def internal_update_room_status(room_id):
    data = request.get_json() or {}
    new_status = data.get('status')
    
    if new_status not in Config.ALLOWED_STATUSES:
        return jsonify({'message': 'Trạng thái phòng không hợp lệ!'}), 400
    
    update_fields = {
        'status': new_status,
        'updated_at': get_timestamp()
    }
    
    if 'current_contract_id' in data:
        update_fields['current_contract_id'] = data['current_contract_id']
    
    result = rooms_collection.update_one({'_id': room_id}, {'$set': update_fields})
    
    if result.matched_count == 0:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404
    
    return jsonify({
        'message': 'Cập nhật trạng thái phòng thành công!',
        'status': new_status
    }), 200


@app.route('/api/rooms/my-reservations', methods=['GET'])
@token_required
# Get rooms reserved by current user
def get_my_reservations(current_user):
    user_id = current_user.get('user_id') or current_user.get('_id')
    if not user_id:
        return jsonify({'message': 'Không tìm thấy user_id!'}), 400

    rooms = list(
        rooms_collection.find(
            {
                'status': Config.STATUS_RESERVED,
                'reserved_by_user_id': str(user_id),
            }
        ).sort('updated_at', -1)
    )

    return jsonify({'rooms': [format_room_response(r) for r in rooms], 'total': len(rooms)}), 200


@app.route('/internal/rooms/<room_id>/reservation/hold', methods=['PUT'])
@internal_api_required
# Hold a room for reservation while user is paying deposit (internal)
def internal_hold_room_reservation(room_id):
    data = request.get_json() or {}
    user_id = data.get('user_id')
    payment_id = data.get('payment_id')
    if not user_id or not payment_id:
        return jsonify({'message': 'Thiếu user_id hoặc payment_id!'}), 400

    room = rooms_collection.find_one({'_id': room_id})
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404

    if room.get('status') != Config.STATUS_AVAILABLE:
        return jsonify({'message': 'Phòng không còn trống để giữ!'}), 400

    update_fields = {
        'status': Config.STATUS_RESERVED,
        'reserved_by_user_id': str(user_id),
        'reserved_payment_id': str(payment_id),
        'reservation_status': 'pending_payment',
        'reserved_at': get_timestamp(),
        'updated_at': get_timestamp(),
    }

    rooms_collection.update_one({'_id': room_id}, {'$set': update_fields})
    return jsonify({'message': 'Giữ phòng thành công!', 'room_id': room_id, 'status': Config.STATUS_RESERVED}), 200


@app.route('/internal/rooms/<room_id>/reservation/confirm', methods=['PUT'])
@internal_api_required
# Confirm a room reservation after VNPay completed (internal)
# Robust handling: If room wasn't properly held before, we still mark it as reserved
def internal_confirm_room_reservation(room_id):
    data = request.get_json() or {}
    payment_id = data.get('payment_id')
    user_id = data.get('user_id')
    
    if not payment_id:
        return jsonify({'message': 'Thiếu payment_id!'}), 400

    room = rooms_collection.find_one({'_id': room_id})
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404

    # Check if room is already occupied
    if room.get('status') == Config.STATUS_OCCUPIED:
        return jsonify({'message': 'Phòng đã có người thuê!'}), 400
    
    # If room is reserved, verify payment_id matches
    if room.get('status') == Config.STATUS_RESERVED:
        if str(room.get('reserved_payment_id') or '') != str(payment_id):
            # Different payment - room was held by another payment
            return jsonify({'message': 'Phòng đang được giữ bởi giao dịch khác!'}), 400
    
    # Update room to reserved with paid status
    update_fields = {
        'status': Config.STATUS_RESERVED,
        'reservation_status': 'paid',
        'reserved_payment_id': str(payment_id),
        'updated_at': get_timestamp()
    }
    
    # Set user_id if provided
    if user_id:
        update_fields['reserved_by_user_id'] = str(user_id)
    
    rooms_collection.update_one({'_id': room_id}, {'$set': update_fields})
    return jsonify({'message': 'Xác nhận giữ phòng thành công!', 'room_id': room_id}), 200


@app.route('/internal/rooms/<room_id>/reservation/release', methods=['PUT'])
@internal_api_required
# Release a room if VNPay was cancelled/failed (internal)
def internal_release_room_reservation(room_id):
    data = request.get_json() or {}
    payment_id = data.get('payment_id')
    if not payment_id:
        return jsonify({'message': 'Thiếu payment_id!'}), 400

    room = rooms_collection.find_one({'_id': room_id})
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404

    if room.get('status') != Config.STATUS_RESERVED:
        return jsonify({'message': 'Phòng không ở trạng thái giữ!'}), 400
    if str(room.get('reserved_payment_id') or '') != str(payment_id):
        return jsonify({'message': 'payment_id không khớp với phòng đang giữ!'}), 400

    # Only release if still pending payment
    if room.get('reservation_status') != 'pending_payment':
        return jsonify({'message': 'Không thể nhả phòng (đã xác nhận hoặc trạng thái không hợp lệ)!'}), 400

    rooms_collection.update_one(
        {'_id': room_id},
        {
            '$set': {
                'status': Config.STATUS_AVAILABLE,
                'reserved_by_user_id': None,
                'reserved_payment_id': None,
                'reservation_status': None,
                'reserved_at': None,
                'updated_at': get_timestamp(),
            }
        },
    )
    return jsonify({'message': 'Nhả phòng thành công!', 'room_id': room_id, 'status': Config.STATUS_AVAILABLE}), 200


@app.route('/internal/rooms/<room_id>/occupy', methods=['PUT'])
@internal_api_required
# Mark a reserved room as occupied after admin creates a contract (internal)
def internal_occupy_room(room_id):
    data = request.get_json() or {}
    user_id = data.get('user_id')
    contract_id = data.get('contract_id')

    if not user_id or not contract_id:
        return jsonify({'message': 'Thiếu user_id hoặc contract_id!'}), 400

    room = rooms_collection.find_one({'_id': room_id})
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404

    if room.get('status') != Config.STATUS_RESERVED:
        return jsonify({'message': 'Phòng không ở trạng thái giữ!'}), 400

    # A user can occupy only one room at a time
    existing = rooms_collection.find_one({
        'current_user_id': str(user_id),
        'status': Config.STATUS_OCCUPIED,
        '_id': {'$ne': room_id}
    })
    if existing:
        return jsonify({'message': 'Người thuê đã có phòng khác đang thuê!'}), 400

    # Only allow occupying if reservation was confirmed.
    if str(room.get('reservation_status') or '') not in ['paid']:
        return jsonify({'message': 'Phòng chưa được xác nhận cọc (reservation_status != paid)!'}), 400

    update_fields = {
        'status': Config.STATUS_OCCUPIED,
        'current_contract_id': str(contract_id),
        'current_user_id': str(user_id),
        'reserved_by_user_id': None,
        'reserved_payment_id': None,
        'reservation_status': None,
        'reserved_at': None,
        'updated_at': get_timestamp(),
    }

    rooms_collection.update_one({'_id': room_id}, {'$set': update_fields})
    return jsonify({'message': 'Gán hợp đồng và chuyển phòng sang đang thuê thành công!', 'room_id': room_id}), 200


@app.route('/internal/rooms/<room_id>/vacate', methods=['PUT'])
@internal_api_required
# Vacate a room when contract is terminated (internal)
def internal_vacate_room(room_id):
    room = rooms_collection.find_one({'_id': room_id})
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404

    data = request.get_json() or {}
    contract_id = str(data.get('contract_id') or '')

    # If the room is linked to a different contract, block vacate to avoid race.
    if room.get('current_contract_id') and contract_id and room.get('current_contract_id') != contract_id:
        return jsonify({'message': 'Phòng đang gán với hợp đồng khác, không thể nhả!'}), 400

    update_fields = {
        'status': Config.STATUS_AVAILABLE,
        'current_contract_id': None,
        'current_user_id': None,
        'reserved_by_user_id': None,
        'reserved_payment_id': None,
        'reservation_status': None,
        'reserved_at': None,
        'updated_at': get_timestamp(),
    }

    rooms_collection.update_one({'_id': room_id}, {'$set': update_fields})
    return jsonify({'message': 'Đã nhả phòng, phòng trở lại trạng thái trống.', 'room_id': room_id, 'status': Config.STATUS_AVAILABLE}), 200


# ============== Reservation Cleanup APIs ==============

@app.route('/internal/rooms/reservations/cleanup', methods=['POST'])
@internal_api_required
# Internal API for scheduled jobs to cleanup expired reservations
def internal_cleanup_expired_reservations():
    data = request.get_json() or {}
    timeout_minutes = data.get('timeout_minutes')
    
    cleaned_room_ids = cleanup_expired_reservations(timeout_minutes)
    
    return jsonify({
        'message': f'Đã cleanup {len(cleaned_room_ids)} phòng hết hạn giữ chỗ.',
        'cleaned_rooms': cleaned_room_ids,
        'count': len(cleaned_room_ids)
    }), 200


@app.route('/api/rooms/reservations/cleanup', methods=['POST'])
@token_required
@admin_required
# Admin API to manually trigger cleanup of expired reservations
def admin_cleanup_expired_reservations(current_user):
    data = request.get_json() or {}
    timeout_minutes = data.get('timeout_minutes')
    
    cleaned_room_ids = cleanup_expired_reservations(timeout_minutes)
    
    if len(cleaned_room_ids) == 0:
        return jsonify({
            'message': 'Không có phòng nào cần cleanup.',
            'cleaned_rooms': [],
            'count': 0
        }), 200
    
    return jsonify({
        'message': f'Đã cleanup {len(cleaned_room_ids)} phòng hết hạn giữ chỗ.',
        'cleaned_rooms': cleaned_room_ids,
        'count': len(cleaned_room_ids)
    }), 200


# ============== Application Entry Point ==============

if __name__ == '__main__':
    import os
    
    print(f"\n{'='*50}")
    print(f"  {Config.SERVICE_NAME.upper()}")
    print(f"  Port: {Config.SERVICE_PORT}")
    print(f"  Debug: {Config.DEBUG}")
    print(f"  Reservation Timeout: {Config.RESERVATION_TIMEOUT_MINUTES} minutes")
    print(f"{'='*50}\n")
    
    register_service()
    
    # Start scheduler (avoid duplicate in Flask reloader)
    # WERKZEUG_RUN_MAIN is set by Flask when running the actual server (not reloader)
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not Config.DEBUG:
        start_scheduler()
    
    app.run(
        host='0.0.0.0',
        port=Config.SERVICE_PORT,
        debug=Config.DEBUG
    )