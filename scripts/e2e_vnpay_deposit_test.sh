#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://localhost}
RUN_ID=${RUN_ID:-$(date +%s)}
USERNAME=${USERNAME:-e2e_user_$RUN_ID}
PASSWORD=${PASSWORD:-password}
EMAIL=${EMAIL:-e2e_user_$RUN_ID@example.com}
FULLNAME=${FULLNAME:-E2E User}
DEPOSIT_AMOUNT=${DEPOSIT_AMOUNT:-100000}
ROOM_ID=${ROOM_ID:-R-DEMO}
CHECK_IN_DATE=${CHECK_IN_DATE:-2025-12-20}

# Read VNPay config from running container (fallback to compose defaults)
VNPAY_HASH_SECRET=$(docker inspect payment-service --format '{{range .Config.Env}}{{println .}}{{end}}' | awk -F= '/^VNPAY_HASH_SECRET=/{print $2; exit}')
VNPAY_TMN_CODE=$(docker inspect payment-service --format '{{range .Config.Env}}{{println .}}{{end}}' | awk -F= '/^VNPAY_TMN_CODE=/{print $2; exit}')

if [[ -z "${VNPAY_HASH_SECRET:-}" ]]; then VNPAY_HASH_SECRET=YOUR_HASH_SECRET; fi
if [[ -z "${VNPAY_TMN_CODE:-}" ]]; then VNPAY_TMN_CODE=YOUR_TMN_CODE; fi

echo "Using BASE_URL=$BASE_URL"
echo "Using VNPAY_TMN_CODE=$VNPAY_TMN_CODE"

# 1) Register (should be unique by default)
curl -s -X POST "$BASE_URL/api/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\",\"email\":\"$EMAIL\",\"fullname\":\"$FULLNAME\"}" \
  | cat

echo

# 2) Login
TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" \
  | python -c "import sys, json; print(json.load(sys.stdin).get('token',''))")

if [[ -z "$TOKEN" ]]; then
  echo "Login failed" >&2
  exit 1
fi

echo "TOKEN_LEN=${#TOKEN}"

# 3) Create booking
BOOKING_ID=$(curl -s -X POST "$BASE_URL/api/bookings" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"room_id\":\"$ROOM_ID\",\"check_in_date\":\"$CHECK_IN_DATE\",\"deposit_amount\":$DEPOSIT_AMOUNT,\"message\":\"demo vnpay\"}" \
  | python -c "import sys, json; d=json.load(sys.stdin); print(d.get('booking',{}).get('_id',''))")

if [[ -z "$BOOKING_ID" ]]; then
  echo "Create booking failed" >&2
  exit 1
fi

echo "BOOKING_ID=$BOOKING_ID"

# 4) Create VNPay deposit payment
PAYMENT_JSON=$(curl -s -X POST "$BASE_URL/api/payments/vnpay/deposit/create" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"booking_id\":\"$BOOKING_ID\"}")

echo "$PAYMENT_JSON" | cat
PAYMENT_ID=$(echo "$PAYMENT_JSON" | python -c "import sys, json; print(json.load(sys.stdin).get('payment_id',''))")

if [[ -z "$PAYMENT_ID" ]]; then
  echo "Create VNPay payment failed" >&2
  exit 1
fi

echo "PAYMENT_ID=$PAYMENT_ID"

# 5) Simulate VNPay IPN with valid signature
IPN_QS=$(python - <<PY
import urllib.parse, hmac, hashlib, time
secret = "${VNPAY_HASH_SECRET}"
tmn = "${VNPAY_TMN_CODE}"
payment_id = "${PAYMENT_ID}"
amount = int(${DEPOSIT_AMOUNT}) * 100
params = {
  'vnp_Amount': str(amount),
  'vnp_BankCode': 'NCB',
  'vnp_Command': 'pay',
  'vnp_ResponseCode': '00',
  'vnp_TmnCode': tmn,
  'vnp_TransactionNo': '123456789',
  'vnp_TxnRef': payment_id,
  'vnp_Version': '2.1.0',
  'vnp_PayDate': time.strftime('%Y%m%d%H%M%S'),
}
qs = urllib.parse.urlencode(sorted(params.items()), quote_via=urllib.parse.quote_plus)
sig = hmac.new(secret.encode('utf-8'), qs.encode('utf-8'), hashlib.sha512).hexdigest()
params['vnp_SecureHashType'] = 'HmacSHA512'
params['vnp_SecureHash'] = sig
print(urllib.parse.urlencode(sorted(params.items()), quote_via=urllib.parse.quote_plus))
PY
)

echo "Calling IPN..."
IPN_RESP=$(curl -s "$BASE_URL/api/payments/vnpay/ipn?$IPN_QS")
echo "$IPN_RESP" | cat

echo

# 6) Verify booking now shows deposit paid
BOOKING=$(curl -s "$BASE_URL/api/bookings/$BOOKING_ID" -H "Authorization: Bearer $TOKEN")
echo "$BOOKING" | cat

echo

echo "OK: VNPay deposit flow simulated successfully"
