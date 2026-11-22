"""The finished work: a bank file, Tally-ready vouchers, and an audit file that can be replayed."""
import csv
import io
import json

from .desk import evidence_hash, now


def _safe(value):
    """Stops a vendor-supplied value from running as a spreadsheet formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _csv(header, rows):
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows([_safe(c) for c in row] for row in rows)
    return out.getvalue()


def _money(paise):
    return f"{(paise or 0) / 100:.2f}"


def _orders(db, client_id):
    return db.execute("SELECT o.*, i.fields, i.invoice_date, i.taxable_paise, i.tax_paise, i.state, i.payment_ref, i.po FROM payment_orders o "
                      "JOIN invoices i ON i.id=o.invoice_id WHERE o.client_id=? AND i.state IN ('APPROVED','PAID') ORDER BY o.invoice_id",
                      (client_id,)).fetchall()


def bank_file(db, client_id):
    rows = [(o["payee_name"], o["account"], o["ifsc"], _money(o["net_paise"]), json.loads(o["fields"])["invoice_no"], o["payment_ref"] or "",
             o["state"]) for o in _orders(db, client_id)]
    return _csv(("beneficiary", "account", "ifsc", "amount_inr", "narration", "provider_reference", "status"), rows)


def tally_vouchers(db, client_id):
    rows = [(o["invoice_date"], "Purchase", o["payee_name"], o["payee_gstin"], json.loads(o["fields"])["invoice_no"], o["po"], _money(o["taxable_paise"]),
             _money(o["tax_paise"]), _money(o["gross_paise"]), _money(o["tds_paise"]), _money(o["retained_gst_paise"]), _money(o["net_paise"]),
             o["payment_ref"] or "") for o in _orders(db, client_id)]
    return _csv(("date", "voucher_type", "party", "party_gstin", "invoice_no", "po", "taxable", "gst", "gross", "tds_draft", "gst_retained",
                 "net_paid", "payment_reference"), rows)


def verify_audit(db, client_id):
    """Replays the books. Returns every broken promise, so an empty list means the books hold."""
    problems = []
    for o in db.execute("SELECT * FROM payment_orders WHERE client_id=?", (client_id,)).fetchall():
        i = o["invoice_id"]
        if o["net_paise"] != o["gross_paise"] - o["tds_paise"] - o["retained_gst_paise"]:
            problems.append(f"Invoice {i}: net does not equal gross less TDS and retained GST.")
        if evidence_hash(db, i) != o["evidence_hash"]:
            problems.append(f"Invoice {i}: evidence changed after sign-off.")
        if not db.execute("SELECT 1 FROM events WHERE invoice_id=? AND event='approved' AND actor=?", (i, o["approved_by"])).fetchone():
            problems.append(f"Invoice {i}: no sign-off event from {o['approved_by']}.")
        paid = db.execute("SELECT * FROM provider_payments WHERE idempotency_key=?", (o["idempotency_key"],)).fetchone()
        if paid and (paid["account"], paid["ifsc"], paid["amount_paise"]) != (o["account"], o["ifsc"], o["net_paise"]):
            problems.append(f"Invoice {i}: payment differs from what was signed.")
    for r in db.execute("SELECT i.id, i.payment_ref, p.ref FROM invoices i LEFT JOIN payment_orders o ON o.invoice_id=i.id "
                        "LEFT JOIN provider_payments p ON p.idempotency_key=o.idempotency_key WHERE i.client_id=? AND i.state='PAID'", (client_id,)):
        if not r["ref"] or r["ref"] != r["payment_ref"]:
            problems.append(f"Invoice {r['id']}: marked paid without a matching provider payment.")
    for r in db.execute("SELECT i.fingerprint, COUNT(*) n FROM invoices i WHERE i.client_id=? AND i.state='PAID' GROUP BY i.fingerprint HAVING n>1", (client_id,)):
        problems.append(f"Vendor invoice {r['fingerprint'][:12]} was paid {r['n']} times.")
    return problems


def audit_file(db, client_id):
    invoices = []
    for inv in db.execute("SELECT * FROM invoices WHERE client_id=? ORDER BY id", (client_id,)).fetchall():
        i = inv["id"]
        order = db.execute("SELECT * FROM payment_orders WHERE invoice_id=?", (i,)).fetchone()
        note = db.execute("SELECT * FROM investigations WHERE invoice_id=?", (i,)).fetchone()
        fields = json.loads(inv["fields"])
        fields.pop("usage", None)
        invoices.append({
            "invoice_id": i, "state": inv["state"], "fields": fields, "payment_reference": inv["payment_ref"],
            "findings": [dict(r) for r in db.execute("SELECT check_name, status, severity, detail, source, retrieved_at FROM findings WHERE invoice_id=?", (i,))],
            "events": [dict(r) for r in db.execute("SELECT event, actor, detail, at FROM events WHERE invoice_id=? ORDER BY id", (i,))],
            "signed_order": dict(order) if order else None, "investigation": dict(note) if note else None})
    ledger = [dict(r) for r in db.execute("SELECT run_id, source, request, credits, usd, outcome, at FROM ledger ORDER BY id")]
    return {"client_id": client_id, "exported_at": now(), "replay_problems": verify_audit(db, client_id), "invoices": invoices, "ledger": ledger}
