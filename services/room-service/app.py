from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import jwt
from functools import wraps
from config import JWT_SECRET, SERVICE_NAME, SERVICE_PORT
from model import rooms_collection
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

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': app.config['SERVICE_NAME']}), 200

# API Lấy danh sách phòng
@app.route('/api/rooms', methods=['GET'])
def get_rooms():
    status_filter = request.args.get('status')
    search = request.args.get('search')
    
    query = {}
    
    # Filter theo status
    if status_filter:
        query['status'] = status_filter
    
    # Search theo tên phòng
    if search:
        query['name'] = {'$regex': search, '$options': 'i'}
    
    rooms = list(rooms_collection.find(query).sort('name', 1))
    
    # Convert ObjectId
    for room in rooms:
        room['id'] = room['_id']
    
    return jsonify({'rooms': rooms, 'total': len(rooms)}), 200

# API Lấy chi tiết phòng
@app.route('/api/rooms/<room_id>', methods=['GET'])
def get_room(room_id):
    room = rooms_collection.find_one({'_id': room_id})
    
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404
    
    room['id'] = room['_id']
    return jsonify(room), 200

# API Tạo phòng mới (Admin only)
@app.route('/api/rooms', methods=['POST'])
@token_required
@admin_required
def create_room(current_user):
    data = request.get_json()
    
    # Validation
    required_fields = ['name', 'price', 'room_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Kiểm tra tên phòng đã tồn tại
    if rooms_collection.find_one({'name': data['name']}):
        return jsonify({'message': 'Tên phòng đã tồn tại!'}), 400
    
    # Tạo room_id tự động
    room_count = rooms_collection.count_documents({})
    room_id = f"R{room_count + 1:03d}"
    
    # Tạo phòng mới
    new_room = {
        '_id': room_id,
        'name': data['name'],
        'price': float(data['price']),
        'status': 'available',  # available | occupied | maintenance
        'tenant_id': None,
        'electric_meter': data.get('electric_meter', 0),
        'water_meter': data.get('water_meter', 0),
        'room_type': data['room_type'],
        'description': data.get('description', ''),
        'created_at': datetime.datetime.utcnow().isoformat(),
        'updated_at': datetime.datetime.utcnow().isoformat()
    }
    
    try:
        rooms_collection.insert_one(new_room)
        new_room['id'] = new_room['_id']
        return jsonify({
            'message': 'Tạo phòng thành công!',
            'room': new_room
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo phòng: {str(e)}'}), 500

# API Cập nhật phòng (Admin only)
@app.route('/api/rooms/<room_id>', methods=['PUT'])
@token_required
@admin_required
def update_room(current_user, room_id):
    data = request.get_json()
    
    room = rooms_collection.find_one({'_id': room_id})
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404
    
    # Kiểm tra tên phòng trùng (nếu đổi tên)
    if 'name' in data and data['name'] != room['name']:
        if rooms_collection.find_one({'name': data['name']}):
            return jsonify({'message': 'Tên phòng đã tồn tại!'}), 400
    
    # Cập nhật các trường
    update_fields = {}
    allowed_fields = ['name', 'price', 'status', 'electric_meter', 'water_meter', 
                     'room_type', 'description', 'tenant_id']
    
    for field in allowed_fields:
        if field in data:
            update_fields[field] = data[field]
    
    update_fields['updated_at'] = datetime.datetime.utcnow().isoformat()
    
    try:
        rooms_collection.update_one(
            {'_id': room_id},
            {'$set': update_fields}
        )
        
        updated_room = rooms_collection.find_one({'_id': room_id})
        updated_room['id'] = updated_room['_id']
        
        return jsonify({
            'message': 'Cập nhật phòng thành công!',
            'room': updated_room
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi cập nhật: {str(e)}'}), 500

# API Xóa phòng (Admin only)
@app.route('/api/rooms/<room_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_room(current_user, room_id):
    room = rooms_collection.find_one({'_id': room_id})
    
    if not room:
        return jsonify({'message': 'Phòng không tồn tại!'}), 404
    
    # Không cho xóa phòng đang có người thuê
    if room['status'] == 'occupied':
        return jsonify({'message': 'Không thể xóa phòng đang có người thuê!'}), 400
    
    try:
        rooms_collection.delete_one({'_id': room_id})
        return jsonify({'message': 'Xóa phòng thành công!'}), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi xóa phòng: {str(e)}'}), 500

# API Lấy thống kê phòng
@app.route('/api/rooms/stats', methods=['GET'])
@token_required
def get_room_stats(current_user):
    total_rooms = rooms_collection.count_documents({})
    available_rooms = rooms_collection.count_documents({'status': 'available'})
    occupied_rooms = rooms_collection.count_documents({'status': 'occupied'})
    maintenance_rooms = rooms_collection.count_documents({'status': 'maintenance'})
    
    return jsonify({
        'total': total_rooms,
        'available': available_rooms,
        'occupied': occupied_rooms,
        'maintenance': maintenance_rooms,
        'occupancy_rate': round((occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0, 2)
    }), 200

# API Lấy danh sách phòng trống (cho user)
@app.route('/api/rooms/available', methods=['GET'])
def get_available_rooms():
    rooms = list(rooms_collection.find({'status': 'available'}).sort('price', 1))
    
    for room in rooms:
        room['id'] = room['_id']
        # Ẩn một số thông tin nhạy cảm với user
        room.pop('tenant_id', None)
        room.pop('electric_meter', None)
        room.pop('water_meter', None)
    
    return jsonify({'rooms': rooms, 'total': len(rooms)}), 200

if __name__ == '__main__':
    register_service()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=True)