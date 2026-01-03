# Booking Service Configuration
import os


class Config:
    # MongoDB
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/users_db')
    DB_NAME = 'users_db'
    COLLECTION_NAME = 'bookings'
    
    # Service
    SERVICE_NAME = 'booking-service'
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5005'))
    
    # JWT
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')
    
    # Consul
    CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))
    
    # Internal API
    INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-secret-key')
    
    # Debug
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    # Booking Status
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_MOVE_IN_READY = 'move_in_ready'
    
    # Deposit Status
    DEPOSIT_AWAITING = 'awaiting_payment'
    DEPOSIT_PENDING_CASH = 'pending_cash'
    DEPOSIT_PAID = 'paid'
    DEPOSIT_FAILED = 'failed'
    DEPOSIT_REFUNDED = 'refunded'
    
    # Defaults
    DEFAULT_ELECTRIC_PRICE = 3500
    DEFAULT_WATER_PRICE = 20000
    DEFAULT_PAYMENT_DAY = 5


# Backward compatibility
MONGO_URI = Config.MONGO_URI
SERVICE_NAME = Config.SERVICE_NAME
SERVICE_PORT = Config.SERVICE_PORT
JWT_SECRET = Config.JWT_SECRET
CONSUL_HOST = Config.CONSUL_HOST
CONSUL_PORT = Config.CONSUL_PORT
INTERNAL_API_KEY = Config.INTERNAL_API_KEY
