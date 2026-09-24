"""Small dependency-free KCB Buni M-Pesa Express adapter."""

import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TOKEN_URL = os.environ.get("KCB_BUNI_TOKEN_URL", "https://accounts.buni.kcbgroup.com/oauth2/token")
API_BASE_URL = os.environ.get("KCB_BUNI_API_BASE_URL", "https://uat.buni.kcbgroup.com").rstrip("/")
STK_PATH = os.environ.get("KCB_BUNI_STK_PATH", "/mm/api/request/1.0.0/stkpush")
ROUTE_CODE = os.environ.get("KCB_BUNI_ROUTE_CODE", "207")
OPERATION = os.environ.get("KCB_BUNI_OPERATION", "STKPush")


class KCBError(RuntimeError):
    pass


def _json_request(request):
    try:
        with urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise KCBError(f"KCB HTTP {exc.code}: {detail[:300]}") from exc
    except URLError as exc:
        raise KCBError(f"KCB connection failed: {exc.reason}") from exc


def access_token():
    key = os.environ.get("KCB_BUNI_CONSUMER_KEY", "")
    secret = os.environ.get("KCB_BUNI_CONSUMER_SECRET", "")
    if not key or not secret:
        raise KCBError("KCB consumer credentials are not configured")
    basic = base64.b64encode(f"{key}:{secret}".encode()).decode()
    request = Request(
        TOKEN_URL,
        data=b"grant_type=client_credentials",
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    _, payload = _json_request(request)
    token = payload.get("access_token")
    if not token:
        raise KCBError("KCB token response did not contain access_token")
    return token


def stk_push(phone_number, amount, invoice_number, callback_url, description="WiHotspot access", message_id=None):
    token = access_token()
    payload = {
        "phoneNumber": phone_number,
        "amount": str(amount),
        "invoiceNumber": invoice_number,
        "sharedShortCode": True,
        "orgShortCode": "",
        "orgPassKey": "",
        "callbackUrl": callback_url,
        "transactionDescription": description[:30],
    }
    request = Request(
        f"{API_BASE_URL}{STK_PATH}",
        data=json.dumps(payload).encode(),
        headers={
            "Accept": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "routeCode": ROUTE_CODE,
            "operation": OPERATION,
            "messageId": message_id or invoice_number,
        },
        method="POST",
    )
    api_key = os.environ.get("KCB_BUNI_API_KEY", "")
    if api_key:
        request.add_header("apikey", api_key)
    _, response = _json_request(request)
    return response
