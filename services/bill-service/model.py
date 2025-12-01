from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_NAME

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
bills_collection = db[COLLECTION_NAME]

# Tạo index cho các trường thường query
bills_collection.create_index('tenant_id')
bills_collection.create_index('room_id')
bills_collection.create_index('month')
bills_collection.create_index('status')
bills_collection.create_index([('tenant_id', 1), ('month', 1)], unique=True)

def get_bills_collection():
    """Get bills collection"""
    return bills_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client

