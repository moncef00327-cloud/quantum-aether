# paypal_client.py
# عميل PayPal Orders v2 من جهة الخادم: إنشاء الطلب والتقاط الدفع والتحقق منه.
# يحتاج PAYPAL_CLIENT_ID وPAYPAL_CLIENT_SECRET (من developer.paypal.com > Apps & Credentials).
import time
from decimal import Decimal

import requests

API_BASE = {"live": "https://api-m.paypal.com", "sandbox": "https://api-m.sandbox.paypal.com"}


class PayPalError(Exception):
    def __init__(self, message, status=None, issue=None):
        super().__init__(message)
        self.status = status
        self.issue = issue


class PayPalClient:
    def __init__(self, client_id, client_secret, env="live", timeout=20, session=None):
        if env not in API_BASE:
            raise ValueError(f"PAYPAL_ENV must be one of {sorted(API_BASE)}")
        self.client_id = client_id
        self.client_secret = client_secret
        self.base = API_BASE[env]
        self.timeout = timeout
        self.http = session or requests.Session()
        self._token = None
        self._token_expires = 0.0

    def _access_token(self):
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        response = self.http.post(f"{self.base}/v1/oauth2/token", auth=(self.client_id, self.client_secret),
                                  data={"grant_type": "client_credentials"}, timeout=self.timeout)
        if response.status_code != 200:
            raise PayPalError("PayPal authentication failed", status=response.status_code)
        payload = response.json()
        self._token = payload["access_token"]
        self._token_expires = time.time() + int(payload.get("expires_in", 300))
        return self._token

    def _request(self, method, path, json=None, request_id=None):
        headers = {"Authorization": f"Bearer {self._access_token()}", "Content-Type": "application/json"}
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        response = self.http.request(method, f"{self.base}{path}", json=json, headers=headers, timeout=self.timeout)
        payload = response.json() if response.content else {}
        if response.status_code >= 400:
            details = payload.get("details") or [{}]
            raise PayPalError(payload.get("message", "PayPal request failed"), status=response.status_code,
                              issue=details[0].get("issue") or payload.get("name"))
        return payload

    def create_order(self, reference_id, amount, currency, description, return_url=None, cancel_url=None):
        body = {
            "intent": "CAPTURE",
            "purchase_units": [{
                "reference_id": reference_id,
                "custom_id": reference_id,
                "description": description,
                "amount": {"currency_code": currency, "value": amount},
            }],
        }
        if return_url:
            # طلب برابط موافقة (payer-action): يفتحه المشتري أو وكيله، ثم يعيده PayPal إلى return_url.
            body["payment_source"] = {"paypal": {"experience_context": {
                "return_url": return_url,
                "cancel_url": cancel_url or return_url,
                "user_action": "PAY_NOW",
                "shipping_preference": "NO_SHIPPING",
                "brand_name": "Quantum Aether",
            }}}
        return self._request("POST", "/v2/checkout/orders", json=body, request_id=f"create-{reference_id}-{int(time.time())}")

    def capture_order(self, order_id):
        return self._request("POST", f"/v2/checkout/orders/{order_id}/capture", request_id=f"capture-{order_id}")

    def get_order(self, order_id):
        return self._request("GET", f"/v2/checkout/orders/{order_id}")

    # ------------------------------------------------------------ الاشتراكات (Subscriptions v1)

    def create_product(self, name, description, home_url):
        body = {"name": name, "description": description, "type": "SERVICE", "category": "SOFTWARE",
                "home_url": home_url}
        return self._request("POST", "/v1/catalogs/products", json=body, request_id=f"product-{name}")

    def create_plan(self, product_id, name, description, price, currency):
        body = {
            "product_id": product_id,
            "name": name,
            "description": description,
            "status": "ACTIVE",
            "billing_cycles": [{
                "frequency": {"interval_unit": "MONTH", "interval_count": 1},
                "tenure_type": "REGULAR",
                "sequence": 1,
                "total_cycles": 0,
                "pricing_scheme": {"fixed_price": {"value": price, "currency_code": currency}},
            }],
            "payment_preferences": {"auto_bill_outstanding": True, "payment_failure_threshold": 2,
                                    "setup_fee_failure_action": "CANCEL"},
        }
        return self._request("POST", "/v1/billing/plans", json=body, request_id=f"plan-{product_id}-{name}")

    def get_subscription(self, subscription_id):
        return self._request("GET", f"/v1/billing/subscriptions/{subscription_id}")

    def cancel_subscription(self, subscription_id, reason):
        return self._request("POST", f"/v1/billing/subscriptions/{subscription_id}/cancel", json={"reason": reason})


# حالات الاشتراك في PayPal التي تعني أن الخدمة مدفوعة ويجب أن تعمل.
SUBSCRIPTION_LIVE_STATUSES = {"ACTIVE"}


def verify_subscription(subscription, expected_plan_id, expected_custom_id):
    """يعيد حالة الاشتراك في PayPal إن طابق الخطة والمرجع، وإلا 'MISMATCH'."""
    if subscription.get("plan_id") != expected_plan_id or subscription.get("custom_id") != expected_custom_id:
        return "MISMATCH"
    return subscription.get("status") or "UNKNOWN"


def verify_capture(order, expected_reference, expected_amount, expected_currency):
    """يعيد (الحالة, معرّف الالتقاط). الحالة COMPLETED فقط إذا طابق المبلغ والعملة والمرجع."""
    units = order.get("purchase_units") or [{}]
    unit = units[0]
    captures = (unit.get("payments") or {}).get("captures") or []
    capture = captures[0] if captures else {}
    amount = capture.get("amount") or {}
    reference = unit.get("reference_id") or capture.get("custom_id")
    matches = (
        reference == expected_reference
        and amount.get("currency_code") == expected_currency
        and amount.get("value") is not None
        and Decimal(amount["value"]) == Decimal(expected_amount)
    )
    if order.get("status") == "COMPLETED" and capture.get("status") == "COMPLETED" and matches:
        return "COMPLETED", capture.get("id")
    if capture.get("status") == "PENDING" and matches:
        return "PENDING", capture.get("id")
    return "FAILED", capture.get("id")
