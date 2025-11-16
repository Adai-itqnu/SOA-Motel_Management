from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_NAME

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
users_collection = db[COLLECTION_NAME]

# Tạo index unique cho username và email
users_collection.create_index('username', unique=True)
users_collection.create_index('email', unique=True)

def get_users_collection():
    """Get users collection"""
    return users_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client

