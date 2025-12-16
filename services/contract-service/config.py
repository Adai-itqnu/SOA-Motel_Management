"""Contract Service Configuration"""
import os

class Config:
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/contracts_db')
    DB_NAME = os.getenv('DB_NAME', 'contracts_db')
    COLLECTION_NAME = 'contracts'
    SERVICE_NAME = 'contract-service'
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5006'))
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')
    CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))
    INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-secret-key')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_TERMINATED = 'terminated'

# Backward compatibility
MONGO_URI = Config.MONGO_URI
SERVICE_NAME = Config.SERVICE_NAME
SERVICE_PORT = Config.SERVICE_PORT
JWT_SECRET = Config.JWT_SECRET
CONSUL_HOST = Config.CONSUL_HOST
CONSUL_PORT = Config.CONSUL_PORT
INTERNAL_API_KEY = Config.INTERNAL_API_KEY
