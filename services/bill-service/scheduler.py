# Bill Service - Scheduler for automatic bill generation
import datetime
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config, INTERNAL_API_KEY, CONSUL_HOST, CONSUL_PORT


def get_service_url(service_name):
# Get service URL from Consul or fallback
    
    try:
        consul_url = f"http://{CONSUL_HOST}:{CONSUL_PORT}/v1/catalog/service/{service_name}"
        response = requests.get(consul_url, timeout=5)
        if response.ok and response.json():
            service = response.json()[0]
            host = service.get('ServiceAddress') or service.get('Address') or service_name
            return f"http://{host}:{service['ServicePort']}"
    except Exception as e:
        print(f"Consul lookup failed: {e}")
    
    # Fallback
    ports = {
        'contract-service': 5006,
        'room-service': 5002,
    }
    return f"http://{service_name}:{ports.get(service_name, 5001)}"


def _compute_next_month_due_date(year, month, day=15):
    # Calculate due date as day X of the NEXT month.
    # Example: Bill for Dec 2025 (month=12) -> Due Jan 5, 2026

    if month == 12:
        next_year = year + 1
        next_month = 1
    else:
        next_year = year
        next_month = month + 1
    
    return f"{next_year}-{next_month:02d}-{day:02d}"


def generate_monthly_bills():
# Generate draft bills for all active contracts on day 1 of each month
    
    from model import bills_collection
    
    now = datetime.datetime.utcnow()
    current_month = f"{now.year}-{now.month:02d}"
    
    print(f"\n{'='*50}")
    print(f"[SCHEDULER] Generating bills for {current_month}")
    print(f"{'='*50}\n")
    
    try:
        # Get all active contracts using internal API
        contract_service_url = get_service_url('contract-service')
        resp = requests.get(
            f"{contract_service_url}/internal/contracts",
            headers={'X-Internal-Api-Key': INTERNAL_API_KEY},
            timeout=10
        )
        
        if not resp.ok:
            print(f"[SCHEDULER] Failed to get contracts: {resp.text}")
            return
        
        contracts = resp.json().get('contracts', [])
        active_contracts = [c for c in contracts if c.get('status') == 'active']
        
        print(f"[SCHEDULER] Found {len(active_contracts)} active contracts")
        
        bills_created = 0
        bills_skipped = 0
        
        for contract in active_contracts:
            contract_id = contract.get('_id')
            room_id = contract.get('room_id')
            user_id = contract.get('user_id')
            monthly_rent = contract.get('monthly_rent', 0)
            start_date_str = contract.get('start_date', '')
            
            # Check if bill already exists for this month
            existing = bills_collection.find_one({
                'contract_id': contract_id,
                'month': current_month
            })
            
            if existing:
                bills_skipped += 1
                continue
            
            # Get room info for electric/water prices
            room_service_url = get_service_url('room-service')
            try:
                room_resp = requests.get(
                    f"{room_service_url}/api/rooms/{room_id}",
                    headers={'X-Internal-Api-Key': INTERNAL_API_KEY},
                    timeout=5
                )
                room = room_resp.json() if room_resp.ok else {}
            except:
                room = {}
            
            # Get previous bill for old meter readings
            prev_bill = bills_collection.find_one(
                {'contract_id': contract_id},
                sort=[('created_at', -1)]
            )
            
            electric_old = prev_bill.get('electric_new', 0) if prev_bill else 0
            water_old = prev_bill.get('water_new', 0) if prev_bill else 0
            
            # Calculate billing days (pro-rata for first month)
            import calendar
            days_in_month = calendar.monthrange(now.year, now.month)[1]
            billing_days = days_in_month
            
            # Check if contract started this month
            try:
                if start_date_str:
                    start_date = datetime.datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                    if start_date.year == now.year and start_date.month == now.month:
                        # Pro-rata: charge from start_date to end of month
                        billing_days = days_in_month - start_date.day + 1
                        print(f"[SCHEDULER] Pro-rata for {contract_id}: {billing_days}/{days_in_month} days")
            except Exception as e:
                print(f"[SCHEDULER] Error parsing start_date: {e}")
            
            # Calculate pro-rata room fee
            room_fee = float(monthly_rent) * billing_days / days_in_month
            
            # Create draft bill
            import uuid
            timestamp = datetime.datetime.utcnow().isoformat() + 'Z'
            bill_id = f"BILL{uuid.uuid4().hex[:8].upper()}"
            
            new_bill = {
                '_id': bill_id,
                'contract_id': contract_id,
                'room_id': room_id,
                'user_id': user_id,
                'month': current_month,
                'billing_days': billing_days,
                'days_in_month': days_in_month,
                'room_fee': round(room_fee, 0),
                'electric_old': electric_old,
                'electric_new': None,  # Admin fills this
                'electric_price': room.get('electricity_price', room.get('electric_price', 3500)),
                'electric_fee': 0,
                'water_old': water_old,
                'water_new': None,  # Admin fills this
                'water_price': room.get('water_price', 15000),
                'water_fee': 0,
                'other_fee': 0,
                'total': round(room_fee, 0),  # Initial = room rent only
                'status': 'draft',  # Draft until admin updates meters
                # Due date is day 5 of NEXT month
                'due_date': _compute_next_month_due_date(now.year, now.month, 5),
                'paid_at': None,
                'created_at': timestamp,
                'auto_generated': True
            }
            
            bills_collection.insert_one(new_bill)
            bills_created += 1
            print(f"[SCHEDULER] Created draft bill {bill_id} for contract {contract_id} ({billing_days} days)")
        
        print(f"\n[SCHEDULER] Summary: {bills_created} created, {bills_skipped} skipped (already exist)")
        
    except Exception as e:
        print(f"[SCHEDULER] Error generating bills: {e}")


def start_scheduler():
# Start the background scheduler
    
    scheduler = BackgroundScheduler()
    
    # Run on day 1 of each month at 00:05 UTC
    scheduler.add_job(
        generate_monthly_bills,
        CronTrigger(day=1, hour=0, minute=5),
        id='monthly_bills',
        name='Generate monthly bills',
        replace_existing=True
    )
    
    scheduler.start()
    print("[SCHEDULER] Started - Bills will be generated on day 1 of each month at 00:05 UTC")
    
    return scheduler


# Manual trigger endpoint helper
def trigger_bill_generation():
# Manually trigger bill generation (for testing/admin use)
    
    generate_monthly_bills()
