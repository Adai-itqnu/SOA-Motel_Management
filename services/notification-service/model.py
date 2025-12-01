from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_NAME

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
notifications_collection = db[COLLECTION_NAME]

# Useful indexes
notifications_collection.create_index('user_id')
notifications_collection.create_index('status')
notifications_collection.create_index('type')
notifications_collection.create_index('metadata.bill_id')

def get_notifications_collection():
    return notifications_collection

def get_db():
    return db

def get_client():
    return client

