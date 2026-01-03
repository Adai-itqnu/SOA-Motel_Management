# Bill Service - External Service Calls
import requests
import calendar
import datetime
from config import Config


def get_service_url(service_name):
# Get service URL from Consul
    
    try:
        url = f"http://{Config.CONSUL_HOST}:{Config.CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(url, timeout=5)
        if response.ok and response.json():
            svc = response.json()[0]
            return f"http://{svc['ServiceAddress']}:{svc['ServicePort']}"
    except:
        pass
    
    ports = {'room-service': 5002, 'user-service': 5003, 'notification-service': 5010}
    return f"http://{service_name}:{ports.get(service_name, 5001)}"


def fetch_service_data(service_name, endpoint, token=None):
# Fetch data from other service
    
    try:
        url = get_service_url(service_name)
        headers = {}
        if token:
            if not token.startswith('Bearer '):
                token = f'Bearer {token}'
            headers['Authorization'] = token
        
        response = requests.get(f"{url}{endpoint}", headers=headers, timeout=10)
        return response.json() if response.ok else None
    except Exception as e:
        print(f"Error fetching from {service_name}: {e}")
        return None


def send_notification(user_id, title, message, notification_type, metadata=None):
# Send notification via notification-service
    
    try:
        url = get_service_url('notification-service')
        response = requests.post(
            f"{url}/api/notifications",
            json={
                'user_id': str(user_id),
                'title': title,
                'message': message,
                'type': notification_type,
                'metadata': metadata or {}
            },
            headers={
                'X-Internal-Api-Key': Config.INTERNAL_API_KEY,
                'Content-Type': 'application/json'
            },
            timeout=5
        )
        return response.ok
    except Exception as e:
        print(f"Error sending notification: {e}")
        return False


def compute_due_date(month_str, payment_day=5):
    """Return ISO date string for due date (day X of NEXT month).
    
    Example: Bill for "2025-12" → Due "2026-01-05"
    """
    try:
        base_date = datetime.datetime.strptime(month_str + "-01", "%Y-%m-%d")
        # Move to next month
        if base_date.month == 12:
            next_year = base_date.year + 1
            next_month = 1
        else:
            next_year = base_date.year
            next_month = base_date.month + 1
        
        # Ensure payment_day is valid for that month
        last_day = calendar.monthrange(next_year, next_month)[1]
        target_day = min(max(1, int(payment_day)), last_day)
        
        return f"{next_year}-{next_month:02d}-{target_day:02d}"
    except:
        # Fallback: just add "-15" to month_str for next month
        return month_str + "-15"
