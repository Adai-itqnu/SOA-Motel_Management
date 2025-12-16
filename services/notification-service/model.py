"""Notification Service Database Models"""
from pymongo import MongoClient, ASCENDING, DESCENDING
from config import Config

class Database:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._client = MongoClient(Config.MONGO_URI)
            cls._db = cls._client[Config.DB_NAME]
        return cls._instance
    
    @property
    def notifications(self):
        return self._db[Config.COLLECTION_NAME]

_database = Database()
notifications_collection = _database.notifications

def init_indexes():
    try:
        notifications_collection.create_index([('user_id', ASCENDING)])
        notifications_collection.create_index([('status', ASCENDING)])
        notifications_collection.create_index([('created_at', DESCENDING)])
        notifications_collection.create_index([('type', ASCENDING)])
        print("[DB] ✓ Notification indexes created")
    except Exception as e:
        print(f"[DB] Index: {e}")

init_indexes()
