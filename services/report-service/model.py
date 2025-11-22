from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, BILLS_COLLECTION

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
bills_collection = db[BILLS_COLLECTION]

# Tạo index cho bills
bills_collection.create_index('contract_id')
bills_collection.create_index('room_id')
bills_collection.create_index('status')
bills_collection.create_index([('month', 1), ('year', 1)])

def get_bills_collection():
    """Get bills collection"""
    return bills_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client