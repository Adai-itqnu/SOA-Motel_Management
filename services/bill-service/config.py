# Bill Service Configuration
import os

class Config:
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/bills_db')
    DB_NAME = 'bills_db'
    COLLECTION_NAME = 'bills'
    SERVICE_NAME = 'bill-service'
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5007'))
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')
    CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))
    INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-secret-key')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

MONGO_URI = Config.MONGO_URI
SERVICE_NAME = Config.SERVICE_NAME
SERVICE_PORT = Config.SERVICE_PORT
JWT_SECRET = Config.JWT_SECRET
CONSUL_HOST = Config.CONSUL_HOST
CONSUL_PORT = Config.CONSUL_PORT
INTERNAL_API_KEY = Config.INTERNAL_API_KEY
