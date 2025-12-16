"""
Auth Service Configuration
Centralized configuration management using environment variables
"""
import os


class Config:
    """Application configuration class"""
    
    # MongoDB
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/users_db')
    DB_NAME = 'users_db'
    COLLECTION_NAME = 'users'
    
    # Service Info
    SERVICE_NAME = 'auth-service'
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5001'))
    
    # JWT
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')
    JWT_EXPIRY_HOURS = int(os.getenv('JWT_EXPIRY_HOURS', '24'))
    
    # Consul
    CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))
    
    # Internal API
    INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-secret-key')
    NOTIFICATION_SERVICE_URL = os.getenv('NOTIFICATION_SERVICE_URL', 'http://notification-service:5008')
    
    # Debug
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'


# Backward compatibility - export as module-level constants
MONGO_URI = Config.MONGO_URI
DB_NAME = Config.DB_NAME
COLLECTION_NAME = Config.COLLECTION_NAME
SERVICE_NAME = Config.SERVICE_NAME
SERVICE_PORT = Config.SERVICE_PORT
JWT_SECRET = Config.JWT_SECRET
CONSUL_HOST = Config.CONSUL_HOST
CONSUL_PORT = Config.CONSUL_PORT
