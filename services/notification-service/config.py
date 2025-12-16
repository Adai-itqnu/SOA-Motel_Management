"""Notification Service Configuration"""
import os

class Config:
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/notifications_db')
    DB_NAME = 'notifications_db'
    COLLECTION_NAME = 'notifications'
    SERVICE_NAME = 'notification-service'
    SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5010'))
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')
    CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
    CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))
    INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-secret-key')
    USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://user-service:5003')
    BILL_SERVICE_URL = os.getenv('BILL_SERVICE_URL', 'http://bill-service:5007')
    DEBUG = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

JWT_SECRET = Config.JWT_SECRET
SERVICE_NAME = Config.SERVICE_NAME
SERVICE_PORT = Config.SERVICE_PORT
CONSUL_HOST = Config.CONSUL_HOST
CONSUL_PORT = Config.CONSUL_PORT
INTERNAL_API_KEY = Config.INTERNAL_API_KEY
USER_SERVICE_URL = Config.USER_SERVICE_URL
BILL_SERVICE_URL = Config.BILL_SERVICE_URL
