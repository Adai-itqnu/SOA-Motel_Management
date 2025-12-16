from pymongo import MongoClient
from config import MONGO_URI, DB_NAME, COLLECTION_NAME

# MongoDB connection
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
payments_collection = db[COLLECTION_NAME]

# Tạo index cho các trường thường query
payments_collection.create_index('bill_id')
payments_collection.create_index('tenant_id')
payments_collection.create_index('payment_date')
payments_collection.create_index('status')
payments_collection.create_index('booking_id')
payments_collection.create_index('payment_type')
payments_collection.create_index('transaction_id')

# Provider-related & performance indexes
payments_collection.create_index('provider')
payments_collection.create_index('provider_txn_id')
payments_collection.create_index('created_at')
payments_collection.create_index('updated_at')
payments_collection.create_index([('payment_type', 1), ('booking_id', 1)])
payments_collection.create_index([('bill_id', 1), ('status', 1)])

# Ensure we don't accept duplicate provider transaction IDs (idempotency safety)
try:
    payments_collection.create_index(
        [('transaction_id', 1)],
        unique=True,
        partialFilterExpression={'transaction_id': {'$exists': True, '$ne': None, '$ne': ''}},
    )
except Exception:
    # Index may already exist with different options; keep service booting.
    pass

try:
    payments_collection.create_index(
        [('provider_txn_id', 1)],
        unique=True,
        partialFilterExpression={'provider_txn_id': {'$exists': True, '$ne': None, '$ne': ''}},
    )
except Exception:
    pass

def get_payments_collection():
    """Get payments collection"""
    return payments_collection

def get_db():
    """Get database instance"""
    return db

def get_client():
    """Get MongoDB client"""
    return client

