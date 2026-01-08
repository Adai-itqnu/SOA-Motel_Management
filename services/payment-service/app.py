from __future__ import annotations

import datetime
import os
import uuid

from flask import Flask, jsonify, request
from flask_cors import CORS

from config import Config
from model import payments_collection
from service_registry import register_service
from decorators import token_required, admin_required
from utils import (
    calculate_total_paid,
    fetch_service_data,
    update_bill_status_if_paid,
)
from vnpay_routes import vnpay_bp


def _utc_now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _today_str() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


app = Flask(__name__)
CORS(app)

# Register VNPay Blueprint (tất cả endpoints VNPay nằm trong vnpay_routes.py)
app.register_blueprint(vnpay_bp)

app.config["SECRET_KEY"] = Config.JWT_SECRET
app.config["SERVICE_NAME"] = Config.SERVICE_NAME
app.config["SERVICE_PORT"] = Config.SERVICE_PORT

@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": app.config["SERVICE_NAME"]}), 200


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


if __name__ == "__main__":
    register_service()
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=Config.SERVICE_PORT, debug=debug_mode)
