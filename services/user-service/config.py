"""
User Service Configuration
"""
import os


class Config:
    # MongoDB - uses same database as auth-service
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/users_db')
    DB_NAME = 'users_db'
    COLLECTION_NAME = 'users'
    
    # Service Info
    SERVICE_NAME = 'user-service'
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5003'))
    
    # JWT
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')
    
    # Internal API
    INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-secret-key')
    
    # Consul
    CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))
    
    # Debug
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
