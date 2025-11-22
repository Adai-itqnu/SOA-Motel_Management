from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, TENANTS_COLLECTION, CONTRACTS_COLLECTION

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
tenants_collection = db[TENANTS_COLLECTION]
contracts_collection = db[CONTRACTS_COLLECTION]

# Tạo index unique cho CMND/CCCD
tenants_collection.create_index('id_card', unique=True)

# Tạo index cho contracts
contracts_collection.create_index('tenant_id')
contracts_collection.create_index('room_id')
contracts_collection.create_index('status')

def get_tenants_collection():
    """Get tenants collection"""
    return tenants_collection

def get_contracts_collection():
    """Get contracts collection"""
    return contracts_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client