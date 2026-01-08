# Payment Service Configuration
import os


class Config:
    # MongoDB
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/payments_db')
    DB_NAME = 'payments_db'
    COLLECTION_NAME = 'payments'
    
    # Service Info
    SERVICE_NAME = 'payment-service'
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5008'))
    
    # JWT
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')
    
    # Consul
    CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))
    
    # Internal API
    INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-secret-key')
    
    # VNPay Configuration (Sandbox)
    VNPAY_TMN_CODE = os.getenv('VNPAY_TMN_CODE', '729I87YR').strip()
    VNPAY_HASH_SECRET = os.getenv('VNPAY_HASH_SECRET', 'ZKPI2R2IFEA4VIA1WMCMI65XQUMQHTWT').strip()
    VNPAY_URL = os.getenv('VNPAY_URL', 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html').strip()
    VNPAY_RETURN_URL = os.getenv('VNPAY_RETURN_URL', 'http://localhost/api/vnpay/return').strip()
    VNPAY_IPN_URL = os.getenv('VNPAY_IPN_URL', '').strip()
    VNPAY_CONFIRM_MODE = os.getenv('VNPAY_CONFIRM_MODE', 'return').strip().lower()
    
    # VNPay API URL (for QueryDR/Refund)
    @classmethod
    def get_vnpay_api_url(cls):
        default_url = ''
        if cls.VNPAY_URL:
            default_url = cls.VNPAY_URL.replace('/paymentv2/vpcpay.html', '/merchant_webapi/api/transaction')
        return os.getenv('VNPAY_API_URL', default_url).strip()
    
    # Debug
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'


# Backward compatibility
MONGO_URI = Config.MONGO_URI
DB_NAME = Config.DB_NAME
COLLECTION_NAME = Config.COLLECTION_NAME
SERVICE_NAME = Config.SERVICE_NAME
SERVICE_PORT = Config.SERVICE_PORT
JWT_SECRET = Config.JWT_SECRET
CONSUL_HOST = Config.CONSUL_HOST
CONSUL_PORT = Config.CONSUL_PORT
INTERNAL_API_KEY = Config.INTERNAL_API_KEY
VNPAY_TMN_CODE = Config.VNPAY_TMN_CODE
VNPAY_HASH_SECRET = Config.VNPAY_HASH_SECRET
VNPAY_URL = Config.VNPAY_URL
VNPAY_RETURN_URL = Config.VNPAY_RETURN_URL
VNPAY_IPN_URL = Config.VNPAY_IPN_URL
VNPAY_CONFIRM_MODE = Config.VNPAY_CONFIRM_MODE
VNPAY_API_URL = Config.get_vnpay_api_url()
