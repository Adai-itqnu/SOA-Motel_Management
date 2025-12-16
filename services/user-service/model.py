"""
User Service Database Model
Uses same database as auth-service
"""
from pymongo import MongoClient, ASCENDING
from config import Config


class Database:
    _instance = None
    _client = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._client = MongoClient(Config.MONGO_URI)
            cls._db = cls._client[Config.DB_NAME]
        return cls._instance
    
    @property
    def db(self):
        return self._db
    
    @property
    def users(self):
        return self._db[Config.COLLECTION_NAME]


_database = Database()
users_collection = _database.users


def init_indexes():
    try:
        users_collection.create_index([('username', ASCENDING)], unique=True)
        users_collection.create_index([('email', ASCENDING)], unique=True)
        users_collection.create_index([('id_card', ASCENDING)], sparse=True)
        print("[DB] ✓ User indexes created")
    except Exception as e:
        print(f"[DB] Index: {e}")


init_indexes()
