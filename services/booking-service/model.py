from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, BOOKINGS_COLLECTION

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
bookings_collection = db[BOOKINGS_COLLECTION]

# Tạo index cho bookings
bookings_collection.create_index('user_id')
bookings_collection.create_index('tenant_id')
bookings_collection.create_index('room_id')
bookings_collection.create_index('status')

def get_bookings_collection():
    """Get bookings collection"""
    return bookings_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client

