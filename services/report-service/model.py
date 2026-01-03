# Report Service Database Models
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
    def bills(self):
        return self._db[Config.COLLECTION_NAME]

_database = Database()
bills_collection = _database.bills

def init_indexes():
    try:
        bills_collection.create_index([('month', ASCENDING), ('year', ASCENDING)])
        bills_collection.create_index([('status', ASCENDING)])
        print("[DB] ✓ Report indexes created")
    except Exception as e:
        print(f"[DB] Index: {e}")

init_indexes()