# Payment Service Database Models
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
    def client(self):
        return self._client
    
    @property
    def db(self):
        return self._db
    
    @property
    def payments(self):
        return self._db[Config.COLLECTION_NAME]


_database = Database()
payments_collection = _database.payments


# Initialize indexes
def init_indexes():
    try:
        # Basic indexes
        payments_collection.create_index([('user_id', ASCENDING)])
        payments_collection.create_index([('bill_id', ASCENDING)])
        payments_collection.create_index([('room_id', ASCENDING)])
        payments_collection.create_index([('status', ASCENDING)])
        payments_collection.create_index([('payment_type', ASCENDING)])
        payments_collection.create_index([('booking_id', ASCENDING)])
        payments_collection.create_index([('created_at', DESCENDING)])
        
        # Provider indexes
        payments_collection.create_index([('provider', ASCENDING)])
        payments_collection.create_index([('transaction_id', ASCENDING)])
        
        # Compound indexes
        payments_collection.create_index([('payment_type', ASCENDING), ('booking_id', ASCENDING)])
        payments_collection.create_index([('bill_id', ASCENDING), ('status', ASCENDING)])
        
        print("[DB] ✓ Payment indexes created")
    except Exception as e:
        print(f"[DB] Index creation: {e}")
    
    # Unique indexes with partial filter
    try:
        payments_collection.create_index(
            [('transaction_id', ASCENDING)],
            unique=True,
            partialFilterExpression={'transaction_id': {'$exists': True, '$ne': None, '$ne': ''}}
        )
    except Exception:
        pass
    
    try:
        payments_collection.create_index(
            [('provider_txn_id', ASCENDING)],
            unique=True,
            partialFilterExpression={'provider_txn_id': {'$exists': True, '$ne': None, '$ne': ''}}
        )
    except Exception:
        pass


init_indexes()


# Utility functions for backward compatibility
def get_payments_collection():
    return payments_collection

def get_db():
    return _database.db

def get_client():
    return _database.client
