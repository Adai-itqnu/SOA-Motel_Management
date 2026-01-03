# Contract Service Database Models
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
    def contracts(self):
        return self._db[Config.COLLECTION_NAME]

_database = Database()
contracts_collection = _database.contracts

def init_indexes():
    try:
        contracts_collection.create_index([('user_id', ASCENDING)])
        contracts_collection.create_index([('room_id', ASCENDING)])
        contracts_collection.create_index([('status', ASCENDING)])
        contracts_collection.create_index([('created_at', DESCENDING)])
        print("[DB] ✓ Contract indexes created")
    except Exception as e:
        print(f"[DB] Index creation: {e}")

init_indexes()
