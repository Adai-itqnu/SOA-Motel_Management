"""Notification Service - Utility Functions"""
import datetime
import uuid
from model import notifications_collection


def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


def generate_notification_id():
    """Generate unique notification ID"""
    return f"N{uuid.uuid4().hex[:10]}"


def create_notification_document(data):
    """Create a notification document and save to DB"""
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
    """Format notification for API response"""
    notification['id'] = notification['_id']
    return notification


def get_user_id(current_user):
    """Get user ID from token payload"""
    return str(current_user.get('user_id') or current_user.get('id'))


def check_duplicate_notification(notification_type, bill_id):
    """Check if notification already exists"""
    return notifications_collection.find_one({
        'type': notification_type,
        'metadata.bill_id': bill_id
    }) is not None
