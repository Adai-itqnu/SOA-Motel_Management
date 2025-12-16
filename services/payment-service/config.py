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
VNPAY_TMN_CODE = os.getenv('VNPAY_TMN_CODE', '729I87YR').strip()  # Official sandbox merchant code
VNPAY_HASH_SECRET = os.getenv('VNPAY_HASH_SECRET', 'ZKPI2R2IFEA4VIA1WMCMI65XQUMQHTWT').strip()  # Official sandbox secret
VNPAY_URL = os.getenv('VNPAY_URL', 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html').strip()
# VNPay QueryDR/Refund API endpoint (used for server-to-server verification).
# If not provided, derive from VNPAY_URL.
_DEFAULT_VNPAY_API_URL = ''
try:
	if VNPAY_URL:
		_DEFAULT_VNPAY_API_URL = VNPAY_URL.replace('/paymentv2/vpcpay.html', '/merchant_webapi/api/transaction')
except Exception:
	_DEFAULT_VNPAY_API_URL = ''

VNPAY_API_URL = os.getenv('VNPAY_API_URL', _DEFAULT_VNPAY_API_URL).strip()
VNPAY_RETURN_URL = os.getenv('VNPAY_RETURN_URL', 'http://localhost/api/payments/vnpay/return').strip()

# Confirmation strategy:
# - return: mark paid when browser returns with valid signature + amount match (project/demo-friendly)
# - querydr: mark paid only when VNPay QueryDR verifies (server-to-server)
# - ipn: mark paid only on IPN (requires public callback URL, e.g. ngrok)
VNPAY_CONFIRM_MODE = os.getenv('VNPAY_CONFIRM_MODE', 'return').strip().lower()

# Optional: explicitly provide IPN callback URL (useful with ngrok). If set, payment URL will include vnp_IpnUrl.
VNPAY_IPN_URL = os.getenv('VNPAY_IPN_URL', '').strip()

# Internal API key for service-to-service communication
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-secret-key')

