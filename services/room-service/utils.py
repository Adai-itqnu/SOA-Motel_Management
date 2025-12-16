"""
Room Service - Utility Functions
"""
import datetime
import uuid
from config import Config
from model import rooms_collection


def generate_room_id():
    """Generate unique room ID"""
    while True:
        room_id = f"ROOM{uuid.uuid4().hex[:8].upper()}"
        if not rooms_collection.find_one({'_id': room_id}):
            return room_id


def get_timestamp():
    """Get current UTC timestamp in ISO format"""
    return datetime.datetime.utcnow().isoformat()


def format_room_response(room, include_sensitive=True):
    """Format room data for API response"""
    raw_images = room.get('images') or []
    if not isinstance(raw_images, list):
        raw_images = []

    # Convert base64 objects to data URL strings
    images = []
    for img in raw_images:
        if isinstance(img, str):
            # Already a string (URL or data URL)
            images.append(img)
        elif isinstance(img, dict):
            # Convert {content_type, data_b64} to data URL
            content_type = img.get('content_type', 'image/jpeg')
            data_b64 = img.get('data_b64') or img.get('data')
            if data_b64:
                images.append(f"data:{content_type};base64,{data_b64}")

    # For public endpoints, keep payload small: include at most 1 image.
    if not include_sensitive:
        images = images[:1]

    data = {
        '_id': room['_id'],
        'name': room.get('name', ''),
        'room_type': room.get('room_type', ''),
        'price': room.get('price', 0),
        'deposit': room.get('deposit', 0),
        'electricity_price': room.get('electricity_price') or room.get('electric_price', Config.DEFAULT_ELECTRIC_PRICE),
        'water_price': room.get('water_price', Config.DEFAULT_WATER_PRICE),
        'description': room.get('description', ''),
        'area': room.get('area') or room.get('area_m2', 0),
        'floor': room.get('floor', 1),
        'amenities': room.get('amenities') or [],
        'images': images,
        'status': room.get('status', Config.STATUS_AVAILABLE),
        'current_contract_id': room.get('current_contract_id'),
        'reserved_by_tenant_id': room.get('reserved_by_tenant_id'),
        'reserved_payment_id': room.get('reserved_payment_id'),
        'reservation_status': room.get('reservation_status'),
        'reserved_at': room.get('reserved_at'),
        'created_at': room.get('created_at'),
        'updated_at': room.get('updated_at')
    }

    if not include_sensitive:
        data.pop('electricity_price', None)
        data.pop('water_price', None)
        data.pop('current_contract_id', None)
        data.pop('reserved_by_tenant_id', None)
        data.pop('reserved_payment_id', None)
        data.pop('reservation_status', None)
        data.pop('reserved_at', None)
        data.pop('created_at', None)
        data.pop('updated_at', None)

    return data


def check_duplicate_room_name(name, exclude_room_id=None):
    """Check if room name already exists"""
    query = {'name': name}
    if exclude_room_id:
        query['_id'] = {'$ne': exclude_room_id}
    return rooms_collection.find_one(query) is not None
