from flask import Flask, request, jsonify
from flask_cors import CORS
import datetime
import jwt
from functools import wraps
import requests
from config import JWT_SECRET, SERVICE_NAME, SERVICE_PORT, CONSUL_HOST, CONSUL_PORT
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

# Helper function: Get data from other services
def fetch_service_data(service_name, endpoint, token):
    try:
        service_url = get_service_url(service_name)
        if not service_url:
            return None
        
        # Ensure token has correct Bearer prefix
        if token and (token.startswith('Bearer ') or token.startswith('bearer ')):
            auth_header = token
        else:
            auth_header = f'Bearer {token}'
        
        response = requests.get(
            f"{service_url}{endpoint}",
            headers={'Authorization': auth_header},
            timeout=10
        )
        
        if response.ok:
            return response.json()
        return None
    except Exception as e:
        print(f"Error fetching from {service_name}: {e}")
        return None

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': app.config['SERVICE_NAME']}), 200

# ============== BILL APIs ==============

# API Tạo hóa đơn
@app.route('/api/bills', methods=['POST'])
@token_required
@admin_required
def create_bill(current_user):
    data = request.get_json()
    
    # Validation
    required_fields = ['contract_id', 'room_id', 'month', 'year', 'electric_old', 'electric_new', 'water_old', 'water_new']
    for field in required_fields:
        if field not in data:
            return jsonify({'message': f'Thiếu trường {field}!'}), 400
    
    # Kiểm tra bill đã tồn tại chưa
    existing_bill = bills_collection.find_one({
        'contract_id': data['contract_id'],
        'month': data['month'],
        'year': data['year']
    })
    
    if existing_bill:
        return jsonify({'message': 'Hóa đơn tháng này đã tồn tại!'}), 400
    
    # Tính toán
    electric_used = data['electric_new'] - data['electric_old']
    water_used = data['water_new'] - data['water_old']
    
    electric_cost = electric_used * float(data.get('electric_price', 3500))
    water_cost = water_used * float(data.get('water_price', 20000))
    room_rent = float(data.get('room_rent', 0))
    other_fees = float(data.get('other_fees', 0))
    
    total_amount = room_rent + electric_cost + water_cost + other_fees
    
    # Tạo bill_id
    bill_count = bills_collection.count_documents({})
    bill_id = f"B{bill_count + 1:05d}"
    
    new_bill = {
        '_id': bill_id,
        'contract_id': data['contract_id'],
        'room_id': data['room_id'],
        'tenant_id': data.get('tenant_id', ''),
        'month': data['month'],
        'year': data['year'],
        'electric_old': data['electric_old'],
        'electric_new': data['electric_new'],
        'electric_used': electric_used,
        'electric_price': float(data.get('electric_price', 3500)),
        'electric_cost': electric_cost,
        'water_old': data['water_old'],
        'water_new': data['water_new'],
        'water_used': water_used,
        'water_price': float(data.get('water_price', 20000)),
        'water_cost': water_cost,
        'room_rent': room_rent,
        'other_fees': other_fees,
        'total_amount': total_amount,
        'paid_amount': 0,
        'debt_amount': total_amount,
        'status': 'unpaid',  # unpaid | partial | paid
        'due_date': data.get('due_date', ''),
        'notes': data.get('notes', ''),
        'created_at': datetime.datetime.utcnow().isoformat(),
        'updated_at': datetime.datetime.utcnow().isoformat()
    }
    
    try:
        bills_collection.insert_one(new_bill)
        new_bill['id'] = new_bill['_id']
        return jsonify({
            'message': 'Tạo hóa đơn thành công!',
            'bill': new_bill
        }), 201
    except Exception as e:
        return jsonify({'message': f'Lỗi tạo hóa đơn: {str(e)}'}), 500

# API Thanh toán hóa đơn
@app.route('/api/bills/<bill_id>/pay', methods=['PUT'])
@token_required
@admin_required
def pay_bill(current_user, bill_id):
    data = request.get_json()
    
    if 'amount' not in data:
        return jsonify({'message': 'Thiếu số tiền thanh toán!'}), 400
    
    bill = bills_collection.find_one({'_id': bill_id})
    if not bill:
        return jsonify({'message': 'Hóa đơn không tồn tại!'}), 404
    
    amount = float(data['amount'])
    new_paid_amount = bill['paid_amount'] + amount
    new_debt_amount = bill['total_amount'] - new_paid_amount
    
    # Xác định trạng thái
    if new_debt_amount <= 0:
        status = 'paid'
        new_debt_amount = 0
    elif new_paid_amount > 0:
        status = 'partial'
    else:
        status = 'unpaid'
    
    try:
        bills_collection.update_one(
            {'_id': bill_id},
            {
                '$set': {
                    'paid_amount': new_paid_amount,
                    'debt_amount': new_debt_amount,
                    'status': status,
                    'payment_date': datetime.datetime.utcnow().isoformat() if status == 'paid' else bill.get('payment_date', ''),
                    'updated_at': datetime.datetime.utcnow().isoformat()
                }
            }
        )
        
        return jsonify({
            'message': 'Thanh toán thành công!',
            'paid_amount': new_paid_amount,
            'debt_amount': new_debt_amount,
            'status': status
        }), 200
    except Exception as e:
        return jsonify({'message': f'Lỗi thanh toán: {str(e)}'}), 500

# API Lấy danh sách hóa đơn
@app.route('/api/bills', methods=['GET'])
@token_required
@admin_required
def get_bills(current_user):
    status = request.args.get('status', '')
    month = request.args.get('month', '')
    year = request.args.get('year', '')
    room_id = request.args.get('room_id', '')
    
    query = {}
    if status:
        query['status'] = status
    if month:
        query['month'] = int(month)
    if year:
        query['year'] = int(year)
    if room_id:
        query['room_id'] = room_id
    
    bills = list(bills_collection.find(query).sort('created_at', -1))
    
    for bill in bills:
        bill['id'] = bill['_id']
    
    return jsonify({'bills': bills, 'total': len(bills)}), 200

# ============== REPORT APIs ==============

# API Báo cáo tổng quan
@app.route('/api/reports/overview', methods=['GET'])
@token_required
@admin_required
def get_overview_report(current_user):
    token = request.headers.get('Authorization')
    
    # Lấy dữ liệu từ các service khác
    rooms_data = fetch_service_data('room-service', '/api/rooms/stats', token)
    contracts_data = fetch_service_data('contract-service', '/api/contracts?status=active', token)
    
    # Thống kê hóa đơn
    total_bills = bills_collection.count_documents({})
    paid_bills = bills_collection.count_documents({'status': 'paid'})
    unpaid_bills = bills_collection.count_documents({'status': 'unpaid'})
    partial_bills = bills_collection.count_documents({'status': 'partial'})
    
    # Tính tổng doanh thu từ bills (thanh toán hàng tháng)
    pipeline_revenue = [
        {'$match': {'status': 'paid'}},
        {'$group': {'_id': None, 'total': {'$sum': '$total_amount'}}}
    ]
    revenue_result = list(bills_collection.aggregate(pipeline_revenue))
    revenue_from_bills = revenue_result[0]['total'] if revenue_result else 0
    
    # Tính tổng tiền cọc từ contracts (deposit) - lấy tất cả contracts
    all_contracts_data = fetch_service_data('contract-service', '/api/contracts', token)
    revenue_from_deposits = 0
    if all_contracts_data and all_contracts_data.get('contracts'):
        for contract in all_contracts_data['contracts']:
            # Tính deposit từ tất cả contracts (kể cả đã kết thúc)
            revenue_from_deposits += float(contract.get('deposit', 0))
    
    # Tổng doanh thu = tiền cọc + thanh toán từ bills
    total_revenue = revenue_from_bills + revenue_from_deposits
    
    # Tính tổng nợ
    pipeline_debt = [
        {'$match': {'status': {'$in': ['unpaid', 'partial']}}},
        {'$group': {'_id': None, 'total': {'$sum': '$debt_amount'}}}
    ]
    debt_result = list(bills_collection.aggregate(pipeline_debt))
    total_debt = debt_result[0]['total'] if debt_result else 0
    
    overview = {
        'rooms': rooms_data if rooms_data else {
            'total': 0,
            'available': 0,
            'occupied': 0,
            'occupancy_rate': 0
        },
        'contracts': {
            'active': contracts_data['total'] if contracts_data else 0
        },
        'bills': {
            'total': total_bills,
            'paid': paid_bills,
            'unpaid': unpaid_bills,
            'partial': partial_bills
        },
        'finance': {
            'total_revenue': total_revenue,
            'total_debt': total_debt,
            'collection_rate': round((total_revenue / (total_revenue + total_debt) * 100) if (total_revenue + total_debt) > 0 else 0, 2)
        }
    }
    
    return jsonify(overview), 200

# API Báo cáo doanh thu theo tháng
@app.route('/api/reports/revenue', methods=['GET'])
@token_required
@admin_required
def get_revenue_report(current_user):
    year = request.args.get('year', datetime.datetime.now().year)
    token = request.headers.get('Authorization')
    
    # Tính doanh thu từ bills (thanh toán hàng tháng)
    pipeline = [
        {'$match': {'year': int(year), 'status': 'paid'}},
        {'$group': {
            '_id': '$month',
            'revenue': {'$sum': '$total_amount'},
            'bills_count': {'$sum': 1}
        }},
        {'$sort': {'_id': 1}}
    ]
    
    result = list(bills_collection.aggregate(pipeline))
    
    # Tính tiền cọc từ contracts được tạo trong năm đó
    contracts_data = fetch_service_data('contract-service', '/api/contracts', token)
    deposits_by_month = {}
    if contracts_data and contracts_data.get('contracts'):
        for contract in contracts_data['contracts']:
            try:
                created_date = datetime.datetime.fromisoformat(contract.get('created_at', ''))
                if created_date.year == int(year):
                    month = created_date.month
                    deposit = float(contract.get('deposit', 0))
                    if month not in deposits_by_month:
                        deposits_by_month[month] = 0
                    deposits_by_month[month] += deposit
            except:
                pass
    
    # Tạo data cho 12 tháng (bills + deposits)
    revenue_by_month = []
    for month in range(1, 13):
        month_data = next((item for item in result if item['_id'] == month), None)
        bills_revenue = month_data['revenue'] if month_data else 0
        deposits_revenue = deposits_by_month.get(month, 0)
        total_month_revenue = bills_revenue + deposits_revenue
        
        revenue_by_month.append({
            'month': month,
            'revenue': total_month_revenue,
            'bills_revenue': bills_revenue,
            'deposits_revenue': deposits_revenue,
            'bills_count': month_data['bills_count'] if month_data else 0
        })
    
    total_revenue = sum(item['revenue'] for item in revenue_by_month)
    
    return jsonify({
        'year': int(year),
        'total_revenue': total_revenue,
        'monthly_data': revenue_by_month
    }), 200

# API Báo cáo nợ tiền
@app.route('/api/reports/debt', methods=['GET'])
@token_required
@admin_required
def get_debt_report(current_user):
    token = request.headers.get('Authorization')
    
    # Lấy tất cả hóa đơn chưa thanh toán hoặc thanh toán một phần
    debt_bills = list(bills_collection.find({
        'status': {'$in': ['unpaid', 'partial']}
    }).sort('due_date', 1))
    
    for bill in debt_bills:
        bill['id'] = bill['_id']
        
        # Lấy thông tin tenant từ Tenant Service
        if bill.get('contract_id'):
            contract_data = fetch_service_data(
                'contract-service', 
                f"/api/contracts/{bill['contract_id']}", 
                token
            )
            if contract_data:
                bill['tenant_name'] = contract_data.get('tenant_info', {}).get('name', '')
                bill['tenant_phone'] = contract_data.get('tenant_info', {}).get('phone', '')
    
    # Tính tổng nợ
    total_debt = sum(bill['debt_amount'] for bill in debt_bills)
    
    # Phân loại nợ theo mức độ
    overdue_bills = []
    current_date = datetime.datetime.now()
    
    for bill in debt_bills:
        if bill.get('due_date'):
            try:
                due_date = datetime.datetime.fromisoformat(bill['due_date'])
                days_overdue = (current_date - due_date).days
                bill['days_overdue'] = days_overdue if days_overdue > 0 else 0
                
                if days_overdue > 0:
                    overdue_bills.append(bill)
            except:
                bill['days_overdue'] = 0
    
    return jsonify({
        'total_debt': total_debt,
        'total_bills': len(debt_bills),
        'overdue_bills': len(overdue_bills),
        'details': debt_bills
    }), 200

# API Báo cáo theo phòng
@app.route('/api/reports/room/<room_id>', methods=['GET'])
@token_required
@admin_required
def get_room_report(current_user, room_id):
    token = request.headers.get('Authorization')
    
    # Lấy thông tin phòng
    room_data = fetch_service_data('room-service', f'/api/rooms/{room_id}', token)
    
    # Lấy hợp đồng hiện tại
    contracts_data = fetch_service_data('contract-service', f'/api/contracts/room/{room_id}', token)
    
    # Lấy hóa đơn của phòng
    bills = list(bills_collection.find({'room_id': room_id}).sort('created_at', -1))
    
    for bill in bills:
        bill['id'] = bill['_id']
    
    # Thống kê
    total_revenue = sum(bill['total_amount'] for bill in bills if bill['status'] == 'paid')
    total_debt = sum(bill['debt_amount'] for bill in bills if bill['status'] in ['unpaid', 'partial'])
    
    return jsonify({
        'room': room_data,
        'contracts': contracts_data.get('contracts', []) if contracts_data else [],
        'bills': bills,
        'statistics': {
            'total_bills': len(bills),
            'total_revenue': total_revenue,
            'total_debt': total_debt
        }
    }), 200

# API Xuất báo cáo Excel (placeholder - cần thêm thư viện openpyxl)
@app.route('/api/reports/export', methods=['GET'])
@token_required
@admin_required
def export_report(current_user):
    report_type = request.args.get('type', 'overview')
    
    # TODO: Implement Excel export with openpyxl
    
    return jsonify({
        'message': 'Tính năng xuất Excel đang được phát triển',
        'report_type': report_type
    }), 501

if __name__ == '__main__':
    register_service()
    app.run(host='0.0.0.0', port=SERVICE_PORT, debug=True)