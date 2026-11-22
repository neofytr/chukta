"""Razorpay test-mode payment requests. Refuses to run on a live key.

Uses Payment Links because Razorpay rejects a repeated reference_id on the server. Orders do not: a live test
created two orders with one receipt, and listing by receipt did not find the first.

ponytail: a Payment Link is a test-mode payment request. Settling to a vendor needs RazorpayX Payouts and an X account number.
"""
import base64
import hashlib
import http.client
import json
import pathlib
import time

from .desk import PaymentConflict, PaymentRejected, PaymentUnavailable, now
from .sources import http_call

API = "https://api.razorpay.com"
PACE_S = 1.5  # Razorpay returned 429 on a burst of about ten calls. Tune here if the account's limit differs.


class RazorpayBank:
    def __init__(self, db, key=None, secret=None, transport=http_call, sleep=time.sleep):
        if key is None:
            env = dict(l.split("=", 1) for l in (pathlib.Path(__file__).parent.parent / ".env").read_text().splitlines() if "=" in l)
            key, secret = env.get("RAZORPAY_KEY_ID", ""), env.get("RAZORPAY_KEY_SECRET", "")
        if not key.startswith("rzp_test_") or not secret:
            raise ValueError("Chukta runs only on Razorpay test keys")
        self.db, self.transport, self.sleep = db, transport, sleep
        self.auth = "Basic " + base64.b64encode(f"{key}:{secret}".encode()).decode()

    def _call(self, method, path, payload=None):
        headers = {"authorization": self.auth, "content-type": "application/json", "user-agent": "chukta/0.1"}
        body = json.dumps(payload).encode() if payload is not None else None
        for wait in (10, 20, 30, None):
            self.sleep(PACE_S)
            try:
                status, _, raw = self.transport(method, API + path, headers, body)
                reply = json.loads(raw)
            except (OSError, http.client.HTTPException) as e:
                raise PaymentUnavailable(f"Razorpay: {type(e).__name__}") from e
            except ValueError as e:
                raise PaymentUnavailable("Razorpay returned an unreadable reply") from e
            if status != 429:
                return status, reply
            if wait:  # A 429 means nothing was created, so repeating the same reference is safe.
                self.sleep(wait)
        raise PaymentUnavailable("Razorpay is rate limiting this key")

    def pay(self, key, account, ifsc, amount_paise):
        """Safe to repeat: Razorpay allows one link per reference, and a repeat returns the first one."""
        reference = "ck_" + hashlib.sha256(key.encode()).hexdigest()[:32]
        check = hashlib.sha256(f"{account}|{ifsc}|{amount_paise}".encode()).hexdigest()[:16]
        status, link = self._call("POST", "/v1/payment_links", {
            "amount": amount_paise, "currency": "INR", "accept_partial": False, "reference_id": reference,
            "description": "Chukta test-mode vendor payment (fictional)", "notify": {"sms": False, "email": False},
            "reminder_enable": False, "notes": {"source": "chukta-contextcon-test", "check": check}})
        if status == 400 and "already exists" in str(link.get("error", {}).get("description", "")):
            status, found = self._call("GET", f"/v1/payment_links?reference_id={reference}")
            links = found.get("payment_links") if isinstance(found, dict) else None
            if status != 200 or not links:
                raise PaymentUnavailable("Razorpay says this payment exists but did not return it")
            link = links[0]
        elif status == 400:
            raise PaymentRejected(str(link.get("error", {}).get("description") or "Razorpay refused the request").rstrip("."))
        elif status != 200:
            raise PaymentUnavailable(f"Razorpay returned HTTP {status}")
        notes = link.get("notes") if isinstance(link.get("notes"), dict) else {}
        if not link.get("id") or link.get("amount") != amount_paise or notes.get("check") != check or link.get("status") == "cancelled":
            raise PaymentConflict(key)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO provider_payments VALUES(?,?,?,?,?,?,?)",
                            (key, "razorpay_test", link["id"], account, ifsc, amount_paise, now()))
        return link["id"]
