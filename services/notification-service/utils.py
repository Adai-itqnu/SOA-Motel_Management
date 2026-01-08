# Notification Service - Utility Functions
import datetime
import uuid
import os
import requests
from model import notifications_collection
from config import CONSUL_HOST, CONSUL_PORT, INTERNAL_API_KEY


# ============== Service Discovery ==============

def get_service_url(service_name):
    """Get service URL dynamically from Consul."""
    try:
        consul_url = f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(consul_url, timeout=5)
        if response.ok and response.json():
            service = response.json()[0]
            host = service.get('ServiceAddress') or service.get('Address') or service_name
            port = service.get('ServicePort')
            if host and port:
                return f"http://{host}:{port}"
    except Exception as e:
        print(f"[Consul] Error getting {service_name} URL: {e}")
    
    fallback_port = os.getenv(f"{service_name.upper().replace('-', '_')}_PORT", "80")
    return f"http://{service_name}:{fallback_port}"


def fetch_unpaid_bills():
    """Fetch unpaid bills from bill-service."""
    try:
        bill_service_url = get_service_url('bill-service')
        response = requests.get(
            f"{bill_service_url}/internal/bills/unpaid",
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY},
            timeout=10
        )
        if response.ok:
            return response.json().get('bills', [])
    except Exception as e:
        print(f"Error fetching unpaid bills: {e}")
    return []

def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


def generate_notification_id():
# Generate unique notification ID
    
    return f"N{uuid.uuid4().hex[:10]}"


def create_notification_document(data):
# Create a notification document and save to DB
    
    notification = {
        '_id': data.get('_id') or generate_notification_id(),
        'user_id': str(data['user_id']),
        'title': data['title'],
        'message': data['message'],
        'type': data.get('type', 'general'),
        'status': 'unread',
        'metadata': data.get('metadata', {}),
        'created_at': get_timestamp(),
        'read_at': None
    }
    notifications_collection.insert_one(notification)
    notification['id'] = notification['_id']
    return notification


def format_notification(notification):
# Format notification for API response
    
    notification['id'] = notification['_id']
    return notification


def get_user_id(current_user):
# Get user ID from token payload
    
    return str(current_user.get('user_id') or current_user.get('id'))


def check_duplicate_notification(notification_type, bill_id):
# Check if notification already exists
    
    return notifications_collection.find_one({
        'type': notification_type,
        'metadata.bill_id': bill_id
    }) is not None
