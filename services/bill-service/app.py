from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import calendar
import jwt
from functools import wraps
import requests
from config import JWT_SECRET, SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT, INTERNAL_API_KEY
from model import bills_collection
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
        # Fallback: use service name directly in Docker network
        service_ports = {
            'room-service': 5002,
            'tenant-service': 5003
        }
        port = service_ports.get(service_name, 5001)
        return f"http://{service_name}:{port}"
    except Exception as e:
        print(f"Error getting service URL: {e}")
        # Fallback: use service name directly in Docker network
        service_ports = {
            'room-service': 5002,
            'tenant-service': 5003
        }
        port = service_ports.get(service_name, 5001)
        return f"http://{service_name}:{port}"

# Helper function: Get data from other services
def fetch_service_data(service_name, endpoint, token=None):
    try:
        service_url = get_service_url(service_name)
        if not service_url:
            return None
        
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}' if not token.startswith('Bearer ') else token
        
        response = requests.get(
            f"{service_url}{endpoint}",
            headers=headers,
            timeout=10
        )
        
        if response.ok:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching from {service_name}: {e}")
        return None

def compute_due_date(month_str, payment_day=5):
    """Return ISO date string for due date based on billing month and payment day."""
    try:
        base_date = datetime.datetime.strptime(month_str + "-01", "%Y-%m-%d")
        last_day = calendar.monthrange(base_date.year, base_date.month)[1]
        target_day = min(max(1, int(payment_day)), last_day)
        due_date = base_date.replace(day=target_day)
        return due_date.strftime("%Y-%m-%d")
    except Exception as exc:
        print(f"Error computing due date: {exc}")
        return month_str + "-05"

def send_notification(user_id, title, message, notification_type, metadata=None):
    """Send notification via notification-service (internal)."""
    try:
        notification_service_url = get_service_url('notification-service')
        if not notification_service_url:
            return False
        payload = {
            'user_id': str(user_id),
            'title': title,
            'message': message,
            'type': notification_type,
            'metadata': metadata or {}
        }
        response = requests.post(
            f"{notification_service_url}/api/notifications",
            json=payload,
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY, 'Content-Type': 'application/json'},
            timeout=5
        )
        if not response.ok:
            print(f"Failed to send notification: {response.text}")
        return response.ok
    except Exception as exc:
        print(f"Error sending notification: {exc}")
        return False

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': app.config['SERVICE_NAME']}), 200

# API Tính toán tiền (không lưu)
@app.route('/api/bills/calculate', methods=['POST'])
@token_required
def calculate_bill(current_user):
    data = request.get_json()
    
    # Validation
    required_fields = ['electric_start', 'electric_end', 'water_start', 'water_end', 'electric_price', 'water_price']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Validate số liệu
    if data['electric_end'] < data['electric_start']:
        return jsonify({'message': 'Số điện cuối phải lớn hơn số điện đầu!'}), 400
    
    if data['water_end'] < data['water_start']:
        return jsonify({'message': 'Số nước cuối phải lớn hơn số nước đầu!'}), 400
    
    # Tính toán
    electric_usage = data['electric_end'] - data['electric_start']
    water_usage = data['water_end'] - data['water_start']
    electric_cost = electric_usage * float(data['electric_price'])
    water_cost = water_usage * float(data['water_price'])
    room_price = float(data.get('room_price', 0))
    total_amount = room_price + electric_cost + water_cost
    
    return jsonify({
        'electric_usage': electric_usage,
        'electric_cost': electric_cost,
        'water_usage': water_usage,
        'water_cost': water_cost,
        'room_price': room_price,
        'total_amount': total_amount
    }), 200

# API Tạo hóa đơn mới
@app.route('/api/bills', methods=['POST'])
@token_required
@admin_required
def create_bill(current_user):
    data = request.get_json()
    
    # Validation
    required_fields = ['tenant_id', 'room_id', 'month', 'electric_start', 'electric_end', 'water_start', 'water_end', 'electric_price', 'water_price']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Validate số liệu
    if data['electric_end'] < data['electric_start']:
        return jsonify({'message': 'Số điện cuối phải lớn hơn số điện đầu!'}), 400
    
    if data['water_end'] < data['water_start']:
        return jsonify({'message': 'Số nước cuối phải lớn hơn số nước đầu!'}), 400
    
    # Kiểm tra bill đã tồn tại chưa
    existing_bill = bills_collection.find_one({
        'tenant_id': data['tenant_id'],
        'month': data['month']
    })
    
    if existing_bill:
        return jsonify({'message': 'Hóa đơn tháng này đã tồn tại!'}), 400
    
    # Lấy room_price nếu không có
    room_price = float(data.get('room_price', 0))
    if room_price == 0:
        token = request.headers.get('Authorization') or request.headers.get('authorization')
        room_data = fetch_service_data('room-service', f"/api/rooms/{data['room_id']}", token)
        if room_data and 'price' in room_data:
            room_price = float(room_data['price'])
        else:
            return jsonify({'message': 'Không thể lấy giá phòng. Vui lòng cung cấp room_price!'}), 400
    
    payment_day = int(data.get('payment_day', 5))
    
    # Tính toán
    electric_usage = data['electric_end'] - data['electric_start']
    water_usage = data['water_end'] - data['water_start']
    electric_cost = electric_usage * float(data['electric_price'])
    water_cost = water_usage * float(data['water_price'])
    total_amount = room_price + electric_cost + water_cost
    due_date = compute_due_date(data['month'], payment_day)
    
    # Tạo bill_id
    bill_count = bills_collection.count_documents({})
    bill_id = f"B{bill_count + 1:03d}"
    
    new_bill = {
        '_id': bill_id,
        'tenant_id': data['tenant_id'],
        'room_id': data['room_id'],
        'month': data['month'],
        'room_price': room_price,
        'electric_start': data['electric_start'],
        'electric_end': data['electric_end'],
        'water_start': data['water_start'],
        'water_end': data['water_end'],
        'electric_price': float(data['electric_price']),
        'water_price': float(data['water_price']),
        'total_amount': total_amount,
        'status': 'unpaid',
        'payment_day': payment_day,
        'due_date': due_date,
        'created_at': datetime.datetime.utcnow().isoformat()
    }
    
    try:
        bills_collection.insert_one(new_bill)
        new_bill['id'] = new_bill['_id']
        
        # Gửi thông báo cho người thuê
        send_notification(
            new_bill['tenant_id'],
            f"Hóa đơn tháng {new_bill['month']} đã được tạo",
            f"Tổng tiền cần thanh toán: {total_amount:,.0f} VND. Hạn thanh toán: {due_date}.",
            "rent_invoice_created",
            {'bill_id': new_bill['_id'], 'due_date': due_date, 'amount': total_amount}
        )
        
        return jsonify({
            'message': 'Tạo hóa đơn thành công!',
            'bill': new_bill
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo hóa đơn: {str(e)}'}), 500

# API Lấy danh sách hóa đơn
@app.route('/api/bills', methods=['GET'])
@token_required
def get_bills(current_user):
    room_id = request.args.get('room_id')
    tenant_id = request.args.get('tenant_id')
    status = request.args.get('status')
    month = request.args.get('month')
    
    query = {}
    
    # Filter theo room_id
    if room_id:
        query['room_id'] = room_id
    
    # Filter theo tenant_id
    if tenant_id:
        query['tenant_id'] = tenant_id
    
    # Filter theo status
    if status:
        query['status'] = status
    
    # Filter theo month
    if month:
        query['month'] = month
    
    # Nếu là user thường, chỉ cho xem hóa đơn của mình
    if current_user.get('role') != 'admin':
        query['tenant_id'] = current_user.get('user_id') or current_user.get('id')
    
    bills = list(bills_collection.find(query).sort('created_at', -1))
    
    # Convert ObjectId
    for bill in bills:
        bill['id'] = bill['_id']
    
    return jsonify({'bills': bills, 'total': len(bills)}), 200

# Internal API: trả về danh sách hóa đơn chưa thanh toán để gửi thông báo
@app.route('/internal/bills/unpaid', methods=['GET'])
@internal_api_required
def get_unpaid_bills_internal():
    status = request.args.get('status', 'unpaid')
    query = {'status': status}
    bills = list(bills_collection.find(query).sort('due_date', 1))
    for bill in bills:
        bill['id'] = bill['_id']
    return jsonify({'bills': bills, 'total': len(bills)}), 200

# API Lấy chi tiết hóa đơn
@app.route('/api/bills/<bill_id>', methods=['GET'])
@token_required
def get_bill(current_user, bill_id):
    bill = bills_collection.find_one({'_id': bill_id})
    
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    # Nếu là user thường, chỉ cho xem hóa đơn của mình
    if current_user.get('role') != 'admin':
        if bill['tenant_id'] != (current_user.get('user_id') or current_user.get('id')):
            return jsonify({'message': 'Không có quyền xem hóa đơn này!'}), 403
    
    bill['id'] = bill['_id']
    return jsonify(bill), 200

# API Cập nhật hóa đơn
@app.route('/api/bills/<bill_id>', methods=['PUT'])
@token_required
@admin_required
def update_bill(current_user, bill_id):
    bill = bills_collection.find_one({'_id': bill_id})
    
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    # Không cho phép cập nhật nếu đã thanh toán
    if bill['status'] == 'paid':
        return jsonify({'message': 'Không thể cập nhật hóa đơn đã thanh toán!'}), 400
    
    data = request.get_json()
    
    # Cập nhật các trường có thể thay đổi
    update_fields = {}
    
    if 'electric_start' in data:
        update_fields['electric_start'] = data['electric_start']
    if 'electric_end' in data:
        update_fields['electric_end'] = data['electric_end']
    if 'water_start' in data:
        update_fields['water_start'] = data['water_start']
    if 'water_end' in data:
        update_fields['water_end'] = data['water_end']
    if 'electric_price' in data:
        update_fields['electric_price'] = float(data['electric_price'])
    if 'water_price' in data:
        update_fields['water_price'] = float(data['water_price'])
    if 'room_price' in data:
        update_fields['room_price'] = float(data['room_price'])
    
    # Tính lại total_amount nếu có thay đổi
    if update_fields:
        electric_start = update_fields.get('electric_start', bill['electric_start'])
        electric_end = update_fields.get('electric_end', bill['electric_end'])
        water_start = update_fields.get('water_start', bill['water_start'])
        water_end = update_fields.get('water_end', bill['water_end'])
        electric_price = update_fields.get('electric_price', bill['electric_price'])
        water_price = update_fields.get('water_price', bill['water_price'])
        room_price = update_fields.get('room_price', bill['room_price'])
        
        electric_usage = electric_end - electric_start
        water_usage = water_end - water_start
        electric_cost = electric_usage * electric_price
        water_cost = water_usage * water_price
        total_amount = room_price + electric_cost + water_cost
        
        update_fields['total_amount'] = total_amount
    
    try:
        bills_collection.update_one(
            {'_id': bill_id},
            {'$set': update_fields}
        )
        
        updated_bill = bills_collection.find_one({'_id': bill_id})
        updated_bill['id'] = updated_bill['_id']
        
        return jsonify({
            'message': 'Cập nhật hóa đơn thành công!',
            'bill': updated_bill
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi cập nhật hóa đơn: {str(e)}'}), 500

# API Xóa hóa đơn
@app.route('/api/bills/<bill_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_bill(current_user, bill_id):
    bill = bills_collection.find_one({'_id': bill_id})
    
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    # Không cho phép xóa hóa đơn đã thanh toán
    if bill.get('status') == 'paid':
        return jsonify({'message': 'Không thể xóa hóa đơn đã thanh toán!'}), 400
    
    try:
        bills_collection.delete_one({'_id': bill_id})
        return jsonify({
            'message': 'Xóa hóa đơn thành công!'
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi xóa hóa đơn: {str(e)}'}), 500

# API Cập nhật status hóa đơn (được payment-service gọi)
@app.route('/api/bills/<bill_id>/status', methods=['PUT'])
def update_bill_status(bill_id):
    # Không cần token vì đây là internal API được payment-service gọi
    data = request.get_json()
    
    if 'status' not in data:
        return jsonify({'message': 'Thiếu trường status!'}), 400
    
    if data['status'] not in ['paid', 'unpaid']:
        return jsonify({'message': 'Status không hợp lệ!'}), 400
    
    bill = bills_collection.find_one({'_id': bill_id})
    
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    try:
        bills_collection.update_one(
            {'_id': bill_id},
            {'$set': {'status': data['status']}}
        )
        
        return jsonify({
            'message': 'Cập nhật status thành công!',
            'status': data['status']
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi cập nhật status: {str(e)}'}), 500

if __name__ == '__main__':
    register_service()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=True)

