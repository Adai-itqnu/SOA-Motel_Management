from __future__ import annotations

import datetime
import hashlib
import hmac
import urllib.parse

import requests


def _sorted_query(params: dict[str, str]) -> str:
    # VNPay expects params sorted by key ascending
    items = sorted((k, v) for k, v in params.items() if v is not None)
    # VNPay implementations typically use application/x-www-form-urlencoded encoding
    # (spaces encoded as '+'), so use quote_plus.
    return urllib.parse.urlencode(items, safe="", quote_via=urllib.parse.quote_plus)


def sign_hmac_sha512(query_string: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), query_string.encode("utf-8"), hashlib.sha512).hexdigest()


def build_payment_url(
    *,
    base_url: str,
    tmn_code: str,
    secret: str,
    txn_ref: str,
    amount_vnd: float,
    order_info: str,
    return_url: str,
    ipn_url: str | None = None,
    client_ip: str,
    locale: str = "vn",
    order_type: str = "other",
    expire_minutes: int = 15,
) -> str:
    amount_int = int(round(float(amount_vnd)))

    # VNPay typically expects timestamps in GMT+7
    now_gmt7 = datetime.datetime.utcnow() + datetime.timedelta(hours=7)
    expire_at = now_gmt7 + datetime.timedelta(minutes=max(1, int(expire_minutes)))

    params: dict[str, str] = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": tmn_code,
        "vnp_Amount": str(amount_int * 100),
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": txn_ref,
        "vnp_OrderInfo": order_info,
        "vnp_OrderType": order_type,
        "vnp_Locale": locale,
        "vnp_ReturnUrl": return_url,
        "vnp_IpAddr": client_ip or "127.0.0.1",
        "vnp_CreateDate": now_gmt7.strftime("%Y%m%d%H%M%S"),
        "vnp_ExpireDate": expire_at.strftime("%Y%m%d%H%M%S"),
    }

    if ipn_url:
        params["vnp_IpnUrl"] = ipn_url

    # IMPORTANT: VNPay hash data excludes vnp_SecureHash and vnp_SecureHashType
    query_string_for_hash = _sorted_query(params)
    secure_hash = sign_hmac_sha512(query_string_for_hash, secret)

    # Build final URL (include hash type as a param, but do not include it in hash data)
    query_string_for_url = _sorted_query({**params, "vnp_SecureHashType": "HmacSHA512"})
    return f"{base_url}?{query_string_for_url}&vnp_SecureHash={secure_hash}"


def validate_return_or_ipn(params: dict[str, str], secret: str) -> bool:
    if not secret:
        return False

    secure_hash = params.get("vnp_SecureHash")
    if not secure_hash:
        return False

    filtered = {k: v for k, v in params.items() if k not in ("vnp_SecureHash", "vnp_SecureHashType")}
    query_string = _sorted_query(filtered)
    expected = sign_hmac_sha512(query_string, secret)
    return expected.lower() == secure_hash.lower()


def build_querydr_payload(
    *,
    tmn_code: str,
    secret: str,
    txn_ref: str,
    order_info: str,
    transaction_date: str,
    client_ip: str,
    request_id: str,
) -> dict[str, str]:
    """Build VNPay QueryDR payload.

    `transaction_date` should be in YYYYMMDDHHMMSS (usually vnp_PayDate).
    """

    # VNPay typically expects timestamps in GMT+7
    now_gmt7 = datetime.datetime.utcnow() + datetime.timedelta(hours=7)

    params: dict[str, str] = {
        "vnp_RequestId": request_id,
        "vnp_Version": "2.1.0",
        "vnp_Command": "querydr",
        "vnp_TmnCode": tmn_code,
        "vnp_TxnRef": txn_ref,
        "vnp_OrderInfo": order_info,
        "vnp_TransactionDate": transaction_date,
        "vnp_CreateDate": now_gmt7.strftime("%Y%m%d%H%M%S"),
        "vnp_IpAddr": client_ip or "127.0.0.1",
    }

    query_string_for_hash = _sorted_query(params)
    secure_hash = sign_hmac_sha512(query_string_for_hash, secret)
    return {**params, "vnp_SecureHash": secure_hash}


def parse_vnpay_kv_response(text: str) -> dict[str, str]:
    """Parse VNPay response formats like: key=value&key2=value2."""
    parsed = urllib.parse.parse_qs(text, keep_blank_values=True)
    return {k: (v[0] if isinstance(v, list) and v else "") for k, v in parsed.items()}


def querydr_verify_transaction(
    *,
    api_url: str,
    tmn_code: str,
    secret: str,
    txn_ref: str,
    order_info: str,
    transaction_date: str,
    client_ip: str,
    request_id: str,
    timeout_seconds: int = 10,
) -> tuple[bool, dict[str, str]]:
    """Call VNPay QueryDR to verify a transaction.

    Returns (verified, response_params).
    verified == True only when response signature is valid AND the transaction status indicates success.
    """

    if not api_url:
        return False, {"message": "Missing VNPAY_API_URL"}

    payload = build_querydr_payload(
        tmn_code=tmn_code,
        secret=secret,
        txn_ref=txn_ref,
        order_info=order_info,
        transaction_date=transaction_date,
        client_ip=client_ip,
        request_id=request_id,
    )

    try:
        resp = requests.post(api_url, data=payload, timeout=timeout_seconds)
    except Exception as exc:
        return False, {"message": f"QueryDR request failed: {exc}"}

    # VNPay commonly responds in key=value&key2=value2 format.
    content_type = (resp.headers.get("Content-Type") or "").lower()
    if "application/json" in content_type:
        try:
            data = resp.json() or {}
            params = {str(k): "" if v is None else str(v) for k, v in data.items()}
        except Exception:
            params = {}
    else:
        params = parse_vnpay_kv_response(resp.text or "")

    # Validate signature when provided
    signature_ok = True
    if params.get("vnp_SecureHash"):
        signature_ok = validate_return_or_ipn(params, secret)

    # Success is typically: vnp_ResponseCode == 00 AND vnp_TransactionStatus == 00
    rsp_code = params.get("vnp_ResponseCode") or ""
    txn_status = params.get("vnp_TransactionStatus") or ""
    verified = bool(signature_ok and rsp_code == "00" and txn_status == "00")
    return verified, {**params, "_signature_ok": "1" if signature_ok else "0"}
