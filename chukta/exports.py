"""The finished work: a bank file, Tally-ready vouchers, and an audit file that can be replayed."""
import csv
import io
import json
import sqlite3
import hashlib
import re

from .desk import _mask, _rupees, decide, event_hash, evidence_hash, now
from .records import mask_text


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
    rows = [(o["payee_name"], o["account"], o["ifsc"], "RTGS" if o["net_paise"] >= 2_00_000_00 else "NEFT", _money(o["net_paise"]), json.loads(o["fields"])["invoice_no"], o["payment_ref"] or "",
             o["state"]) for o in _orders(db, client_id)]
    return _csv(("beneficiary", "account", "ifsc", "mode", "amount_inr", "narration", "provider_reference", "status"), rows)


def tally_vouchers(db, client_id):
    rows = [(o["invoice_date"], "Purchase", o["payee_name"], o["payee_gstin"], json.loads(o["fields"])["invoice_no"], o["po"], _money(o["taxable_paise"]),
             _money(o["tax_paise"]), _money(o["gross_paise"]), _money(o["tds_paise"]), _money(o["retained_gst_paise"]), _money(o["net_paise"]),
             o["payment_ref"] or "") for o in _orders(db, client_id)]
    return _csv(("date", "voucher_type", "party", "party_gstin", "invoice_no", "po", "taxable", "gst", "gross", "tds_draft", "gst_retained",
                 "net_paid", "payment_reference"), rows)


def verify_audit(db, client_id):
    """Replays the books. Returns every broken promise, so an empty list means the books hold."""
    problems = []
    previous = ""
    for e in db.execute("SELECT * FROM events ORDER BY id"):
        if e["prev_hash"] != previous or e["hash"] != event_hash(previous, e["invoice_id"], e["event"], e["actor"], e["detail"], e["at"]):
            problems.append(f"Audit trail altered at event {e['id']}.")
            break
        previous = e["hash"]
    for r in db.execute("SELECT id, state FROM invoices WHERE client_id=? AND state IN ('READY','HELD','BLOCKED')", (client_id,)).fetchall():
        rows = [tuple(x) for x in db.execute("SELECT invoice_id, check_name, status, severity FROM findings WHERE invoice_id=?", (r["id"],))]
        if rows and decide(rows) != r["state"]:
            problems.append(f"Invoice {r['id']}: its decision does not follow from its evidence.")
    for r in db.execute("SELECT i.id FROM invoices i WHERE i.client_id=? AND i.state='PAID' AND NOT EXISTS (SELECT 1 FROM events e WHERE e.invoice_id=i.id AND e.event='paid')", (client_id,)):
        problems.append(f"Invoice {r['id']}: issued with no payment event.")
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


def tds_sections(db, orders):
    """TDS grouped by the section its finding cites. A reviewer's own figure is labelled as theirs."""
    sections = {}
    for o in orders:
        if o["tds_paise"]:
            found = db.execute("SELECT detail FROM findings WHERE invoice_id=? AND check_name='tds'", (o["invoice_id"],)).fetchone()
            entry = re.search(r"(s\.393\(1\) Table \S+?)[.:]?(?:\s|$)", found[0]) if found else None
            label = entry.group(1) if entry and _rupees(o["tds_paise"]) in found[0] else "Entered by the reviewer"
            sections[label] = sections.get(label, 0) + o["tds_paise"]
    return dict(sorted(sections.items()))


def replay_story(db, client_id):
    """Replays the books line by line from what was stored, and says exactly which promise broke on which line."""
    previous, broken_at = "", None
    events = db.execute("SELECT * FROM events ORDER BY id").fetchall()
    for e in events:
        if e["prev_hash"] != previous or e["hash"] != event_hash(previous, e["invoice_id"], e["event"], e["actor"], e["detail"], e["at"]):
            broken_at = e["id"]
            break
        previous = e["hash"]
    lines = []
    for inv in db.execute("SELECT i.*, v.name vendor FROM invoices i LEFT JOIN vendors v ON v.client_id=i.client_id AND v.gstin=i.gstin WHERE i.client_id=? ORDER BY i.id", (client_id,)).fetchall():
        i, steps = inv["id"], []
        step = lambda title, ok, detail: steps.append({"title": title, "ok": bool(ok), "detail": detail})
        step("Original document", hashlib.sha256(" ".join(inv["raw"].split()).encode()).hexdigest() == inv["raw_hash"], f"Fingerprint {inv['raw_hash'][:10]} matches the text received")
        found = [tuple(r) for r in db.execute("SELECT invoice_id, check_name, status, severity FROM findings WHERE invoice_id=?", (i,))]
        flagged = sum(r[2] not in ("pass", "info") for r in found)
        step("Checks on file", found, f"{len(found)} checks, {flagged} flagged")
        decided = decide(found) if found else None
        fits = {"READY": decided == "READY", "HELD": decided == "HELD", "BLOCKED": decided == "BLOCKED", "APPROVED": decided in ("READY", "HELD"), "PAID": decided in ("READY", "HELD"), "REJECTED": True}.get(inv["state"], False)
        step("Decision follows from evidence", fits, f"Evidence says {str(decided).title()}, books say {inv['state'].title()}")
        o = db.execute("SELECT * FROM payment_orders WHERE invoice_id=?", (i,)).fetchone()
        if o:
            signed = db.execute("SELECT 1 FROM events WHERE invoice_id=? AND event='approved' AND actor=?", (i, o["approved_by"])).fetchone()
            step("Signed by a named person", signed and evidence_hash(db, i) == o["evidence_hash"], f"{o['approved_by']}, on the evidence shown at the time")
            step("The arithmetic holds", o["net_paise"] == o["gross_paise"] - o["tds_paise"] - o["retained_gst_paise"],
                 f"{_rupees(o['gross_paise'])} less {_rupees(o['tds_paise'])} TDS and {_rupees(o['retained_gst_paise'])} GST is {_rupees(o['net_paise'])}")
            paid = db.execute("SELECT * FROM provider_payments WHERE idempotency_key=?", (o["idempotency_key"],)).fetchone()
            if inv["state"] == "PAID":
                step("Right account, right amount", paid and (paid["account"], paid["ifsc"], paid["amount_paise"]) == (o["account"], o["ifsc"], o["net_paise"]), f"{_rupees(paid['amount_paise']) if paid else 'No payment'} to {_mask(o['account'])}")
                times = db.execute("SELECT COUNT(*) FROM invoices WHERE client_id=? AND fingerprint=? AND state='PAID'", (client_id, inv["fingerprint"])).fetchone()[0]
                step("Paid exactly once", times == 1 and paid and paid["ref"] == inv["payment_ref"], f"{times} payment, reference {inv['payment_ref']}")
        own = [e["id"] for e in events if e["invoice_id"] == i]
        step("Audit trail unbroken", broken_at is None or not own or max(own) < broken_at, f"{len(own)} hash-chained events")
        lines.append({"id": i, "vendor": inv["vendor"] or "Unknown vendor", "number": json.loads(inv["fields"]).get("invoice_no"), "state": inv["state"],
                      "amount": _rupees(inv["amount_paise"]) if inv["amount_paise"] else "Unclear", "ok": all(s["ok"] for s in steps), "steps": steps})
    return {"lines": lines, "ok": broken_at is None and all(l["ok"] for l in lines), "steps": sum(len(l["steps"]) for l in lines), "bad": [l["id"] for l in lines if not l["ok"]], "events": len(events)}


def tamper_story(db, client_id):
    """Adds one rupee to a signed payment in a private copy, so the real books are never touched."""
    copy = sqlite3.connect(":memory:")
    db.backup(copy)
    copy.row_factory = sqlite3.Row
    target = copy.execute("SELECT o.invoice_id FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id WHERE o.client_id=? AND i.state='PAID' ORDER BY o.invoice_id LIMIT 1", (client_id,)).fetchone()
    if not target:
        raise ValueError("Issue a payment run first")
    with copy:
        copy.execute("UPDATE payment_orders SET net_paise=net_paise+100 WHERE invoice_id=?", (target[0],))
    out = replay_story(copy, client_id) | {"tampered": target[0]}
    copy.close()
    return out


def replay_lines(db, client_id):
    """One row per signed payment, so a reviewer can watch the books replay."""
    problems = verify_audit(db, client_id)
    rows = []
    totals = {"gross": 0, "tds": 0, "retained": 0, "net": 0}
    orders = db.execute("SELECT o.*, i.state, i.fields, i.payment_ref, i.due_date FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id WHERE o.client_id=? "
                        "ORDER BY o.invoice_id", (client_id,)).fetchall()
    for o in orders:
        own = [p for p in problems if p.startswith(f"Invoice {o['invoice_id']}:")]
        rows.append({"id": o["invoice_id"], "number": json.loads(o["fields"]).get("invoice_no"), "payee": o["payee_name"], "gross": _rupees(o["gross_paise"]),
                     "tds": _rupees(o["tds_paise"]), "retained": _rupees(o["retained_gst_paise"]), "net": _rupees(o["net_paise"]), "signed_by": o["approved_by"],
                     "reference": o["payment_ref"], "state": o["state"], "ok": not own, "problems": own, "account": _mask(o["account"]), "ifsc": o["ifsc"], "due": o["due_date"]})
        for key, column in (("gross", "gross_paise"), ("tds", "tds_paise"), ("retained", "retained_gst_paise"), ("net", "net_paise")):
            totals[key] += o[column]
    sections = tds_sections(db, orders)
    return {"lines": rows, "problems": problems, "ok": not problems, "totals": {k: _rupees(v) for k, v in totals.items()},
            "tds_by_section": [{"section": k, "amount": _rupees(v)} for k, v in sorted(sections.items())]}


def audit_file(db, client_id):
    invoices = []
    for inv in db.execute("SELECT * FROM invoices WHERE client_id=? ORDER BY id", (client_id,)).fetchall():
        i = inv["id"]
        order = db.execute("SELECT * FROM payment_orders WHERE invoice_id=?", (i,)).fetchone()
        note = db.execute("SELECT * FROM investigations WHERE invoice_id=?", (i,)).fetchone()
        fields = json.loads(inv["fields"])
        fields.pop("usage", None)
        fields["accounts"] = [_mask(a) for a in fields.get("accounts", [])]  # Only the data an audit needs.
        fields["reader_notes"] = [mask_text(n) for n in fields.get("reader_notes", [])]
        fields["sender_emails"] = sorted({e.split("@")[-1] for e in fields.get("sender_emails", [])})
        invoices.append({
            "invoice_id": i, "state": inv["state"], "fields": fields, "payment_reference": inv["payment_ref"],
            "findings": [dict(r) for r in db.execute("SELECT check_name, status, severity, detail, source, retrieved_at FROM findings WHERE invoice_id=?", (i,))],
            "events": [dict(r) for r in db.execute("SELECT event, actor, detail, at FROM events WHERE invoice_id=? ORDER BY id", (i,))],
            "signed_order": {**dict(order), "account": _mask(order["account"])} if order else None, "investigation": dict(note) if note else None})
    ledger = [dict(r) for r in db.execute("SELECT run_id, source, request, credits, usd, outcome, at FROM ledger ORDER BY id")]
    return {"client_id": client_id, "exported_at": now(), "replay_problems": verify_audit(db, client_id), "invoices": invoices, "ledger": ledger,
            "bank_lines": [dict(r) for r in db.execute("SELECT txn_date, narration, amount_paise, payee, account, status, reason, source, retrieved_at, resolved_by "
                                                       "FROM bank_lines WHERE client_id=? ORDER BY id", (client_id,))]}
