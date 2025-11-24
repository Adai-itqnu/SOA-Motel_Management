from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, TENANTS_COLLECTION

# MongoDB connection - Dùng chung database với auth-service
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
# Dùng chung users collection từ auth-service
tenants_collection = db[TENANTS_COLLECTION]  # users collection

# Tạo index unique cho CMND/CCCD (chỉ khi id_card có giá trị)
# Lưu ý: Sparse index để cho phép null/empty
tenants_collection.create_index('id_card', unique=True, sparse=True)

def get_tenants_collection():
    """Get tenants collection"""
    return tenants_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client