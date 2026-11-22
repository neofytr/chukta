"""A receipt for every issued payment, with a proof code anyone can check.

Event rule: agents do not contact people outside the room. Mail is delivered only to RECEIPT_TEST_INBOX,
and the vendor's address is shown as the intended recipient. With no mail settings, receipts stay in the outbox.
A receipt is never sent twice: if a crash leaves delivery unknown, it is marked unclear for a person.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import smtplib
import ssl
from email.message import EmailMessage

from .desk import _mask, _rupees, now
from .sources import load_env

NOTE = "Test-mode payment request. No money has moved."


def _key(db):
    with db:
        db.execute("INSERT OR IGNORE INTO meta VALUES('receipt_key', ?)", (secrets.token_hex(32),))
    return bytes.fromhex(db.execute("SELECT value FROM meta WHERE key='receipt_key'").fetchone()[0])


def proof_code(db, order, reference):
    message = json.dumps([order["idempotency_key"], order["payee_name"], order["account"], order["ifsc"], order["net_paise"], reference]).encode()
    raw = base64.b32encode(hmac.new(_key(db), message, hashlib.sha256).digest()).decode()[:12]
    return f"CHK-{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def _facts(db, invoice_id):
    return db.execute("SELECT o.*, i.fields, i.payment_ref, i.state, c.name client FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id "
                      "JOIN clients c ON c.id=o.client_id WHERE o.invoice_id=?", (invoice_id,)).fetchone()


def _intended(db, row):
    """Only an address the vendor master holds, or one on the vendor's own verified domain. Never one an invoice merely claims."""
    vendor = db.execute("SELECT domain, emails FROM vendors WHERE client_id=? AND gstin=?", (row["client_id"], row["payee_gstin"])).fetchone()
    known = json.loads(vendor["emails"]) if vendor else []
    if known:
        return known[0]
    sent = json.loads(row["fields"]).get("sender_emails") or []
    return next((a for a in sent if vendor and a.split("@")[-1] == vendor["domain"]), None)


def mail_settings():
    env = load_env()
    needed = ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "RECEIPT_TEST_INBOX")
    return {k: env[k] for k in env if k.startswith(("SMTP_", "RECEIPT_"))} if all(env.get(k) for k in needed) else None


def _html(value):
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_message(r, settings):
    text = (f"Payment receipt from {r['client']}\n\nPaid to: {r['payee']}\nAccount: {r['account']}\nInvoice: {r['number']}\nGross: {r['gross']}\nTDS deducted: {r['tds']}\n"
            f"GST retained: {r['retained']}\nNet: {r['net']}\nReference: {r['reference']}\nProof code: {r['code']}\n\n{NOTE}\n"
            f"We will never ask you to change bank details by email.\n\nIntended for: {r['intended'] or 'no address on file'}. Delivered to the team's test inbox under the event rules.")
    msg = EmailMessage()
    msg["Subject"] = f"Receipt: {r['net']} for invoice {r['number']}"
    msg["From"] = settings.get("RECEIPT_FROM") or settings["SMTP_USER"]
    msg["To"] = settings["RECEIPT_TEST_INBOX"]
    msg["Message-ID"] = f"<{r['code'].lower()}@chukta.receipt>"  # The same receipt always has the same ID.
    msg["X-Chukta-Intended-For"] = r["intended"] or "none"
    msg.set_content(text)
    rows = "".join(f'<tr><td style="padding:7px 0;color:#5b6472">{a}</td><td style="padding:7px 0;text-align:right;font-weight:600">{b}</td></tr>' for a, b in (("Invoice", _html(r["number"])), ("Account", r["account"]), ("Gross", r["gross"]), ("TDS deducted", r["tds"]), ("GST retained", r["retained"]), ("Reference", _html(r["reference"]))))
    msg.add_alternative(f"""<div style="background:#e9eef7;padding:28px 12px;font-family:'Google Sans',Roboto,Arial,sans-serif;color:#191c20"><div style="max-width:460px;margin:auto;background:#fff;border-radius:34px 34px 12px 12px;padding:32px">
<div style="color:#0061a3;font-weight:600">Payment receipt</div><div style="font-size:15px;color:#5b6472;margin-top:2px">{_html(r['client'])} to {_html(r['payee'])}</div>
<div style="font-size:42px;font-weight:600;margin:16px 0 12px">{r['net']}</div><table style="width:100%;border-collapse:collapse;font-size:14px">{rows}</table>
<div style="margin-top:18px;background:#d4e3ff;border-radius:18px;padding:14px 16px;text-align:center"><div style="font-size:12px;color:#06365d">Proof code</div><div style="font:600 18px monospace;color:#06365d">{r['code']}</div></div>
<p style="font-size:12px;color:#5b6472;margin:16px 0 0">{NOTE} We will never ask you to change bank details by email.</p><p style="font-size:12px;color:#5b6472;margin:6px 0 0">Intended for {_html(r['intended'] or 'no address on file')}. Delivered to the team's test inbox under the event rules.</p></div></div>""", subtype="html")
    return msg


def smtp_send(message, settings):
    """Returns only after the server accepts it. Raises ConnectionError if nothing can have been delivered."""
    host, port = settings["SMTP_HOST"], int(settings.get("SMTP_PORT") or 587)
    try:
        server = smtplib.SMTP_SSL(host, port, timeout=15, context=ssl.create_default_context()) if port == 465 else smtplib.SMTP(host, port, timeout=15)
        if port != 465:
            server.starttls(context=ssl.create_default_context())
        server.login(settings["SMTP_USER"], settings["SMTP_PASSWORD"])
    except (OSError, smtplib.SMTPException) as e:
        raise ConnectionError(type(e).__name__) from e
    with server:
        server.send_message(message)


def issue_receipts(db, client_id, send=smtp_send, settings=None):
    """Safe to call again and again. Each receipt is claimed once before any mail is attempted."""
    settings = mail_settings() if settings is None else settings
    for row in db.execute("SELECT o.invoice_id FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id LEFT JOIN receipts r ON r.invoice_id=o.invoice_id "
                          "WHERE o.client_id=? AND i.state='PAID' AND r.invoice_id IS NULL ORDER BY o.invoice_id", (client_id,)).fetchall():
        f = _facts(db, row[0])
        code = proof_code(db, f, f["payment_ref"])
        with db:
            db.execute("INSERT OR IGNORE INTO receipts(invoice_id, client_id, code, intended, status, at) VALUES(?,?,?,?,?,?)",
                       (f["invoice_id"], client_id, code, _intended(db, f), "queued", now()))
    if not settings:
        with db:
            db.execute("UPDATE receipts SET status='outbox', at=? WHERE client_id=? AND status='queued'", (now(), client_id))
        return
    for row in db.execute("SELECT invoice_id FROM receipts WHERE client_id=? AND status='queued' ORDER BY invoice_id", (client_id,)).fetchall():
        with db:
            claimed = db.execute("UPDATE receipts SET status='sending', at=? WHERE invoice_id=? AND status='queued'", (now(), row[0])).rowcount
        if not claimed:
            continue
        r = receipt(db, row[0])
        try:
            send(build_message(r, settings), settings)
            outcome = ("sent", settings["RECEIPT_TEST_INBOX"])
        except ConnectionError:
            outcome = ("failed", None)  # Never reached the server, so it is safe to try again.
        except (OSError, smtplib.SMTPException):
            outcome = ("unclear", None)  # It may have been delivered, so it is never resent automatically.
        with db:
            db.execute("UPDATE receipts SET status=?, delivered_to=?, at=? WHERE invoice_id=?", (outcome[0], outcome[1], now(), row[0]))


def mark_interrupted(db):
    with db:
        db.execute("UPDATE receipts SET status='unclear', at=? WHERE status='sending'", (now(),))


def retry_failed(db, client_id):
    with db:
        db.execute("UPDATE receipts SET status='queued' WHERE client_id=? AND status IN ('failed', 'outbox')", (client_id,))
    issue_receipts(db, client_id)


def receipt(db, invoice_id):
    r = db.execute("SELECT * FROM receipts WHERE invoice_id=?", (invoice_id,)).fetchone()
    f = r and _facts(db, invoice_id)
    if not r or not f:
        return None
    return {"invoice_id": invoice_id, "code": r["code"], "status": r["status"], "intended": r["intended"], "delivered_to": r["delivered_to"], "at": r["at"], "client": f["client"],
            "payee": f["payee_name"], "account": _mask(f["account"]), "number": json.loads(f["fields"]).get("invoice_no"), "gross": _rupees(f["gross_paise"]), "tds": _rupees(f["tds_paise"]),
            "retained": _rupees(f["retained_gst_paise"]), "net": _rupees(f["net_paise"]), "reference": f["payment_ref"], "signed_by": f["approved_by"], "note": NOTE}


def receipts_payload(db, client_id):
    rows = [receipt(db, r[0]) for r in db.execute("SELECT invoice_id FROM receipts WHERE client_id=? ORDER BY invoice_id", (client_id,))]
    settings = mail_settings()
    return {"receipts": rows, "mail_on": bool(settings), "inbox": (settings or {}).get("RECEIPT_TEST_INBOX")}


def verify_code(db, client_id, code):
    """Recomputes the proof from the signed order. An edited amount or a made-up code cannot pass."""
    code = re.sub(r"\s+", "", str(code or "")).upper()
    r = db.execute("SELECT invoice_id FROM receipts WHERE client_id=? AND code=?", (client_id, code)).fetchone()
    if not r:
        return {"genuine": False, "reason": "No payment was issued with this code."}
    f = _facts(db, r[0])
    if not hmac.compare_digest(proof_code(db, f, f["payment_ref"]), code):
        return {"genuine": False, "reason": "This payment's record has changed since the receipt was issued."}
    out = receipt(db, r[0])
    return {"genuine": True, "payee": out["payee"], "account": out["account"], "net": out["net"], "number": out["number"], "reference": out["reference"], "signed_by": out["signed_by"], "at": out["at"]}
