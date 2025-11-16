from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Lấy API Gateway URL từ environment variable
API_GATEWAY = os.getenv('API_GATEWAY', 'http://localhost')

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'frontend'}), 200

# Trang chủ - redirect đến login
@app.route('/')
def index():
    return render_template('login.html', api_gateway=API_GATEWAY)

# Trang đăng ký
@app.route('/register')
def register_page():
    return render_template('register.html', api_gateway=API_GATEWAY)

# Trang đăng nhập
@app.route('/login')
def login_page():
    return render_template('login.html', api_gateway=API_GATEWAY)

# Trang user home - KHÔNG kiểm tra session, để JavaScript xử lý
@app.route('/user-home')
def user_home():
    # Render trang trực tiếp, JavaScript sẽ kiểm tra localStorage
    return render_template('user-home.html', api_gateway=API_GATEWAY)

# Trang admin dashboard - KHÔNG kiểm tra session, để JavaScript xử lý
@app.route('/admin-dashboard')
def admin_dashboard():
    # Render trang trực tiếp, JavaScript sẽ kiểm tra localStorage
    return render_template('admin-dashboard.html', api_gateway=API_GATEWAY)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)