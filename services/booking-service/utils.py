# Booking Service - Utility Functions
import datetime
import uuid
from model import bookings_collection


# ============== ID & Timestamp ==============

# Get current UTC timestamp in ISO format
def get_timestamp():
    return datetime.datetime.utcnow().isoformat()


# Generate unique booking ID
def generate_booking_id():
    return f"BOOK{uuid.uuid4().hex[:8].upper()}"


# ============== Booking Formatting ==============

# Format booking data for API response
def format_booking_response(booking):
    return {
        '_id': booking['_id'],
        'room_id': booking.get('room_id', ''),
        'user_id': booking.get('user_id', ''),
        'check_in_date': booking.get('check_in_date', ''),
        'message': booking.get('message', ''),
        'deposit_amount': booking.get('deposit_amount', 0),
        'deposit_status': booking.get('deposit_status', 'pending'),
        'deposit_paid_at': booking.get('deposit_paid_at'),
        'deposit_payment_id': booking.get('deposit_payment_id'),
        'payment_method': booking.get('payment_method', 'cash'),
        'status': booking.get('status', 'pending'),
        'admin_note': booking.get('admin_note', ''),
        'checked_in_at': booking.get('checked_in_at'),
        'created_at': booking.get('created_at'),
        'updated_at': booking.get('updated_at')
    }


# ============== User Helpers ==============

# Get user ID from token payload
def get_user_id(current_user):
    return current_user.get('user_id') or current_user.get('_id')


# Check if user can access booking
def can_access_booking(current_user, booking):
    user_id = get_user_id(current_user)
    role = current_user.get('role', '')
    return role == 'admin' or booking['user_id'] == user_id


# Check if user owns the booking
def is_booking_owner(current_user, booking):
    user_id = get_user_id(current_user)
    return booking['user_id'] == user_id


# ============== Validation ==============

# Validate required fields for booking creation
def validate_booking_data(data):
    required = ['room_id', 'check_in_date']
    missing = [f for f in required if not data.get(f)]
    return missing


# Check if booking can be cancelled
def can_cancel_booking(booking):
    return booking['status'] not in ['checked_in', 'cancelled']


# Check if deposit is paid
def is_deposit_paid(booking):
    return booking.get('deposit_status') == 'paid' or booking.get('status') == 'deposit_paid'


# Check if already checked in
def is_checked_in(booking):
    return booking.get('status') == 'checked_in'


# ============== Document Creation ==============

# Create new booking document from data
def create_booking_document(data, user_id):
    timestamp = get_timestamp()
    return {
        '_id': generate_booking_id(),
        'room_id': data['room_id'],
        'user_id': user_id,
        'check_in_date': data['check_in_date'],
        'message': data.get('message', ''),
        'deposit_amount': float(data.get('deposit_amount', 0)),
        'deposit_status': 'pending',
        'deposit_paid_at': None,
        'payment_method': data.get('payment_method', 'cash'),
        'status': 'pending',
        'admin_note': '',
        'created_at': timestamp,
        'updated_at': timestamp
    }


# Create checked-in booking document from payment
def create_checkin_booking_document(room_id, user_id, payment_id, check_in_date=None):
    timestamp = get_timestamp()
    return {
        '_id': generate_booking_id(),
        'room_id': room_id,
        'user_id': user_id,
        'check_in_date': check_in_date or timestamp[:10],
        'deposit_amount': 0,
        'deposit_status': 'paid',
        'deposit_payment_id': payment_id,
        'payment_method': 'vnpay',
        'status': 'checked_in',
        'checked_in_at': timestamp,
        'admin_note': 'Check-in từ thanh toán VNPay',
        'created_at': timestamp,
        'updated_at': timestamp
    }


# Create booking document from payment (internal)
def create_booking_from_payment_data(data):
    timestamp = get_timestamp()
    return {
        '_id': generate_booking_id(),
        'room_id': data.get('room_id'),
        'user_id': data.get('user_id'),
        'check_in_date': data.get('check_in_date') or timestamp[:10],
        'deposit_amount': data.get('deposit_amount', 0),
        'deposit_status': 'paid',
        'deposit_paid_at': timestamp,
        'deposit_payment_id': data.get('deposit_payment_id'),
        'payment_method': data.get('payment_method', 'vnpay'),
        'status': 'deposit_paid',
        'created_at': timestamp,
        'updated_at': timestamp
    }


# ============== Database Queries ==============

# Find existing pending booking for room and user
def find_pending_booking(room_id, user_id):
    return bookings_collection.find_one({
        'room_id': room_id,
        'user_id': user_id,
        'status': {'$in': ['pending', 'deposit_paid']}
    })
