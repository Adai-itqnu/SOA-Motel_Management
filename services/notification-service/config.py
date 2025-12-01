import os

# MongoDB configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/notifications_db')

# Service configuration
SERVICE_NAME = "notification-service"
SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5010'))

# JWT configuration (shared secret for verifying user tokens)
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')

# Consul configuration
CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))

# Database configuration
DB_NAME = 'notifications_db'
COLLECTION_NAME = 'notifications'

# Internal API key for trusted service-to-service calls
INTERNAL_API_KEY = os.getenv('INTERNAL_API_KEY', 'internal-api-key-change-me')

