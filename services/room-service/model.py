from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_NAME

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
rooms_collection = db[COLLECTION_NAME]

# Tạo index
rooms_collection.create_index('name', unique=True)

def get_rooms_collection():
    """Get rooms collection"""
    return rooms_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client

