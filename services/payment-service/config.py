import os

# MongoDB configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/payments_db')

# Service configuration
SERVICE_NAME = "payment-service"
SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5008'))

# JWT configuration
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')

# Consul configuration
CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))

# Database configuration
DB_NAME = 'payments_db'
COLLECTION_NAME = 'payments'

# VNpay configuration (Sandbox for testing)
# Register at: https://sandbox.vnpayment.vn/
# Demo credentials for sandbox testing from VNPAY docs
VNPAY_TMN_CODE = os.getenv('VNPAY_TMN_CODE', 'CGWSANDBOX')  # Official sandbox merchant code
VNPAY_HASH_SECRET = os.getenv('VNPAY_HASH_SECRET', 'RAOEXHYVSDDIIENYWSLDIIZTANXUXZFJ')  # Official sandbox secret
VNPAY_URL = os.getenv('VNPAY_URL', 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html')
VNPAY_RETURN_URL = os.getenv('VNPAY_RETURN_URL', 'http://localhost:5000/payment-return')

# Internal API key for service-to-service communication
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-api-key-change-me')

