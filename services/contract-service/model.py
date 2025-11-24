from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, CONTRACTS_COLLECTION

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
contracts_collection = db[CONTRACTS_COLLECTION]

# Tạo index cho contracts
contracts_collection.create_index('tenant_id')
contracts_collection.create_index('room_id')
contracts_collection.create_index('status')

def get_contracts_collection():
    """Get contracts collection"""
    return contracts_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client

