from __future__ import annotations

import datetime
import os
import uuid

from flask import Flask, jsonify, redirect, request
from flask_cors import CORS

from config import Config
from model import payments_collection
from service_registry import register_service
from decorators import token_required, admin_required, internal_api_required
from utils import (
    auto_create_contract,
    calculate_total_paid,
    check_user_has_active_contract,
    confirm_room_reservation,
    fetch_service_data,
    hold_room_reservation,
    release_room_reservation,
    update_bill_status_if_paid,
    update_booking_deposit_status,
    send_notification,
)
from vnpay import build_payment_url, querydr_verify_transaction, validate_return_or_ipn


def _utc_now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _today_str() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _get_client_ip() -> str:
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote_addr
        or "127.0.0.1"
    )


app = Flask(__name__)
CORS(app)

app.config["SECRET_KEY"] = Config.JWT_SECRET
app.config["SERVICE_NAME"] = Config.SERVICE_NAME
app.config["SERVICE_PORT"] = Config.SERVICE_PORT


# ---------------------------
# Health
# ---------------------------


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": app.config["SERVICE_NAME"]}), 200


# ---------------------------
# Payments API (bill payments)
# ---------------------------


@app.route("/api/payments", methods=["POST"])
@token_required
def create_payment(current_user):
    data = request.get_json() or {}

    required_fields = ["bill_id", "amount", "method"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"message": f"Thiếu trường {', '.join(missing)}!"}), 400

    valid_methods = ["cash", "bank_transfer", "momo", "vnpay"]
    if data["method"] not in valid_methods:
        return (
            jsonify(
                {
                    "message": "Phương thức thanh toán không hợp lệ! Chỉ chấp nhận: "
                    + ", ".join(valid_methods)
                }
            ),
            400,
        )

    try:
        amount = float(data["amount"])
    except Exception:
        return jsonify({"message": "Số tiền không hợp lệ!"}), 400
    if amount <= 0:
        return jsonify({"message": "Số tiền phải lớn hơn 0!"}), 400

    status = data.get("status") or "pending"
    valid_statuses = ["pending", "completed", "failed"]
    if status not in valid_statuses:
        return (
            jsonify(
                {
                    "message": f"Status không hợp lệ! Chỉ chấp nhận: {', '.join(valid_statuses)}"
                }
            ),
            400,
        )

    bill_id = data["bill_id"]

    token = request.headers.get("Authorization") or request.headers.get("authorization")
    bill_data = fetch_service_data("bill-service", f"/api/bills/{bill_id}", token)
    if not bill_data:
        return jsonify({"message": "Hóa đơn không tồn tại!"}), 404

    bill = bill_data if isinstance(bill_data, dict) else bill_data.get("bill", bill_data)
    if bill.get("status") == "paid":
        return jsonify({"message": "Hóa đơn đã được thanh toán đầy đủ!"}), 400

    bill_total = float(bill.get("total_amount") or bill.get("total") or 0)
    total_paid = calculate_total_paid(bill_id)
    remaining_amount = bill_total - float(total_paid)
    if amount > remaining_amount:
        return (
            jsonify(
                {
                    "message": f"Số tiền thanh toán ({amount:,.0f}) vượt quá số tiền còn lại ({remaining_amount:,.0f})!"
                }
            ),
            400,
        )

    payment_id = f"P{uuid.uuid4().hex[:10].upper()}"
    while payments_collection.find_one({"_id": payment_id}):
        payment_id = f"P{uuid.uuid4().hex[:10].upper()}"

    user_id = data.get("user_id")
    if current_user.get("role") != "admin":
        user_id = current_user.get("user_id") or current_user.get("_id")

    payment_date = data.get("payment_date") or _today_str()

    new_payment = {
        "_id": payment_id,
        "payment_type": "bill_payment",
        "bill_id": bill_id,
        "user_id": user_id,
        "amount": amount,
        "currency": "VND",
        "method": data["method"],
        "payment_date": payment_date,
        "status": status,
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }

    try:
        payments_collection.insert_one(new_payment)
        if status == "completed":
            update_bill_status_if_paid(bill_id, bill_total)
        new_payment["id"] = new_payment["_id"]
        return jsonify({"message": "Tạo thanh toán thành công!", "payment": new_payment}), 201
    except Exception as e:
        return jsonify({"message": f"Lỗi tạo thanh toán: {str(e)}"}), 500


@app.route("/api/payments", methods=["GET"])
@token_required
def get_payments(current_user):
    bill_id = request.args.get("bill_id")
    room_id = request.args.get("room_id")
    booking_id = request.args.get("booking_id")
    user_id = request.args.get("user_id")
    payment_date = request.args.get("payment_date")
    status = request.args.get("status")
    payment_type = request.args.get("payment_type")

    query: dict = {}
    if bill_id:
        query["bill_id"] = bill_id
    if room_id:
        query["room_id"] = room_id
    if booking_id:
        query["booking_id"] = booking_id
    if user_id:
        query["user_id"] = user_id
    if payment_date:
        query["payment_date"] = payment_date
    if status:
        query["status"] = status
    if payment_type:
        query["payment_type"] = payment_type

    if current_user.get("role") != "admin":
        query["user_id"] = current_user.get("user_id") or current_user.get("_id")

    payments = list(payments_collection.find(query).sort("payment_date", -1))
    for p in payments:
        p["id"] = p.get("_id")

    return jsonify({"payments": payments, "total": len(payments)}), 200


@app.route("/api/payments/<payment_id>", methods=["GET"])
@token_required
def get_payment(current_user, payment_id):
    payment = payments_collection.find_one({"_id": payment_id})
    if not payment:
        return jsonify({"message": "Thanh toán không tồn tại!"}), 404

    if current_user.get("role") != "admin":
        if payment.get("user_id") != (current_user.get("user_id") or current_user.get("_id")):
            return jsonify({"message": "Không có quyền xem thanh toán này!"}), 403

    payment["id"] = payment.get("_id")
    return jsonify(payment), 200


@app.route("/api/payments/bill/<bill_id>", methods=["GET"])
@token_required
def get_payments_by_bill(current_user, bill_id):
    payments = list(payments_collection.find({"bill_id": bill_id}).sort("payment_date", -1))
    total_paid = calculate_total_paid(bill_id)

    token = request.headers.get("Authorization") or request.headers.get("authorization")
    bill_data = fetch_service_data("bill-service", f"/api/bills/{bill_id}", token)
    bill = (
        bill_data
        if isinstance(bill_data, dict)
        else bill_data.get("bill", bill_data)
        if bill_data
        else {}
    )

    total_amount = float(bill.get("total_amount") or bill.get("total") or 0)
    remaining_amount = total_amount - float(total_paid)

    for p in payments:
        p["id"] = p.get("_id")

    return (
        jsonify(
            {
                "payments": payments,
                "total": len(payments),
                "total_paid": total_paid,
                "total_amount": total_amount,
                "remaining_amount": remaining_amount,
            }
        ),
        200,
    )


@app.route("/api/payments/<payment_id>", methods=["PUT"])
@token_required
@admin_required
def update_payment(current_user, payment_id):
    payment = payments_collection.find_one({"_id": payment_id})
    if not payment:
        return jsonify({"message": "Thanh toán không tồn tại!"}), 404

    data = request.get_json() or {}
    update_fields = {}

    if "amount" in data:
        try:
            amount = float(data["amount"])
        except Exception:
            return jsonify({"message": "Số tiền không hợp lệ!"}), 400
        if amount <= 0:
            return jsonify({"message": "Số tiền phải lớn hơn 0!"}), 400
        update_fields["amount"] = amount

    if "status" in data:
        valid_statuses = ["pending", "completed", "failed"]
        if data["status"] not in valid_statuses:
            return (
                jsonify(
                    {
                        "message": f"Status không hợp lệ! Chỉ chấp nhận: {', '.join(valid_statuses)}"
                    }
                ),
                400,
            )
        update_fields["status"] = data["status"]

    if "method" in data:
        valid_methods = ["cash", "bank_transfer", "momo", "vnpay"]
        if data["method"] not in valid_methods:
            return (
                jsonify(
                    {
                        "message": "Phương thức thanh toán không hợp lệ! Chỉ chấp nhận: "
                        + ", ".join(valid_methods)
                    }
                ),
                400,
            )
        update_fields["method"] = data["method"]

    if "payment_date" in data:
        update_fields["payment_date"] = data["payment_date"]

    if not update_fields:
        return jsonify({"message": "Không có trường nào để cập nhật!"}), 400

    update_fields["updated_at"] = _utc_now_iso()

    payments_collection.update_one({"_id": payment_id}, {"$set": update_fields})
    updated = payments_collection.find_one({"_id": payment_id})
    updated["id"] = updated.get("_id")

    if update_fields.get("status") == "completed" and updated.get("bill_id"):
        token = request.headers.get("Authorization") or request.headers.get("authorization")
        bill_data = fetch_service_data("bill-service", f"/api/bills/{updated['bill_id']}", token)
        if bill_data:
            bill = bill_data if isinstance(bill_data, dict) else bill_data.get("bill", bill_data)
            bill_total = float(bill.get("total_amount") or bill.get("total") or 0)
            update_bill_status_if_paid(updated["bill_id"], bill_total)

    return jsonify({"message": "Cập nhật thanh toán thành công!", "payment": updated}), 200


@app.route("/api/payments/statistics", methods=["GET"])
@token_required
@admin_required
def get_payment_statistics(current_user):
    total_payments = payments_collection.count_documents({})

    pipeline_total = [
        {"$match": {"status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    result_total = list(payments_collection.aggregate(pipeline_total))
    total_amount = result_total[0]["total"] if result_total else 0

    pipeline_status = [
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"},
            }
        }
    ]
    status_stats = list(payments_collection.aggregate(pipeline_status))

    pipeline_method = [
        {
            "$group": {
                "_id": "$method",
                "count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"},
            }
        }
    ]
    method_stats = list(payments_collection.aggregate(pipeline_method))

    thirty_days_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).strftime(
        "%Y-%m-%d"
    )
    recent_payments = payments_collection.count_documents(
        {"payment_date": {"$gte": thirty_days_ago}, "status": "completed"}
    )

    pipeline_recent = [
        {"$match": {"payment_date": {"$gte": thirty_days_ago}, "status": "completed"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    result_recent = list(payments_collection.aggregate(pipeline_recent))
    recent_amount = result_recent[0]["total"] if result_recent else 0

    return (
        jsonify(
            {
                "total_payments": total_payments,
                "total_amount": total_amount,
                "recent_payments_30days": recent_payments,
                "recent_amount_30days": recent_amount,
                "by_status": {
                    stat["_id"]: {"count": stat["count"], "total_amount": stat["total_amount"]}
                    for stat in status_stats
                },
                "by_method": {
                    stat["_id"]: {"count": stat["count"], "total_amount": stat["total_amount"]}
                    for stat in method_stats
                },
            }
        ),
        200,
    )


@app.route("/api/payments/deposit", methods=["POST"])
@token_required
def create_deposit_payment(current_user):
    data = request.get_json() or {}

    required_fields = ["amount", "payment_type"]
    missing = [f for f in required_fields if not data.get(f)]
    if missing:
        return jsonify({"message": f"Thiếu trường {', '.join(missing)}!"}), 400

    if data["payment_type"] not in ["booking", "contract"]:
        return jsonify({"message": 'payment_type phải là "booking" hoặc "contract"!'}), 400

    if data["payment_type"] == "booking" and not data.get("booking_id"):
        return jsonify({"message": "Thiếu trường booking_id!"}), 400
    if data["payment_type"] == "contract" and not data.get("contract_id"):
        return jsonify({"message": "Thiếu trường contract_id!"}), 400

    try:
        amount = float(data["amount"])
    except Exception:
        return jsonify({"message": "Số tiền không hợp lệ!"}), 400
    if amount <= 0:
        return jsonify({"message": "Số tiền phải lớn hơn 0!"}), 400

    user_id = current_user.get("user_id") or current_user.get("_id")
    if not user_id:
        return jsonify({"message": "Không tìm thấy user_id!"}), 400

    payment_id = f"P{uuid.uuid4().hex[:10].upper()}"
    while payments_collection.find_one({"_id": payment_id}):
        payment_id = f"P{uuid.uuid4().hex[:10].upper()}"

    new_payment = {
        "_id": payment_id,
        "payment_type": data["payment_type"],
        "booking_id": data.get("booking_id"),
        "contract_id": data.get("contract_id"),
        "bill_id": None,
        "user_id": user_id,
        "amount": amount,
        "currency": "VND",
        "method": "vnpay",
        "payment_date": _today_str(),
        "status": "pending",
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }

    payments_collection.insert_one(new_payment)
    new_payment["id"] = new_payment["_id"]
    return jsonify({"message": "Tạo payment tiền cọc thành công!", "payment": new_payment}), 201


# ---------------------------
# VNPay deposit flow (booking)
# ---------------------------


@app.route("/api/payments/vnpay/deposit/create", methods=["POST"])
@token_required
def vnpay_create_deposit(current_user):
    data = request.get_json() or {}
    booking_id = data.get("booking_id")
    if not booking_id:
        return jsonify({"message": "Missing booking_id"}), 400

    token = request.headers.get("Authorization") or request.headers.get("authorization")
    booking = fetch_service_data("booking-service", f"/api/bookings/{booking_id}", token)
    if not booking:
        return jsonify({"message": "Booking không tồn tại hoặc không có quyền!"}), 404

    deposit_amount = float(booking.get("deposit_amount") or 0)
    deposit_status = booking.get("deposit_status")
    if deposit_amount <= 0:
        return jsonify({"message": "Booking không có tiền cọc để thanh toán!"}), 400
    if deposit_status == "paid":
        return jsonify({"message": "Booking đã thanh toán cọc rồi!"}), 400

    deposit_amount_vnd = int(round(deposit_amount))

    payment_id = f"PAY{uuid.uuid4().hex[:10].upper()}"
    payment_doc = {
        "_id": payment_id,
        "payment_type": "booking_deposit",
        "booking_id": booking_id,
        "user_id": booking.get("user_id"),
        "amount": float(deposit_amount_vnd),
        "amount_vnd": deposit_amount_vnd,
        "currency": "VND",
        "method": "vnpay",
        "provider": "vnpay",
        "status": "pending",
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }
    payments_collection.insert_one(payment_doc)

    order_info = f"Thanh toan coc booking {booking_id}"
    payment_url = build_payment_url(
        base_url=Config.VNPAY_URL,
        tmn_code=Config.VNPAY_TMN_CODE,
        secret=Config.VNPAY_HASH_SECRET,
        txn_ref=payment_id,
        amount_vnd=deposit_amount_vnd,
        order_info=order_info,
        return_url=Config.VNPAY_RETURN_URL,
        ipn_url=Config.VNPAY_IPN_URL or None,
        client_ip=_get_client_ip(),
    )

    return jsonify({"payment_url": payment_url, "payment_id": payment_id, "booking_id": booking_id})


# ---------------------------
# VNPay bill payment flow
# ---------------------------


@app.route("/api/payments/vnpay/bill/create", methods=["POST"])
@token_required
def vnpay_create_bill_payment(current_user):
    data = request.get_json() or {}
    bill_id = data.get("bill_id") or data.get("billId")
    if not bill_id:
        return jsonify({"message": "Missing bill_id"}), 400

    token = request.headers.get("Authorization") or request.headers.get("authorization")
    bill_data = fetch_service_data("bill-service", f"/api/bills/{bill_id}", token)
    if not bill_data:
        return jsonify({"message": "Hóa đơn không tồn tại hoặc không có quyền!"}), 404

    bill = bill_data if isinstance(bill_data, dict) else bill_data.get("bill", bill_data)

    # Authz: only owner or admin
    user_id = current_user.get("user_id") or current_user.get("_id")
    if current_user.get("role") != "admin" and bill.get("user_id") != user_id:
        return jsonify({"message": "Không có quyền thanh toán hóa đơn này!"}), 403

    status = (bill.get("status") or "").lower()
    if status == "paid":
        return jsonify({"message": "Hóa đơn đã thanh toán!"}), 400

    bill_total = float(bill.get("total_amount") or bill.get("total") or 0)
    already_paid = calculate_total_paid(bill_id)
    remaining = bill_total - float(already_paid)
    if remaining <= 0:
        return jsonify({"message": "Hóa đơn đã thanh toán đủ!"}), 400

    amount_vnd = int(round(remaining))

    payment_id = f"PAY{uuid.uuid4().hex[:10].upper()}"
    payment_doc = {
        "_id": payment_id,
        "payment_type": "bill_payment",
        "bill_id": bill_id,
        "user_id": str(user_id),
        "amount": float(amount_vnd),
        "amount_vnd": amount_vnd,
        "bill_total": bill_total,
        "currency": "VND",
        "method": "vnpay",
        "provider": "vnpay",
        "status": "pending",
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }
    payments_collection.insert_one(payment_doc)

    order_info = f"Thanh toan hoa don {bill_id}"
    payment_url = build_payment_url(
        base_url=Config.VNPAY_URL,
        tmn_code=Config.VNPAY_TMN_CODE,
        secret=Config.VNPAY_HASH_SECRET,
        txn_ref=payment_id,
        amount_vnd=amount_vnd,
        order_info=order_info,
        return_url=Config.VNPAY_RETURN_URL,
        ipn_url=Config.VNPAY_IPN_URL or None,
        client_ip=_get_client_ip(),
    )

    return jsonify({"payment_url": payment_url, "payment_id": payment_id, "bill_id": bill_id})


# ---------------------------
# VNPay room-reservation deposit flow
# ---------------------------


@app.route("/api/payments/vnpay/room-deposit/create", methods=["POST"])
@token_required
def vnpay_create_room_deposit(current_user):
    data = request.get_json() or {}
    room_id = data.get("room_id")
    check_in_date = data.get("check_in_date")  # Expected check-in date
    
    if not room_id:
        return jsonify({"message": "Missing room_id"}), 400

    room = fetch_service_data("room-service", f"/api/rooms/{room_id}")
    if not room:
        return jsonify({"message": "Phòng không tồn tại!"}), 404

    if room.get("status") != "available":
        return jsonify({"message": "Phòng không còn trống để giữ!"}), 400

    deposit_amount = float(room.get("deposit") or 0)
    if deposit_amount <= 0:
        return jsonify({"message": "Phòng này chưa cấu hình tiền cọc!"}), 400

    user_id = current_user.get("user_id") or current_user.get("_id")
    if not user_id:
        return jsonify({"message": "Không tìm thấy user_id!"}), 400

    # Check if user already has an active contract
    if check_user_has_active_contract(user_id):
        return jsonify({
            "message": "Bạn đã có hợp đồng thuê phòng đang hoạt động. Không thể đặt cọc phòng mới!"
        }), 400

    deposit_amount_vnd = int(round(deposit_amount))

    payment_id = f"PAY{uuid.uuid4().hex[:10].upper()}"
    payment_doc = {
        "_id": payment_id,
        "payment_type": "room_reservation_deposit",
        "room_id": room_id,
        "user_id": str(user_id),
        "amount": float(deposit_amount_vnd),
        "amount_vnd": deposit_amount_vnd,
        "currency": "VND",
        "method": "vnpay",
        "provider": "vnpay",
        "status": "pending",
        "check_in_date": check_in_date,
        "created_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
    }
    payments_collection.insert_one(payment_doc)

    # Hold the room BEFORE redirecting to VNPay to prevent double booking
    if not hold_room_reservation(room_id, user_id, payment_id):
        # If hold fails, delete payment and return error
        payments_collection.delete_one({"_id": payment_id})
        return jsonify({"message": "Không thể giữ phòng. Phòng có thể đã được đặt bởi người khác."}), 400

    order_info = f"Thanh toan coc giu phong {room_id}"
    payment_url = build_payment_url(
        base_url=Config.VNPAY_URL,
        tmn_code=Config.VNPAY_TMN_CODE,
        secret=Config.VNPAY_HASH_SECRET,
        txn_ref=payment_id,
        amount_vnd=deposit_amount_vnd,
        order_info=order_info,
        return_url=Config.VNPAY_RETURN_URL,
        ipn_url=Config.VNPAY_IPN_URL or None,
        client_ip=_get_client_ip(),
    )

    return jsonify({"payment_url": payment_url, "payment_id": payment_id, "room_id": room_id})


@app.route("/api/payments/vnpay/ipn", methods=["GET"])
def vnpay_ipn():
    vnp_params = request.args.to_dict()

    if not validate_return_or_ipn(vnp_params, Config.VNPAY_HASH_SECRET):
        return jsonify({"RspCode": "97", "Message": "Invalid Signature"})

    payment_id = vnp_params.get("vnp_TxnRef")
    response_code = vnp_params.get("vnp_ResponseCode")
    transaction_id = vnp_params.get("vnp_TransactionNo")
    vnp_amount_raw = vnp_params.get("vnp_Amount", "0")
    try:
        amount_received_vnd = int(vnp_amount_raw) // 100
    except Exception:
        amount_received_vnd = 0

    payment = payments_collection.find_one({"_id": payment_id})
    if not payment:
        return jsonify({"RspCode": "01", "Message": "Order not found"})

    if payment.get("method") != "vnpay":
        return jsonify({"RspCode": "01", "Message": "Order not found"})

    if payment.get("status") == "completed":
        return jsonify({"RspCode": "02", "Message": "Order already confirmed"})

    if payment.get("status") == "failed":
        return jsonify({"RspCode": "00", "Message": "Confirm Success"})

    expected_amount_vnd = int(round(float(payment.get("amount_vnd") or payment.get("amount") or 0)))
    if expected_amount_vnd <= 0 or amount_received_vnd != expected_amount_vnd:
        payments_collection.update_one(
            {"_id": payment_id},
            {
                "$set": {
                    "status": "failed",
                    "provider": "vnpay",
                    "provider_txn_id": transaction_id,
                    "transaction_id": transaction_id,
                    "provider_response_code": response_code,
                    "amount_received_vnd": amount_received_vnd,
                    "vnpay_response": vnp_params,
                    "updated_at": _utc_now_iso(),
                }
            },
        )
        return jsonify({"RspCode": "04", "Message": "Invalid amount"})

    if response_code == "00":
        payments_collection.update_one(
            {"_id": payment_id},
            {
                "$set": {
                    "status": "completed",
                    "transaction_id": transaction_id,
                    "provider": "vnpay",
                    "provider_txn_id": transaction_id,
                    "provider_response_code": response_code,
                    "amount_received_vnd": amount_received_vnd,
                    "vnpay_response": vnp_params,
                    "updated_at": _utc_now_iso(),
                }
            },
        )

        if payment.get("payment_type") in ["booking", "booking_deposit"] and payment.get("booking_id"):
            update_booking_deposit_status(
                payment["booking_id"],
                "paid",
                transaction_id,
                payment_id=payment_id,
            )

        if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
            confirm_room_reservation(payment["room_id"], payment_id)
            # Send notification for successful deposit payment
            if payment.get("user_id"):
                send_notification(
                    payment.get("user_id"),
                    "Đặt cọc thành công",
                    f"Bạn đã đặt cọc phòng thành công. Vui lòng vào 'Phòng của tôi' để xem chi tiết và xác nhận nhận phòng vào ngày check-in.",
                    "payment",
                    {"room_id": payment.get("room_id"), "payment_id": payment_id, "type": "room_deposit"},
                )

        if payment.get("payment_type") == "bill_payment" and payment.get("bill_id"):
            bill_total = payment.get("bill_total") or payment.get("amount") or amount_received_vnd
            update_bill_status_if_paid(payment["bill_id"], bill_total)
            if payment.get("user_id"):
                send_notification(
                    payment.get("user_id"),
                    "Thanh toán thành công",
                    f"Hóa đơn {payment.get('bill_id')} đã được thanh toán thành công.",
                    "payment",
                    {"bill_id": payment.get("bill_id"), "payment_id": payment_id},
                )

        return jsonify({"RspCode": "00", "Message": "Confirm Success"})

    payments_collection.update_one(
        {"_id": payment_id},
        {
            "$set": {
                "status": "failed",
                "transaction_id": transaction_id,
                "provider": "vnpay",
                "provider_txn_id": transaction_id,
                "provider_response_code": response_code,
                "amount_received_vnd": amount_received_vnd,
                "vnpay_response": vnp_params,
                "updated_at": _utc_now_iso(),
            }
        },
    )

    # Release held room if this is a room reservation deposit.
    if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
        release_room_reservation(payment["room_id"], payment_id)

    return jsonify({"RspCode": "00", "Message": "Confirm Success"})


@app.route("/api/payments/vnpay/return", methods=["GET"])
def vnpay_return():
    # VNPay redirects the user back to this URL in the browser.
    # Always redirect back to the frontend so the user doesn't see raw JSON.
    vnp_params = request.args.to_dict()

    response_code = vnp_params.get("vnp_ResponseCode") or ""
    txn_ref = vnp_params.get("vnp_TxnRef") or ""

    signature_ok = validate_return_or_ipn(vnp_params, Config.VNPAY_HASH_SECRET)

    mode = (Config.VNPAY_CONFIRM_MODE or "return").lower()

    # Best-effort update of payment record (return can arrive before/without IPN)
    # Modes:
    # - return: confirm paid on return signature+amount
    # - querydr: confirm paid only when QueryDR verifies
    # - ipn: keep pending on return; confirm only on IPN
    verified = False
    verified_code = ""
    verified_txn_status = ""

    if txn_ref:
        set_fields = {
            "vnpay_return": vnp_params,
            "provider": "vnpay",
            "provider_response_code": response_code,
            "updated_at": _utc_now_iso(),
        }

        transaction_id = vnp_params.get("vnp_TransactionNo")
        if transaction_id:
            set_fields["transaction_id"] = transaction_id
            set_fields["provider_txn_id"] = transaction_id

        if not signature_ok:
            set_fields["status"] = "failed"
            payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})
        else:
            if response_code == "00":
                payment = payments_collection.find_one({"_id": txn_ref})

                # Mode: ipn -> don't confirm on return.
                if mode == "ipn":
                    set_fields["status"] = "pending"
                    payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})

                # Mode: return -> confirm based on signature + amount match.
                elif mode == "return":
                    if payment:
                        expected_amount_vnd = int(
                            round(float(payment.get("amount_vnd") or payment.get("amount") or 0))
                        )
                        vnp_amount_raw = vnp_params.get("vnp_Amount", "0")
                        try:
                            amount_received_vnd = int(vnp_amount_raw) // 100
                        except Exception:
                            amount_received_vnd = 0

                        if amount_received_vnd:
                            set_fields["amount_received_vnd"] = amount_received_vnd

                        if expected_amount_vnd > 0 and amount_received_vnd == expected_amount_vnd:
                            verified = True
                            set_fields["status"] = "completed"
                            payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})

                            if payment.get("payment_type") in ["booking", "booking_deposit"] and payment.get(
                                "booking_id"
                            ):
                                update_booking_deposit_status(
                                    payment["booking_id"],
                                    "paid",
                                    transaction_id,
                                    payment_id=txn_ref,
                                )
                            if payment.get("payment_type") == "bill_payment" and payment.get("bill_id"):
                                bill_total = payment.get("bill_total") or payment.get("amount") or amount_received_vnd
                                update_bill_status_if_paid(payment["bill_id"], bill_total)
                                if payment.get("user_id"):
                                    send_notification(
                                        payment.get("user_id"),
                                        "Thanh toán thành công",
                                        f"Hóa đơn {payment.get('bill_id')} đã được thanh toán thành công.",
                                        "payment",
                                        {"bill_id": payment.get("bill_id"), "payment_id": txn_ref},
                                    )
                            if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
                                confirm_room_reservation(payment["room_id"], txn_ref)
                                # Send notification for successful deposit payment
                                if payment.get("user_id"):
                                    send_notification(
                                        payment.get("user_id"),
                                        "Đặt cọc thành công",
                                        f"Bạn đã đặt cọc phòng thành công. Vui lòng vào 'Phòng của tôi' để xác nhận nhận phòng.",
                                        "payment",
                                        {"room_id": payment.get("room_id"), "payment_id": txn_ref, "type": "room_deposit"},
                                    )
                        else:
                            set_fields["status"] = "failed"
                            payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})
                            if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
                                release_room_reservation(payment["room_id"], txn_ref)
                    else:
                        payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})

                # Default: querydr
                else:
                    if payment:
                        transaction_date = (
                            vnp_params.get("vnp_PayDate")
                            or vnp_params.get("vnp_TransactionDate")
                            or vnp_params.get("vnp_CreateDate")
                            or ""
                        )
                        if payment.get("payment_type") == "room_reservation_deposit":
                            order_info = f"Thanh toan coc giu phong {payment.get('room_id') or ''}".strip()
                        else:
                            order_info = f"Thanh toan coc booking {payment.get('booking_id') or ''}".strip()
                        request_id = uuid.uuid4().hex

                        verified, qdr = querydr_verify_transaction(
                            api_url=Config.VNPAY_API_URL,
                            tmn_code=Config.VNPAY_TMN_CODE,
                            secret=Config.VNPAY_HASH_SECRET,
                            txn_ref=txn_ref,
                            order_info=order_info,
                            transaction_date=transaction_date,
                            client_ip=_get_client_ip(),
                            request_id=request_id,
                        )
                        verified_code = qdr.get("vnp_ResponseCode") or ""
                        verified_txn_status = qdr.get("vnp_TransactionStatus") or ""
                        set_fields["vnpay_querydr"] = qdr

                        expected_amount_vnd = int(
                            round(float(payment.get("amount_vnd") or payment.get("amount") or 0))
                        )
                        vnp_amount_raw = vnp_params.get("vnp_Amount", "0")
                        try:
                            amount_received_vnd = int(vnp_amount_raw) // 100
                        except Exception:
                            amount_received_vnd = 0
                        if amount_received_vnd:
                            set_fields["amount_received_vnd"] = amount_received_vnd

                        if verified and expected_amount_vnd > 0 and amount_received_vnd == expected_amount_vnd:
                            set_fields["status"] = "completed"
                            payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})

                            if payment.get("payment_type") in ["booking", "booking_deposit"] and payment.get(
                                "booking_id"
                            ):
                                update_booking_deposit_status(
                                    payment["booking_id"],
                                    "paid",
                                    transaction_id,
                                    payment_id=txn_ref,
                                )
                            if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
                                confirm_room_reservation(payment["room_id"], txn_ref)
                                if payment.get("user_id"):
                                    send_notification(
                                        payment.get("user_id"),
                                        "Đặt cọc thành công",
                                        f"Bạn đã đặt cọc phòng thành công. Vui lòng vào 'Phòng của tôi' để xác nhận nhận phòng.",
                                        "payment",
                                        {"room_id": payment.get("room_id"), "payment_id": txn_ref, "type": "room_deposit"},
                                    )
                            if payment.get("payment_type") == "bill_payment" and payment.get("bill_id"):
                                bill_total = payment.get("bill_total") or payment.get("amount") or amount_received_vnd
                                update_bill_status_if_paid(payment["bill_id"], bill_total)
                                if payment.get("user_id"):
                                    send_notification(
                                        payment.get("user_id"),
                                        "Thanh toán thành công",
                                        f"Hóa đơn {payment.get('bill_id')} đã được thanh toán thành công.",
                                        "payment",
                                        {"bill_id": payment.get("bill_id"), "payment_id": txn_ref},
                                    )
                        else:
                            set_fields["status"] = "pending"
                            payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})
                    else:
                        payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})
            else:
                # 24 = user cancelled, others = failed
                set_fields["status"] = "failed"
                payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})

    # Figure out booking_id / room_id for nicer UX
    booking_id = ""
    room_id = ""
    bill_id = ""
    is_room_reservation = False
    if txn_ref:
        payment = payments_collection.find_one({"_id": txn_ref})
        if payment:
            booking_id = str(payment.get("booking_id") or "")
            room_id = str(payment.get("room_id") or "")
            bill_id = str(payment.get("bill_id") or "")
            is_room_reservation = payment.get("payment_type") == "room_reservation_deposit"

    frontend_redirect_base = "/user/home.html"

    if not signature_ok:
        if is_room_reservation and room_id and txn_ref:
            release_room_reservation(room_id, txn_ref)
        return redirect(f"{frontend_redirect_base}?vnpay=error&code=97&payment_id={txn_ref}")

    # If we already marked as failed (e.g., amount mismatch), don't show pending.
    if response_code == "00" and txn_ref:
        payment = payments_collection.find_one({"_id": txn_ref})
        if payment and payment.get("status") == "failed":
            suffix = f"payment_id={txn_ref}"
            if booking_id:
                suffix += f"&booking_id={booking_id}"
            if room_id:
                suffix += f"&room_id={room_id}"
            return redirect(f"{frontend_redirect_base}?vnpay=failed&code=failed&{suffix}")

    if response_code == "00":
        # Success (user-facing).
        # Behavior depends on confirmation mode.
        suffix = f"payment_id={txn_ref}"
        if booking_id:
            suffix += f"&booking_id={booking_id}"
        if room_id:
            suffix += f"&room_id={room_id}"
        if bill_id:
            suffix += f"&bill_id={bill_id}"
        if mode == "return" and verified:
            # Finalize reservation if this is room deposit.
            if is_room_reservation and room_id:
                confirm_room_reservation(room_id, txn_ref)
                if payment and payment.get("user_id"):
                    send_notification(
                        payment.get("user_id"),
                        "Đặt cọc thành công",
                        f"Bạn đã đặt cọc phòng thành công. Vui lòng vào 'Phòng của tôi' để xác nhận nhận phòng.",
                        "payment",
                        {"room_id": room_id, "payment_id": txn_ref, "type": "room_deposit"},
                    )
                # NOTE: Contract created when user clicks check-in, not here
            return redirect(f"{frontend_redirect_base}?vnpay=success&{suffix}")
        if mode == "ipn":
            return redirect(f"{frontend_redirect_base}?vnpay=pending&code=ipn&{suffix}")
        if verified:
            if is_room_reservation and room_id:
                confirm_room_reservation(room_id, txn_ref)
                if payment and payment.get("user_id"):
                    send_notification(
                        payment.get("user_id"),
                        "Đặt cọc thành công",
                        f"Bạn đã đặt cọc phòng thành công. Vui lòng vào 'Phòng của tôi' để xác nhận nhận phòng.",
                        "payment",
                        {"room_id": room_id, "payment_id": txn_ref, "type": "room_deposit"},
                    )
                # NOTE: Contract created when user clicks check-in, not here
            return redirect(f"{frontend_redirect_base}?vnpay=success&{suffix}")
        code = verified_code or verified_txn_status or "pending"
        return redirect(f"{frontend_redirect_base}?vnpay=pending&code={code}&{suffix}")

    if response_code == "24":
        suffix = f"payment_id={txn_ref}"
        if booking_id:
            suffix += f"&booking_id={booking_id}"
        if room_id:
            suffix += f"&room_id={room_id}"
        if is_room_reservation and room_id and txn_ref:
            release_room_reservation(room_id, txn_ref)
        return redirect(f"{frontend_redirect_base}?vnpay=cancel&{suffix}")

    suffix = f"payment_id={txn_ref}"
    if booking_id:
        suffix += f"&booking_id={booking_id}"
    if room_id:
        suffix += f"&room_id={room_id}"
    if bill_id:
        suffix += f"&bill_id={bill_id}"
    if is_room_reservation and room_id and txn_ref:
        release_room_reservation(room_id, txn_ref)
    return redirect(f"{frontend_redirect_base}?vnpay=failed&code={response_code}&{suffix}")


@app.route("/api/payments/vnpay/verify/<payment_id>", methods=["GET"])
@token_required
def vnpay_verify_payment(current_user, payment_id):
    # Verify a VNPay payment.
    # Used by frontend polling when return page shows `vnpay=pending`.

    payment = payments_collection.find_one({"_id": payment_id})
    if not payment:
        return jsonify({"message": "Thanh toán không tồn tại!"}), 404

    # Permission: admin can verify any; user can verify own payments.
    if current_user.get("role") != "admin":
        me = current_user.get("user_id") or current_user.get("_id")
        if payment.get("user_id") != me:
            return jsonify({"message": "Không có quyền!"}), 403

    # If already completed/failed, return current state.
    # For completed booking deposits, also re-sync booking-service (idempotent).
    if payment.get("status") in ("completed", "failed"):
        if payment.get("status") == "completed":
            if payment.get("payment_type") in ("booking_deposit", "booking") and payment.get("booking_id"):
                update_booking_deposit_status(
                    payment["booking_id"],
                    "paid",
                    payment.get("transaction_id"),
                    payment_id=payment_id,
                )
            if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
                confirm_room_reservation(payment["room_id"], payment_id)

        if payment.get("status") == "failed":
            if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
                release_room_reservation(payment["room_id"], payment_id)

        return (
            jsonify(
                {
                    "payment_id": payment_id,
                    "status": payment.get("status"),
                    "booking_id": payment.get("booking_id"),
                    "room_id": payment.get("room_id"),
                    "provider_response_code": payment.get("provider_response_code"),
                }
            ),
            200,
        )

    mode = (Config.VNPAY_CONFIRM_MODE or "return").lower()

    vnp_return = payment.get("vnpay_return") or {}

    # Mode: return -> finalize using stored return params (signature + amount match)
    if mode == "return":
        response_code = vnp_return.get("vnp_ResponseCode") or ""
        signature_ok = validate_return_or_ipn(vnp_return, Config.VNPAY_HASH_SECRET) if vnp_return else False

        if response_code == "00" and signature_ok:
            expected_amount_vnd = int(round(float(payment.get("amount_vnd") or payment.get("amount") or 0)))
            vnp_amount_raw = vnp_return.get("vnp_Amount", "0")
            try:
                amount_received_vnd = int(vnp_amount_raw) // 100
            except Exception:
                amount_received_vnd = 0

            if expected_amount_vnd > 0 and amount_received_vnd == expected_amount_vnd:
                set_fields = {
                    "status": "completed",
                    "amount_received_vnd": amount_received_vnd,
                    "updated_at": _utc_now_iso(),
                }
                transaction_id = vnp_return.get("vnp_TransactionNo")
                if transaction_id:
                    set_fields["transaction_id"] = transaction_id
                    set_fields["provider_txn_id"] = transaction_id

                payments_collection.update_one({"_id": payment_id}, {"$set": set_fields})
                updated = payments_collection.find_one({"_id": payment_id}) or payment

                if updated.get("payment_type") in ("booking_deposit", "booking") and updated.get("booking_id"):
                    update_booking_deposit_status(
                        updated["booking_id"],
                        "paid",
                        transaction_id,
                        payment_id=payment_id,
                    )

                if updated.get("payment_type") == "room_reservation_deposit" and updated.get("room_id"):
                    confirm_room_reservation(updated["room_id"], payment_id)

                return (
                    jsonify(
                        {
                            "payment_id": payment_id,
                            "booking_id": updated.get("booking_id"),
                            "room_id": updated.get("room_id"),
                            "status": "completed",
                            "verified": True,
                            "provider_response_code": "00",
                            "transaction_status": "00",
                        }
                    ),
                    200,
                )

        # Still pending in return mode
        return (
            jsonify(
                {
                    "payment_id": payment_id,
                    "booking_id": payment.get("booking_id"),
                    "room_id": payment.get("room_id"),
                    "status": payment.get("status") or "pending",
                    "verified": False,
                    "provider_response_code": response_code or payment.get("provider_response_code"),
                }
            ),
            200,
        )
    transaction_date = (
        vnp_return.get("vnp_PayDate")
        or vnp_return.get("vnp_TransactionDate")
        or vnp_return.get("vnp_CreateDate")
        or ""
    )

    # Without a transaction date, QueryDR can't be performed reliably.
    if not transaction_date:
        return (
            jsonify(
                {
                    "payment_id": payment_id,
                    "status": "pending",
                    "verified": False,
                    "reason": "missing_transaction_date",
                }
            ),
            200,
        )

    order_info = ""
    if payment.get("payment_type") in ("booking_deposit", "booking") and payment.get("booking_id"):
        order_info = f"Thanh toan coc booking {payment.get('booking_id')}".strip()
    elif payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
        order_info = f"Thanh toan coc giu phong {payment.get('room_id')}".strip()
    else:
        order_info = f"Thanh toan {payment_id}".strip()

    verified, qdr = querydr_verify_transaction(
        api_url=Config.VNPAY_API_URL,
        tmn_code=Config.VNPAY_TMN_CODE,
        secret=Config.VNPAY_HASH_SECRET,
        txn_ref=payment_id,
        order_info=order_info,
        transaction_date=transaction_date,
        client_ip=_get_client_ip(),
        request_id=uuid.uuid4().hex,
    )

    set_fields = {
        "vnpay_querydr": qdr,
        "updated_at": _utc_now_iso(),
    }

    if verified:
        # Extra safety: amount check if we have vnp_Amount in return.
        expected_amount_vnd = int(round(float(payment.get("amount_vnd") or payment.get("amount") or 0)))
        vnp_amount_raw = vnp_return.get("vnp_Amount", "0")
        try:
            amount_received_vnd = int(vnp_amount_raw) // 100
        except Exception:
            amount_received_vnd = 0

        if expected_amount_vnd > 0 and amount_received_vnd == expected_amount_vnd:
            set_fields["status"] = "completed"
            if amount_received_vnd:
                set_fields["amount_received_vnd"] = amount_received_vnd
        else:
            # QueryDR says OK but our amount check fails => keep pending.
            verified = False
            set_fields["status"] = "pending"
            set_fields["verify_mismatch"] = {
                "expected_amount_vnd": expected_amount_vnd,
                "amount_received_vnd": amount_received_vnd,
            }
    else:
        # Still pending or not successful.
        set_fields["status"] = "pending"

    payments_collection.update_one({"_id": payment_id}, {"$set": set_fields})

    updated = payments_collection.find_one({"_id": payment_id}) or payment
    status = updated.get("status")

    # If we just completed a booking deposit, sync booking-service.
    if status == "completed" and updated.get("payment_type") in ("booking_deposit", "booking") and updated.get(
        "booking_id"
    ):
        transaction_id = (updated.get("transaction_id") or (vnp_return.get("vnp_TransactionNo")))
        update_booking_deposit_status(
            updated["booking_id"],
            "paid",
            transaction_id,
            payment_id=payment_id,
        )

    if status == "completed" and updated.get("payment_type") == "room_reservation_deposit" and updated.get("room_id"):
        confirm_room_reservation(updated["room_id"], payment_id)

    return (
        jsonify(
            {
                "payment_id": payment_id,
                "booking_id": updated.get("booking_id"),
                "room_id": updated.get("room_id"),
                "status": status,
                "verified": bool(status == "completed"),
                "provider_response_code": (updated.get("vnpay_querydr") or {}).get("vnp_ResponseCode")
                or updated.get("provider_response_code"),
                "transaction_status": (updated.get("vnpay_querydr") or {}).get("vnp_TransactionStatus"),
            }
        ),
        200,
    )


if __name__ == "__main__":
    register_service()
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=Config.SERVICE_PORT, debug=debug_mode)
