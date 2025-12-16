"""
Auth Service Database Models
MongoDB connection and collection management
"""
from pymongo import MongoClient, ASCENDING
from pymongo.errors import CollectionInvalid
from config import Config


class Database:
    """Database connection singleton"""
    
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
    def users(self):
        return self._db[Config.COLLECTION_NAME]


# Initialize database
_database = Database()

# Export collection for backward compatibility
users_collection = _database.users

# Create indexes
def init_indexes():
    """Initialize database indexes"""
    try:
        users_collection.create_index([('username', ASCENDING)], unique=True)
        users_collection.create_index([('email', ASCENDING)], unique=True)
        users_collection.create_index([('id_card', ASCENDING)], sparse=True)
        users_collection.create_index([('phone', ASCENDING)], sparse=True)
        print("[DB] ✓ Indexes created successfully")
    except Exception as e:
        print(f"[DB] Index creation: {e}")

# Initialize on import
init_indexes()


# Utility functions
def get_users_collection():
    """Get users collection"""
    return users_collection


def get_db():
    """Get database instance"""
    return _database.db


def get_client():
    """Get MongoDB client"""
    return _database.client
