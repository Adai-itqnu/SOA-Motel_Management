"""
Booking Service - Utility Functions
"""
import datetime
import uuid


def get_timestamp():
    """Get current UTC timestamp in ISO format"""
    return datetime.datetime.utcnow().isoformat()


def generate_booking_id():
    """Generate unique booking ID"""
    return f"BOOK{uuid.uuid4().hex[:8].upper()}"


def format_booking_response(booking):
    """Format booking data for API response"""
    return {
        '_id': booking['_id'],
        'room_id': booking.get('room_id', ''),
        'user_id': booking.get('user_id', ''),
        'check_in_date': booking.get('check_in_date', ''),
        'message': booking.get('message', ''),
        'deposit_amount': booking.get('deposit_amount', 0),
        'deposit_status': booking.get('deposit_status', 'pending'),
        'deposit_paid_at': booking.get('deposit_paid_at'),
        'payment_method': booking.get('payment_method', 'cash'),
        'status': booking.get('status', 'pending'),
        'admin_note': booking.get('admin_note', ''),
        'created_at': booking.get('created_at'),
        'updated_at': booking.get('updated_at')
    }
