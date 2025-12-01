from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_NAME

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
payments_collection = db[COLLECTION_NAME]

# Tạo index cho các trường thường query
payments_collection.create_index('bill_id')
payments_collection.create_index('tenant_id')
payments_collection.create_index('payment_date')
payments_collection.create_index('status')

def get_payments_collection():
    """Get payments collection"""
    return payments_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client

