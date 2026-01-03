# Room Service Database Models
from pymongo import MongoClient, ASCENDING
from config import Config


# Database connection singleton
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
    def client(self):
        return self._client
    
    @property
    def db(self):
        return self._db
    
    @property
    def rooms(self):
        return self._db[Config.COLLECTION_NAME]


# Initialize database
_database = Database()
rooms_collection = _database.rooms


# Initialize database indexes
def init_indexes():
    try:
        rooms_collection.create_index([('name', ASCENDING)], unique=True)
        rooms_collection.create_index([('status', ASCENDING)])
        rooms_collection.create_index([('user_id', ASCENDING)], sparse=True)
        print("[DB] ✓ Room indexes created")
    except Exception as e:
        print(f"[DB] Index creation: {e}")


init_indexes()


# Utility functions
def get_rooms_collection():
    return rooms_collection


def get_db():
    return _database.db


def get_client():
    return _database.client
