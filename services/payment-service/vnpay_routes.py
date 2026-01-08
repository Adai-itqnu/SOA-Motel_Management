"""
VNPay Routes - Flask Blueprint for all VNPay-related endpoints
Tách từ app.py để code gọn gàng hơn
"""
from __future__ import annotations

import datetime
import os
import uuid

from flask import Blueprint, jsonify, redirect, request

from config import Config
from model import payments_collection
from decorators import token_required
from utils import (
    check_user_has_active_contract,
    confirm_room_reservation,
    fetch_service_data,
    hold_room_reservation,
    release_room_reservation,
    update_bill_status_if_paid,
    update_booking_deposit_status,
    send_notification,
    calculate_total_paid,
)
from vnpay import build_payment_url, querydr_verify_transaction, validate_return_or_ipn


# Create Blueprint
vnpay_bp = Blueprint('vnpay', __name__, url_prefix='/api/vnpay')


def _utc_now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _get_client_ip() -> str:
    return (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.remote_addr
        or "127.0.0.1"
    )


# ---------------------------
# VNPay deposit flow (booking)
# ---------------------------


@vnpay_bp.route("/booking-deposit", methods=["POST"])
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


@vnpay_bp.route("/bill", methods=["POST"])
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


@vnpay_bp.route("/room-deposit", methods=["POST"])
@token_required
def vnpay_create_room_deposit(current_user):
    data = request.get_json() or {}
    room_id = data.get("room_id")
    check_in_date = data.get("check_in_date")
    
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

    # Hold the room BEFORE redirecting to VNPay
    if not hold_room_reservation(room_id, user_id, payment_id):
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


# ---------------------------
# VNPay IPN Callback
# ---------------------------


@vnpay_bp.route("/ipn", methods=["GET"])
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
            if payment.get("user_id"):
                send_notification(
                    payment.get("user_id"),
                    "Đặt cọc thành công",
                    f"Bạn đã đặt cọc phòng thành công. Vui lòng vào 'Phòng của tôi' để xem chi tiết.",
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

    if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
        release_room_reservation(payment["room_id"], payment_id)

    return jsonify({"RspCode": "00", "Message": "Confirm Success"})


# ---------------------------
# VNPay Return (User redirect)
# ---------------------------


@vnpay_bp.route("/return", methods=["GET"])
def vnpay_return():
    vnp_params = request.args.to_dict()

    response_code = vnp_params.get("vnp_ResponseCode") or ""
    txn_ref = vnp_params.get("vnp_TxnRef") or ""

    signature_ok = validate_return_or_ipn(vnp_params, Config.VNPAY_HASH_SECRET)

    mode = (Config.VNPAY_CONFIRM_MODE or "return").lower()

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

                if mode == "ipn":
                    set_fields["status"] = "pending"
                    payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})

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

                            _process_successful_payment(payment, transaction_id, txn_ref, amount_received_vnd)
                        else:
                            set_fields["status"] = "failed"
                            payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})
                            if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
                                release_room_reservation(payment["room_id"], txn_ref)
                    else:
                        payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})

                else:  # querydr mode
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
                            _process_successful_payment(payment, transaction_id, txn_ref, amount_received_vnd)
                        else:
                            set_fields["status"] = "pending"
                            payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})
                    else:
                        payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})
            else:
                set_fields["status"] = "failed"
                payments_collection.update_one({"_id": txn_ref}, {"$set": set_fields})

    # Get payment info for redirect
    booking_id = ""
    room_id = ""
    bill_id = ""
    is_room_reservation = False
    is_bill_payment = False
    if txn_ref:
        payment = payments_collection.find_one({"_id": txn_ref})
        if payment:
            booking_id = str(payment.get("booking_id") or "")
            room_id = str(payment.get("room_id") or "")
            bill_id = str(payment.get("bill_id") or "")
            is_room_reservation = payment.get("payment_type") == "room_reservation_deposit"
            is_bill_payment = payment.get("payment_type") == "bill_payment"

    # Redirect to appropriate page based on payment type
    if is_bill_payment:
        frontend_redirect_base = "/user/bills.html"
    else:
        frontend_redirect_base = "/user/home.html"

    if not signature_ok:
        if is_room_reservation and room_id and txn_ref:
            release_room_reservation(room_id, txn_ref)
        return redirect(f"{frontend_redirect_base}?vnpay=error&code=97&payment_id={txn_ref}")

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
        suffix = f"payment_id={txn_ref}"
        if booking_id:
            suffix += f"&booking_id={booking_id}"
        if room_id:
            suffix += f"&room_id={room_id}"
        if bill_id:
            suffix += f"&bill_id={bill_id}"
        if mode == "return" and verified:
            return redirect(f"{frontend_redirect_base}?vnpay=success&{suffix}")
        if mode == "ipn":
            return redirect(f"{frontend_redirect_base}?vnpay=pending&code=ipn&{suffix}")
        if verified:
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


def _process_successful_payment(payment, transaction_id, payment_id, amount_received_vnd):
    """Helper function to process successful payment side effects."""
    if payment.get("payment_type") in ["booking", "booking_deposit"] and payment.get("booking_id"):
        update_booking_deposit_status(
            payment["booking_id"],
            "paid",
            transaction_id,
            payment_id=payment_id,
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
    if payment.get("payment_type") == "room_reservation_deposit" and payment.get("room_id"):
        confirm_room_reservation(payment["room_id"], payment_id)
        if payment.get("user_id"):
            send_notification(
                payment.get("user_id"),
                "Đặt cọc thành công",
                f"Bạn đã đặt cọc phòng thành công. Vui lòng vào 'Phòng của tôi' để xác nhận nhận phòng.",
                "payment",
                {"room_id": payment.get("room_id"), "payment_id": payment_id, "type": "room_deposit"},
            )


# ---------------------------
# VNPay Verify Payment (Polling)
# ---------------------------


@vnpay_bp.route("/verify/<payment_id>", methods=["GET"])
@token_required
def vnpay_verify_payment(current_user, payment_id):
    payment = payments_collection.find_one({"_id": payment_id})
    if not payment:
        return jsonify({"message": "Thanh toán không tồn tại!"}), 404

    if current_user.get("role") != "admin":
        me = current_user.get("user_id") or current_user.get("_id")
        if payment.get("user_id") != me:
            return jsonify({"message": "Không có quyền!"}), 403

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

        return jsonify({
            "payment_id": payment_id,
            "status": payment.get("status"),
            "booking_id": payment.get("booking_id"),
            "room_id": payment.get("room_id"),
            "provider_response_code": payment.get("provider_response_code"),
        }), 200

    mode = (Config.VNPAY_CONFIRM_MODE or "return").lower()
    vnp_return = payment.get("vnpay_return") or {}

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

                return jsonify({
                    "payment_id": payment_id,
                    "booking_id": updated.get("booking_id"),
                    "room_id": updated.get("room_id"),
                    "status": "completed",
                    "verified": True,
                    "provider_response_code": "00",
                    "transaction_status": "00",
                }), 200

        return jsonify({
            "payment_id": payment_id,
            "booking_id": payment.get("booking_id"),
            "room_id": payment.get("room_id"),
            "status": payment.get("status") or "pending",
            "verified": False,
            "provider_response_code": response_code or payment.get("provider_response_code"),
        }), 200

    # QueryDR mode
    transaction_date = (
        vnp_return.get("vnp_PayDate")
        or vnp_return.get("vnp_TransactionDate")
        or vnp_return.get("vnp_CreateDate")
        or ""
    )

    if not transaction_date:
        return jsonify({
            "payment_id": payment_id,
            "status": "pending",
            "verified": False,
            "reason": "missing_transaction_date",
        }), 200

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
            verified = False
            set_fields["status"] = "pending"
            set_fields["verify_mismatch"] = {
                "expected_amount_vnd": expected_amount_vnd,
                "amount_received_vnd": amount_received_vnd,
            }
    else:
        set_fields["status"] = "pending"

    payments_collection.update_one({"_id": payment_id}, {"$set": set_fields})

    updated = payments_collection.find_one({"_id": payment_id}) or payment
    status = updated.get("status")

    if status == "completed" and updated.get("payment_type") in ("booking_deposit", "booking") and updated.get("booking_id"):
        transaction_id = updated.get("transaction_id") or vnp_return.get("vnp_TransactionNo")
        update_booking_deposit_status(
            updated["booking_id"],
            "paid",
            transaction_id,
            payment_id=payment_id,
        )

    if status == "completed" and updated.get("payment_type") == "room_reservation_deposit" and updated.get("room_id"):
        confirm_room_reservation(updated["room_id"], payment_id)

    return jsonify({
        "payment_id": payment_id,
        "booking_id": updated.get("booking_id"),
        "room_id": updated.get("room_id"),
        "status": status,
        "verified": bool(status == "completed"),
        "provider_response_code": (updated.get("vnpay_querydr") or {}).get("vnp_ResponseCode")
        or updated.get("provider_response_code"),
        "transaction_status": (updated.get("vnpay_querydr") or {}).get("vnp_TransactionStatus"),
    }), 200
