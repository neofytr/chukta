"""The month-end close: what stops the books from closing, and a signed pack once nothing does."""
import datetime as dt
import hashlib
import json
import re

from .desk import _rupees, now, today
from .exports import tds_sections, verify_audit

OPEN_STATES = ("NEW", "HELD", "BLOCKED")
UNPAID_STATES = ("NEW", "HELD", "BLOCKED", "READY", "APPROVED")


def previous_month(day):
    first = dt.date.fromisoformat(day).replace(day=1)
    return (first - dt.timedelta(days=1)).strftime("%Y-%m")


def _item(key, title, ok, detail, link):
    return {"key": key, "title": title, "ok": bool(ok), "detail": detail, "link": link}


def close_payload(db, client_id, period=None, as_of=None):
    as_of = as_of or today()
    period = period or previous_month(as_of)
    if not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])", str(period)):
        raise ValueError("Choose a month")
    rows = db.execute("SELECT * FROM invoices WHERE client_id=? AND substr(invoice_date, 1, 7)=?", (client_id, period)).fetchall()
    count = lambda *states: sum(r["state"] in states for r in rows)
    live = [r for r in rows if r["state"] != "REJECTED"]
    ids = [r["id"] for r in live]
    marks = ",".join("?" * len(ids))
    missing = db.execute(f"SELECT invoice_id FROM findings WHERE check_name='gst' AND status='fail' AND invoice_id IN ({marks})", ids).fetchall() if ids else []
    missing_ids = {r[0] for r in missing}
    repeats = {r[0] for r in db.execute(f"SELECT invoice_id FROM findings WHERE check_name='duplicate' AND status='fail' AND invoice_id IN ({marks})", ids)} if ids else set()
    owed = [r for r in live if r["id"] not in repeats]  # A suspected duplicate is not a second debt.
    at_risk = sum(r["tax_paise"] or 0 for r in live if r["id"] in missing_ids and r["state"] != "PAID")
    imported = db.execute("SELECT 1 FROM gstr2b_imports WHERE client_id=? AND period=?", (client_id, period)).fetchone()
    soon = (dt.date.fromisoformat(as_of) + dt.timedelta(days=7)).isoformat()
    msme = [r for r in live if r["state"] in UNPAID_STATES and r["due_date"] and r["due_date"] <= soon]
    bank = db.execute("SELECT status, COUNT(*) n FROM bank_lines WHERE client_id=? AND substr(txn_date, 1, 7)=? GROUP BY status", (client_id, period)).fetchall()
    bank = {r["status"]: r["n"] for r in bank}
    problems = verify_audit(db, client_id)
    undecided, unissued = count(*OPEN_STATES), count("READY", "APPROVED")
    checks = [
        _item("decide", "Every invoice decided", rows and not undecided, f"{undecided} still need a person" if undecided else f"{len(rows)} decided" if rows else "No invoices for this month", "#/review"),
        _item("issue", "Signed payments issued", rows and not unissued, f"{unissued} ready or signed, not issued" if unissued else f"{count('PAID')} issued" if rows else "No invoices for this month", "#/today"),
        _item("gst", "GSTR-2B reconciled", imported and rows and not missing_ids, "Statement not imported" if not imported else "No invoices to reconcile" if not rows else f"{len(missing_ids)} missing, {_rupees(at_risk)} of credit at risk" if missing_ids else "Every invoice is in the statement", "#/vendors/books"),
        _item("msme", "No MSME payment at risk", not msme, f"{len(msme)} due by {min(r['due_date'] for r in msme)}" if msme else "None due within 7 days", "#/review"),
        _item("bank", "Bank statement posted", bank and not bank.get("HELD") and not bank.get("NEW"), "No statement imported for this month" if not bank else f"{bank.get('HELD', 0)} lines held" if bank.get("HELD") else f"{bank.get('POSTED', 0)} lines posted", "#/close/bank"),
        _item("audit", "Books replay clean", not problems, problems[0] if problems else "Every line replays", "#/audit/replay"),
    ]
    orders = db.execute("SELECT o.* FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id WHERE o.client_id=? AND i.state='PAID' AND substr(i.invoice_date, 1, 7)=?", (client_id, period)).fetchall()
    totals = {"invoiced": sum(r["amount_paise"] or 0 for r in owed), "duplicates": sum(r["amount_paise"] or 0 for r in live if r["id"] in repeats), "issued": sum(o["net_paise"] for o in orders), "tds": sum(o["tds_paise"] for o in orders),
              "retained": sum(o["retained_gst_paise"] for o in orders), "outstanding": sum(r["amount_paise"] or 0 for r in owed if r["state"] in UNPAID_STATES)}
    ageing = {"0-30 days": 0, "31-60 days": 0, "61-90 days": 0, "Over 90 days": 0}
    for r in owed:
        if r["state"] in UNPAID_STATES and r["invoice_date"] and r["amount_paise"]:
            days = (dt.date.fromisoformat(as_of) - dt.date.fromisoformat(r["invoice_date"])).days
            ageing["0-30 days" if days <= 30 else "31-60 days" if days <= 60 else "61-90 days" if days <= 90 else "Over 90 days"] += r["amount_paise"]
    pack = {"period": period, "invoices": sorted((r["id"], r["state"], r["amount_paise"]) for r in rows), "checks": [(c["key"], c["ok"]) for c in checks], "totals": totals}
    digest = hashlib.sha256(json.dumps(pack, sort_keys=True).encode()).hexdigest()
    closed = db.execute("SELECT signed_by, pack_hash, at FROM closes WHERE client_id=? AND period=?", (client_id, period)).fetchone()
    return {"period": period, "checks": checks, "ready": all(c["ok"] for c in checks), "done": sum(c["ok"] for c in checks), "count": len(rows),
            "totals": {k: _rupees(v) for k, v in totals.items()}, "ageing": [{"bucket": k, "amount": _rupees(v), "paise": v} for k, v in ageing.items()],
            "tds_by_section": [{"section": k, "amount": _rupees(v)} for k, v in tds_sections(db, orders).items()], "pack_hash": digest,
            "closed": ({"by": closed["signed_by"], "at": closed["at"], "changed": closed["pack_hash"] != digest} if closed else None),
            "periods": [r[0] for r in db.execute("SELECT DISTINCT substr(invoice_date, 1, 7) p FROM invoices WHERE client_id=? AND invoice_date IS NOT NULL ORDER BY p DESC", (client_id,))]}


def sign_close(db, client_id, period, by):
    if not by.strip():
        raise ValueError("Enter the reviewer's name first")
    pack = close_payload(db, client_id, period)
    if not pack["ready"]:
        raise ValueError("This month can't close yet: " + next(c["title"] for c in pack["checks"] if not c["ok"]).lower())
    with db:
        db.execute("INSERT OR REPLACE INTO closes VALUES(?,?,?,?,?)", (client_id, pack["period"], by.strip(), pack["pack_hash"], now()))
    return close_payload(db, client_id, period)
