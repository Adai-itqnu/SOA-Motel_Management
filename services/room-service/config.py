"""
Room Service Configuration
"""
import os


class Config:
    """Application configuration"""
    
    # MongoDB
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/rooms_db')
    DB_NAME = 'rooms_db'
    COLLECTION_NAME = 'rooms'
    
    # Service Info
    SERVICE_NAME = 'room-service'
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5002'))
    
    # JWT
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')
    
    # Consul
    CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))
    
    # Internal API
    INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-secret-key')
    
    # Debug
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    # Room Status Constants
    STATUS_AVAILABLE = 'available'
    STATUS_OCCUPIED = 'occupied'
    STATUS_MAINTENANCE = 'maintenance'
    STATUS_RESERVED = 'reserved'
    ALLOWED_STATUSES = {STATUS_AVAILABLE, STATUS_OCCUPIED, STATUS_MAINTENANCE, STATUS_RESERVED}
    
    # Default Values
    DEFAULT_ELECTRIC_PRICE = 3500
    DEFAULT_WATER_PRICE = 20000
    DEFAULT_PAYMENT_DAY = 5


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