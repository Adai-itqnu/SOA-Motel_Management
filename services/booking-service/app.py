from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import jwt
from functools import wraps
import requests
from bson import ObjectId
from config import JWT_SECRET, SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT
from model import bookings_collection
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

# Helper function: Create contract via contract-service
def create_contract_via_service(contract_data, token):
    """Create contract via contract-service"""
    try:
        contract_service_url = get_service_url('contract-service')
        if not contract_service_url:
            return None, "Không thể kết nối tới Contract Service"
        
        # Ensure token has Bearer prefix
        if token and not token.startswith('Bearer ') and not token.startswith('bearer '):
            auth_token = f'Bearer {token}'
        else:
            auth_token = token
        
        response = requests.post(
            f"{contract_service_url}/api/contracts",
            json=contract_data,
            headers={
                'Authorization': auth_token,
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        
        if response.ok:
            return response.json(), None
        else:
            error_msg = response.json().get('message', 'Lỗi tạo hợp đồng')
            return None, error_msg
    except Exception as e:
        return None, f"Lỗi kết nối Contract Service: {str(e)}"

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'service': SERVICE_NAME}), 200

# ============== BOOKING APIs ==============

# API Tạo booking request (user đặt phòng)
@app.route('/api/bookings', methods=['POST'])
@token_required
def create_booking(current_user):
    """User đăng nhập tạo booking request"""
    try:
        data = request.get_json()
        print(f"[DEBUG] Booking request data: {data}")
        print(f"[DEBUG] Current user: {current_user}")
        
        if not data:
            return jsonify({'message': 'Không có dữ liệu được gửi lên!'}), 400
        
        token = request.headers.get('Authorization') or request.headers.get('authorization')
        
        # Validation
        required_fields = ['room_id', 'start_date', 'end_date', 'monthly_rent', 'deposit']
        missing_fields = []
        for field in required_fields:
            value = data.get(field)
            if value is None or value == '':
                missing_fields.append(field)
        
        if missing_fields:
            print(f"[DEBUG] Missing fields: {missing_fields}")
            return jsonify({'message': f'Thiếu các trường bắt buộc: {", ".join(missing_fields)}!'}), 400
        
        # Validate số
        try:
            monthly_rent = float(data['monthly_rent'])
            deposit = float(data['deposit'])
            if monthly_rent <= 0:
                return jsonify({'message': 'Giá thuê phải lớn hơn 0!'}), 400
            if deposit < 0:
                return jsonify({'message': 'Tiền cọc không được âm!'}), 400
        except (ValueError, TypeError) as e:
            print(f"[DEBUG] Invalid number format: {e}")
            return jsonify({'message': f'Giá trị số không hợp lệ: {str(e)}'}), 400
        
        # Kiểm tra phòng có available không
        try:
            room, error = check_room_availability(data['room_id'], token)
            if error:
                print(f"[DEBUG] Room availability check error: {error}")
                return jsonify({'message': error}), 400
            
            if not room:
                print(f"[DEBUG] Room not found: {data['room_id']}")
                return jsonify({'message': 'Không tìm thấy phòng!'}), 404
            
            if room.get('status') != 'available':
                print(f"[DEBUG] Room not available. Status: {room.get('status')}")
                return jsonify({'message': 'Phòng không còn trống!'}), 400
        except Exception as e:
            print(f"[DEBUG] Error checking room: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'message': f'Lỗi kiểm tra phòng: {str(e)}'}), 500
        
        # Kiểm tra ngày hợp lệ
        try:
            # Xử lý format date (có thể là YYYY-MM-DD hoặc ISO format)
            start_date_str = str(data['start_date']).strip()
            end_date_str = str(data['end_date']).strip()
            
            print(f"[DEBUG] Date strings - start: {start_date_str}, end: {end_date_str}")
            
            # Nếu chỉ có date (YYYY-MM-DD), thêm time
            if len(start_date_str) == 10:
                start_date_str += 'T00:00:00'
            if len(end_date_str) == 10:
                end_date_str += 'T00:00:00'
            
            # Xử lý timezone
            start_date_str = start_date_str.replace('Z', '+00:00')
            end_date_str = end_date_str.replace('Z', '+00:00')
            
            # Parse dates
            try:
                start_date = datetime.datetime.fromisoformat(start_date_str)
                end_date = datetime.datetime.fromisoformat(end_date_str)
            except ValueError as ve:
                # Thử parse với format đơn giản hơn
                if len(data['start_date']) == 10:
                    start_date = datetime.datetime.strptime(data['start_date'], '%Y-%m-%d')
                else:
                    raise ve
                if len(data['end_date']) == 10:
                    end_date = datetime.datetime.strptime(data['end_date'], '%Y-%m-%d')
                else:
                    raise ve
            
            if end_date <= start_date:
                return jsonify({'message': 'Ngày kết thúc phải sau ngày bắt đầu!'}), 400
        except Exception as e:
            print(f"[DEBUG] Date parsing error: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'message': f'Định dạng ngày không hợp lệ: {str(e)}'}), 400
        
        # Tìm tenant từ user_id (user chính là tenant)
        # Token payload contains 'user_id', 'username', 'role'
        user_id = current_user.get('user_id') or current_user.get('_id') or current_user.get('id')
        print(f"[DEBUG] User ID from token: {user_id}, type: {type(user_id)}")
        
        if not user_id:
            print("[DEBUG] No user_id found in current_user")
            return jsonify({'message': 'Không tìm thấy thông tin user!'}), 400
        
        # Convert user_id to ObjectId nếu là string và có format hợp lệ
        try:
            if isinstance(user_id, str) and ObjectId.is_valid(user_id):
                user_id = ObjectId(user_id)
                print(f"[DEBUG] Converted user_id to ObjectId: {user_id}")
        except Exception as e:
            print(f"[DEBUG] Error converting user_id to ObjectId: {str(e)}")
            # Không return error, giữ nguyên user_id là string
            pass
        
        # Lấy thông tin tenant từ tenant-service
        tenant = get_tenant_info(user_id, token)
        print(f"[DEBUG] Tenant found: {tenant is not None}")
        
        if not tenant:
            print(f"[DEBUG] Tenant not found for user_id: {user_id}")
            return jsonify({'message': 'Bạn chưa có thông tin người thuê. Vui lòng liên hệ admin!'}), 400
        
        # Cảnh báo nếu thiếu thông tin (nhưng vẫn cho phép đặt phòng)
        # Admin có thể cập nhật thông tin khi duyệt booking
        missing_info = []
        if not tenant.get('id_card'):
            missing_info.append('CMND/CCCD')
        if not tenant.get('address'):
            missing_info.append('địa chỉ')
        
        warning_message = ''
        if missing_info:
            warning_message = f' (Lưu ý: Bạn chưa cập nhật {", ".join(missing_info)}. Admin có thể yêu cầu bổ sung khi duyệt booking)'
        
        # Tạo booking_id tự động - tìm số lớn nhất và tăng lên 1
        existing_bookings = bookings_collection.find({}, {'_id': 1})
        max_num = 0
        for booking in existing_bookings:
            booking_id_str = str(booking.get('_id', ''))
            if booking_id_str.startswith('BK') and len(booking_id_str) > 2:
                try:
                    num = int(booking_id_str[2:])
                    if num > max_num:
                        max_num = num
                except ValueError:
                    continue
        
        # Tạo booking_id mới
        booking_id = f"BK{max_num + 1:04d}"
        
        # Đảm bảo booking_id không trùng (trong trường hợp hiếm)
        while bookings_collection.find_one({'_id': booking_id}):
            max_num += 1
            booking_id = f"BK{max_num + 1:04d}"
        
        # Xử lý dates - đảm bảo format đúng (dùng lại từ validation)
        start_date_str = data['start_date']
        end_date_str = data['end_date']
        if len(start_date_str) == 10:
            start_date_str += 'T00:00:00'
        if len(end_date_str) == 10:
            end_date_str += 'T00:00:00'
        
        # Parse các giá trị số, đảm bảo không lỗi (đã validate ở trên)
        try:
            electric_price = float(data.get('electric_price', 3500)) if data.get('electric_price') else 3500
            water_price = float(data.get('water_price', 20000)) if data.get('water_price') else 20000
            payment_day = int(data.get('payment_day', 5)) if data.get('payment_day') else 5
        except (ValueError, TypeError) as e:
            print(f"[DEBUG] Invalid optional number format: {e}")
            return jsonify({'message': f'Giá trị số không hợp lệ: {str(e)}'}), 400
        
        new_booking = {
            '_id': booking_id,
            'user_id': user_id,
            'tenant_id': user_id,  # user_id và tenant_id giống nhau
            'room_id': data['room_id'],
            'start_date': start_date_str,
            'end_date': end_date_str,
            'monthly_rent': monthly_rent,
            'deposit': deposit,
            'electric_price': electric_price,
            'water_price': water_price,
            'payment_day': payment_day,
            'notes': data.get('notes', ''),
            'status': 'pending',  # pending | approved | rejected | cancelled
            'created_at': datetime.datetime.utcnow().isoformat(),
            'updated_at': datetime.datetime.utcnow().isoformat()
        }
        
        print(f"[DEBUG] Inserting booking: {new_booking}")
        bookings_collection.insert_one(new_booking)
        new_booking['id'] = new_booking['_id']
        success_message = 'Đặt phòng thành công! Vui lòng chờ admin duyệt.' + warning_message
        print(f"[DEBUG] Booking created successfully: {booking_id}")
        return jsonify({
            'message': success_message,
            'booking': new_booking
        }), 201
    except Exception as e:
        import traceback
        error_msg = f"Error creating booking: {str(e)}"
        print(f"[ERROR] {error_msg}")
        print(traceback.format_exc())
        return jsonify({'message': f'Lỗi tạo booking: {str(e)}'}), 500

# API Lấy danh sách bookings (admin xem tất cả, user xem của mình)
@app.route('/api/bookings', methods=['GET'])
@token_required
def get_bookings(current_user):
    user_id = current_user.get('user_id') or current_user.get('_id') or current_user.get('id')
    role = current_user.get('role', '')
    
    # Convert user_id to ObjectId if string and valid
    if isinstance(user_id, str) and ObjectId.is_valid(user_id):
        try:
            user_id = ObjectId(user_id)
        except:
            pass
    
    query = {}
    # User chỉ xem booking của mình, admin xem tất cả
    if role != 'admin':
        query['user_id'] = user_id
    
    status = request.args.get('status', '').strip()
    if status:
        query['status'] = status
    
    bookings = list(bookings_collection.find(query).sort('created_at', -1))
    
    # Thêm thông tin tenant và room
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    for booking in bookings:
        booking['id'] = booking['_id']
        
        # Lấy thông tin tenant
        booking_tenant_id = booking.get('tenant_id')
        if booking_tenant_id:
            booking_tenant_id = to_object_id(booking_tenant_id)
            tenant = get_tenant_info(booking_tenant_id, token)
            if tenant:
                booking['tenant_info'] = {
                    'name': tenant.get('name', ''),
                    'phone': tenant.get('phone', ''),
                    'email': tenant.get('email', '')
                }
            else:
                booking['tenant_info'] = {
                    'name': '',
                    'phone': '',
                    'email': ''
                }
        else:
            booking['tenant_info'] = {
                'name': '',
                'phone': '',
                'email': ''
            }
        
        # Lấy thông tin room
        room, _ = check_room_availability(booking.get('room_id'), token)
        if room:
            booking['room_info'] = {
                'name': room.get('name', ''),
                'room_type': room.get('room_type', ''),
                'price': room.get('price', 0)
            }
        else:
            booking['room_info'] = {
                'name': '',
                'room_type': '',
                'price': 0
            }
    
    return jsonify({'bookings': bookings, 'total': len(bookings)}), 200

# API Duyệt booking (admin) - Tạo contract qua contract-service
@app.route('/api/bookings/<booking_id>/approve', methods=['PUT'])
@token_required
@admin_required
def approve_booking(current_user, booking_id):
    """Admin duyệt booking và tạo contract"""
    token = request.headers.get('Authorization') or request.headers.get('authorization')
    
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    if booking['status'] != 'pending':
        return jsonify({'message': f'Booking đã được {booking["status"]}!'}), 400
    
    # Kiểm tra phòng vẫn còn available
    room, error = check_room_availability(booking['room_id'], token)
    if error or not room or room.get('status') != 'available':
        return jsonify({'message': 'Phòng không còn trống!'}), 400
    
    try:
        # Tạo contract data
        contract_data = {
            'tenant_id': str(booking['tenant_id']) if isinstance(booking['tenant_id'], ObjectId) else booking['tenant_id'],
            'room_id': booking['room_id'],
            'start_date': booking['start_date'],
            'end_date': booking['end_date'],
            'monthly_rent': booking['monthly_rent'],
            'deposit': booking['deposit'],
            'electric_price': booking.get('electric_price', 3500),
            'water_price': booking.get('water_price', 20000),
            'payment_day': booking.get('payment_day', 5),
            'notes': booking.get('notes', '')
        }
        
        # Tạo contract qua contract-service
        contract_result, error = create_contract_via_service(contract_data, token)
        if error:
            return jsonify({'message': f'Lỗi tạo hợp đồng: {error}'}), 500
        
        contract_id = contract_result.get('contract', {}).get('id') or contract_result.get('contract', {}).get('_id')
        
        # Cập nhật booking status
        bookings_collection.update_one(
            {'_id': booking_id},
            {
                '$set': {
                    'status': 'approved',
                    'contract_id': contract_id,
                    'updated_at': datetime.datetime.utcnow().isoformat()
                }
            }
        )
        
        return jsonify({
            'message': 'Duyệt booking và tạo hợp đồng thành công!',
            'contract': contract_result.get('contract', {})
        }), 200
        
    except Exception as e:
        import traceback
        print(f"Error approving booking: {str(e)}")
        traceback.print_exc()
        return jsonify({'message': f'Lỗi duyệt booking: {str(e)}'}), 500

# API Từ chối booking (admin)
@app.route('/api/bookings/<booking_id>/reject', methods=['PUT'])
@token_required
@admin_required
def reject_booking(current_user, booking_id):
    data = request.get_json() or {}
    reason = data.get('reason', '')
    
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    if booking['status'] != 'pending':
        return jsonify({'message': f'Booking đã được {booking["status"]}!'}), 400
    
    try:
        bookings_collection.update_one(
            {'_id': booking_id},
            {
                '$set': {
                    'status': 'rejected',
                    'rejection_reason': reason,
                    'updated_at': datetime.datetime.utcnow().isoformat()
                }
            }
        )
        
        return jsonify({'message': 'Từ chối booking thành công!'}), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi từ chối booking: {str(e)}'}), 500

# API Hủy booking (user)
@app.route('/api/bookings/<booking_id>/cancel', methods=['PUT'])
@token_required
def cancel_booking(current_user, booking_id):
    user_id = current_user.get('user_id') or current_user.get('_id') or current_user.get('id')
    
    # Convert user_id to ObjectId if string and valid
    if isinstance(user_id, str) and ObjectId.is_valid(user_id):
        try:
            user_id = ObjectId(user_id)
        except:
            pass
    
    booking = bookings_collection.find_one({'_id': booking_id})
    if not booking:
        return jsonify({'message': 'Booking không tồn tại!'}), 404
    
    # User chỉ có thể hủy booking của mình
    booking_user_id = booking.get('user_id')
    if isinstance(booking_user_id, str) and ObjectId.is_valid(booking_user_id):
        try:
            booking_user_id = ObjectId(booking_user_id)
        except:
            pass
    
    if booking_user_id != user_id:
        return jsonify({'message': 'Bạn không có quyền hủy booking này!'}), 403
    
    if booking['status'] != 'pending':
        return jsonify({'message': f'Không thể hủy booking đã được {booking["status"]}!'}), 400
    
    try:
        bookings_collection.update_one(
            {'_id': booking_id},
            {
                '$set': {
                    'status': 'cancelled',
                    'updated_at': datetime.datetime.utcnow().isoformat()
                }
            }
        )
        
        return jsonify({'message': 'Hủy booking thành công!'}), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi hủy booking: {str(e)}'}), 500

if __name__ == '__main__':
    register_service()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=True)

