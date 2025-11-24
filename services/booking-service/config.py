import os

# MongoDB configuration - Dùng chung database với auth-service
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/users_db')

# Service configuration
SERVICE_NAME = "booking-service"
SERVICE_PORT = int(os.getenv('SERVICE_PORT', '5005'))

# JWT configuration
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-key-change-this')

# Consul configuration
CONSUL_HOST = os.getenv('CONSUL_HOST', 'localhost')
CONSUL_PORT = int(os.getenv('CONSUL_PORT', '8500'))

# Database configuration
DB_NAME = 'users_db'
BOOKINGS_COLLECTION = 'bookings'

