# Booking Service Database Models
from pymongo import MongoClient, ASCENDING, DESCENDING
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
    def bookings(self):
        return self._db[Config.COLLECTION_NAME]


_database = Database()
bookings_collection = _database.bookings


def init_indexes():
    try:
        bookings_collection.create_index([('user_id', ASCENDING)])
        bookings_collection.create_index([('room_id', ASCENDING)])
        bookings_collection.create_index([('status', ASCENDING)])
        bookings_collection.create_index([('created_at', DESCENDING)])
        print("[DB] ✓ Booking indexes created")
    except Exception as e:
        print(f"[DB] Index creation: {e}")


init_indexes()
