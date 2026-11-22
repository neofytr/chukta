"""Chukta reviewer app.

python3 app.py           start on http://127.0.0.1:8765 and resume any interrupted work
python3 app.py --reset   delete the local demo books first
"""
import json
import os
import pathlib
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from chukta.demo import BATCH, CLIENT, CLIENT_NAME, seed
from chukta.desk import (HARD_STOPS, SandboxBank, _rupees, add_alias, approve, compute_tds, connect, ingest, now, pay_approved, process,
                         recheck, reject)
from chukta.exports import audit_file, bank_file, tally_vouchers, verify_audit
from chukta.investigator import investigate
from chukta.razorpay import RazorpayBank
from chukta.reader import logged_reader
from chukta.sources import Sources

ROOT = pathlib.Path(__file__).parent
DB = str(ROOT / "chukta.db")
PORT = int(os.environ.get("CHUKTA_PORT", 8765))
CREDIT_LIMIT, TIME_LIMIT_S = 10.0, 900  # Ceiling for each run.
PAY_DELAY_S = float(os.environ.get("CHUKTA_PAY_DELAY", 0))  # Set to 3 to make a kill during payment easy to show.
MAX_BODY = 1_000_000
JOB = {"running": False, "name": "", "message": "", "error": ""}
JOB_LOCK = threading.Lock()
ORDER = {"BLOCKED": 0, "HELD": 1, "NEW": 2, "READY": 3, "APPROVED": 4, "PAID": 5, "REJECTED": 6}


def bank_for(db):
    try:
        return RazorpayBank(db)
    except (ValueError, OSError):
        return SandboxBank(db)


class SlowBank:
    """Waits after the provider call, which is the exact moment a crash is most dangerous."""

    def __init__(self, inner):
        self.inner = inner

    def pay(self, *args):
        ref = self.inner.pay(*args)
        if PAY_DELAY_S:
            time.sleep(PAY_DELAY_S)
        return ref


def start_job(name, target, *args):
    with JOB_LOCK:
        if JOB["running"]:
            return False
        JOB.update(running=True, name=name, message="Starting", error="")

    def wrapped():
        try:
            target(*args)
            JOB["message"] = "Done"
        except Exception as e:  # The app must stay up and show the failure. Work resumes on the next run.
            JOB.update(error=f"{type(e).__name__}: {e}", message="Stopped")
        finally:
            JOB["running"] = False
    threading.Thread(target=wrapped, daemon=True).start()
    return True


def run_batch(texts):
    db = connect(DB)
    run_id = f"run-{int(time.time())}"
    read = logged_reader(db, run_id)
    for n, text in enumerate(texts, 1):
        JOB["message"] = f"Reading invoice {n} of {len(texts)}"
        ingest(db, CLIENT, text, read)
    JOB["message"] = "Checking against records"
    process(db, Sources(db, run_id, credit_limit=CREDIT_LIMIT, time_limit_s=TIME_LIMIT_S))
    todo = db.execute("SELECT id FROM invoices i WHERE state IN ('HELD','BLOCKED') AND NOT EXISTS "
                      "(SELECT 1 FROM investigations n WHERE n.invoice_id=i.id)").fetchall()
    for n, row in enumerate(todo, 1):
        JOB["message"] = f"Investigating exception {n} of {len(todo)}"
        investigate(db, row[0], run_id)
    db.close()


def run_pay(run_row):
    db = connect(DB)
    JOB["message"] = "Releasing signed payments"
    pay_approved(db, SlowBank(bank_for(db)))
    left = db.execute("SELECT COUNT(*) FROM invoices WHERE state='APPROVED'").fetchone()[0]
    if not left:
        with db:
            db.execute("UPDATE pay_runs SET finished_at=? WHERE finished_at IS NULL", (now(),))
    db.close()
    if left:  # The run stays open, so a restart or another release finishes it.
        raise RuntimeError(f"{left} signed payments did not go through and are safe to retry")


def resume():
    """After a crash: finish unchecked invoices, then any payment run a person already released."""
    db = connect(DB)
    seed(db)
    new = db.execute("SELECT COUNT(*) FROM invoices WHERE state='NEW'").fetchone()[0]
    missing = db.execute("SELECT COUNT(*) FROM invoices i WHERE state IN ('HELD','BLOCKED') AND NOT EXISTS "
                         "(SELECT 1 FROM investigations n WHERE n.invoice_id=i.id)").fetchone()[0]
    open_run = db.execute("SELECT id FROM pay_runs WHERE finished_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    db.close()

    def work():
        if new or missing:
            run_batch([])
        if open_run:
            run_pay(open_run[0])
    if new or missing or open_run:
        start_job("Resuming after restart", work)
        return True
    return False


def mask_accounts(text):
    return re.sub(r"\b\d(?:[ -]?\d){8,17}\b", lambda m: "****" + re.sub(r"\D", "", m.group(0))[-4:], text)


def state_payload(db):
    rows = db.execute("SELECT i.*, v.name vendor_name, o.net_paise order_net, n.action_text FROM invoices i "
                      "LEFT JOIN vendors v ON v.client_id=i.client_id AND v.gstin=i.gstin LEFT JOIN payment_orders o ON o.invoice_id=i.id "
                      "LEFT JOIN investigations n ON n.invoice_id=i.id WHERE i.client_id=?", (CLIENT,)).fetchall()
    out, ready_net = [], 0
    for r in rows:
        f = json.loads(r["fields"])
        net = r["order_net"]
        if net is None and r["amount_paise"] and r["vendor_name"] and r["state"] in ("READY", "HELD", "BLOCKED"):
            vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (r["client_id"], r["gstin"])).fetchone()
            tds = compute_tds(db, vendor, r)[0]
            net = r["amount_paise"] - tds if tds is not None else None
        if r["state"] == "READY" and net:
            ready_net += net
        reason = db.execute("SELECT detail FROM findings WHERE invoice_id=? AND status NOT IN ('pass','info') "
                            "ORDER BY severity='block' DESC LIMIT 1", (r["id"],)).fetchone()
        out.append({"id": r["id"], "number": f.get("invoice_no") or "No number", "vendor": r["vendor_name"] or "Unknown vendor", "date": r["invoice_date"],
                    "state": r["state"], "gross": _rupees(r["amount_paise"]) if r["amount_paise"] else "Unclear", "net": _rupees(net) if net else "",
                    "due": r["due_date"], "reason": reason[0] if reason else "", "action": r["action_text"] or ""})
    out.sort(key=lambda x: (ORDER.get(x["state"], 9), x["due"] or "9999", x["id"]))
    counts = {s: sum(1 for x in out if x["state"] == s) for s in ORDER}
    credits, usd, calls = db.execute("SELECT COALESCE(SUM(credits),0), COALESCE(SUM(usd),0), COUNT(*) FROM ledger").fetchone()
    paid = db.execute("SELECT COALESCE(SUM(net_paise),0) FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id WHERE i.state='PAID'").fetchone()[0]
    return {"client": CLIENT_NAME, "provider": "Razorpay test mode" if isinstance(bank_for(db), RazorpayBank) else "Local sandbox",
            "invoices": out, "counts": counts, "ready_net": _rupees(ready_net), "paid_net": _rupees(paid), "job": dict(JOB),
            "cost": {"credits": round(credits, 2), "usd": round(usd, 4), "calls": calls, "per_invoice_credits": round(credits / len(out), 2) if out else 0},
            "audit_problems": verify_audit(db, CLIENT), "payable_now": counts["APPROVED"],
            "open_pay_run": bool(db.execute("SELECT 1 FROM pay_runs WHERE finished_at IS NULL").fetchone())}


def invoice_payload(db, invoice_id):
    r = db.execute("SELECT * FROM invoices WHERE id=? AND client_id=?", (invoice_id, CLIENT)).fetchone()
    if not r:
        return None
    fields = json.loads(r["fields"])
    findings = [dict(x) for x in db.execute("SELECT check_name, status, severity, detail, source, retrieved_at FROM findings WHERE invoice_id=? "
                                            "ORDER BY severity='block' DESC, status='pass', status='info', check_name", (invoice_id,))]
    failing = {x["check_name"] for x in findings if x["status"] not in ("pass", "info")}
    vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (r["client_id"], r["gstin"])).fetchone()
    tds = compute_tds(db, vendor, r)[0] if vendor else None
    note = db.execute("SELECT * FROM investigations WHERE invoice_id=?", (invoice_id,)).fetchone()
    order = db.execute("SELECT gross_paise, tds_paise, retained_gst_paise, net_paise, approved_by FROM payment_orders WHERE invoice_id=?", (invoice_id,)).fetchone()
    company = next((x for x in findings if x["check_name"] == "company"), None)
    return {"id": r["id"], "state": r["state"], "number": fields.get("invoice_no"), "date": r["invoice_date"], "po": r["po"],
            "vendor": vendor["name"] if vendor else "Unknown vendor", "gstin": r["gstin"],
            "gross": _rupees(r["amount_paise"]) if r["amount_paise"] else "Unclear", "taxable": _rupees(r["taxable_paise"]) if r["taxable_paise"] else "Unclear",
            "tax": _rupees(r["tax_paise"]) if r["tax_paise"] else "Unclear", "tds": _rupees(tds) if tds is not None else "Needs a person",
            "due": r["due_date"], "findings": findings, "reader_notes": fields.get("reader_notes", []),
            "events": [dict(x) for x in db.execute("SELECT event, actor, detail, at FROM events WHERE invoice_id=? ORDER BY id", (invoice_id,))],
            "investigation": {**dict(note), "citations": json.loads(note["citations"])} if note else None,
            "order": {k: _rupees(order[k]) for k in ("gross_paise", "tds_paise", "retained_gst_paise", "net_paise")} | {"by": order["approved_by"]} if order else None,
            "payment_ref": r["payment_ref"], "raw": mask_accounts(r["raw"]),
            "can_approve": r["state"] in ("READY", "HELD") and not (failing & set(HARD_STOPS)), "needs_tds": tds is None and bool(vendor),
            "can_retain_gst": "gst" in failing and bool(r["tax_paise"]),
            "can_alias": bool(company and company["status"] == "unverified" and "resolves to" in company["detail"])}


class Handler(BaseHTTPRequestHandler):
    server_version = "Chukta"
    sys_version = ""

    def log_message(self, *args):
        pass

    def _send(self, code, body, kind="application/json", name=None):
        data = body if isinstance(body, bytes) else (body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode())
        self.send_response(code)
        self.send_header("content-type", kind)
        self.send_header("content-length", str(len(data)))
        self.send_header("x-content-type-options", "nosniff")
        self.send_header("cache-control", "no-store")
        self.send_header("content-security-policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        if name:
            self.send_header("content-disposition", f'attachment; filename="{name}"')
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        return self.headers.get("host") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        path = self.path.split("?")[0]
        if path == "/":
            return self._send(200, (ROOT / "ui.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/favicon.ico":
            return self._send(204, b"")
        db = connect(DB)
        try:
            if path == "/api/state":
                return self._send(200, state_payload(db))
            if m := re.fullmatch(r"/api/invoice/(\d+)", path):
                got = invoice_payload(db, int(m.group(1)))
                return self._send(200, got) if got else self._send(404, {"error": "not found"})
            if path == "/export/bank.csv":
                return self._send(200, bank_file(db, CLIENT), "text/csv; charset=utf-8", "chukta-bank-file.csv")
            if path == "/export/tally.csv":
                return self._send(200, tally_vouchers(db, CLIENT), "text/csv; charset=utf-8", "chukta-tally-vouchers.csv")
            if path == "/export/audit.json":
                return self._send(200, audit_file(db, CLIENT), "application/json", "chukta-audit.json")
            return self._send(404, {"error": "not found"})
        finally:
            db.close()

    def do_POST(self):
        # A custom header cannot be sent cross-site without a preflight, which this server never approves.
        if not self._host_ok() or self.headers.get("x-chukta") != "1":
            return self._send(403, {"error": "forbidden"})
        try:
            size = int(self.headers.get("content-length", 0))
            if size > MAX_BODY:
                return self._send(413, {"error": "too large"})
            body = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("expected an object")
        except ValueError:
            return self._send(400, {"error": "bad request"})
        db = connect(DB)
        try:
            return self._send(200, self._route(db, body))
        except ValueError as e:
            return self._send(400, {"error": str(e)})
        finally:
            db.close()

    def _route(self, db, body):
        path = self.path
        by = str(body.get("by") or "").strip()[:80]
        if path == "/api/run":
            texts = [t for _, t, _, _ in BATCH] if body.get("sample") else [t.strip() for t in str(body.get("text", "")).split("\n---\n") if t.strip()]
            if not texts or len(texts) > 100 or any(len(t) > 30000 for t in texts):
                raise ValueError("Add between 1 and 100 invoices, separated by a line with ---")
            if not start_job("Running the request", run_batch, texts):
                raise ValueError("Chukta is already working")
            return {"ok": True}
        if not by:
            raise ValueError("Enter the reviewer's name first")
        if JOB["running"]:
            raise ValueError("Chukta is working. Try again when it finishes.")
        if path == "/api/signoff":
            ids = [r[0] for r in db.execute("SELECT id FROM invoices WHERE client_id=? AND state='READY'", (CLIENT,))]
            for i in ids:
                approve(db, i, by)
            return {"signed": len(ids)}
        if path == "/api/pay":
            if not db.execute("SELECT 1 FROM invoices WHERE state='APPROVED'").fetchone():
                raise ValueError("Nothing is signed and waiting for payment")
            open_run = db.execute("SELECT id FROM pay_runs WHERE finished_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
            if open_run:
                row = open_run[0]
            else:
                with db:
                    row = db.execute("INSERT INTO pay_runs(started_by, started_at) VALUES(?,?)", (by, now())).lastrowid
            start_job("Paying", run_pay, row)
            return {"ok": True}
        invoice_id = int(body.get("id", 0))
        if not db.execute("SELECT 1 FROM invoices WHERE id=? AND client_id=?", (invoice_id, CLIENT)).fetchone():
            raise ValueError("Unknown invoice")
        note = str(body.get("note") or "").strip()[:500]
        src = Sources(db, f"review-{int(time.time())}", credit_limit=2.0)
        if path == "/api/approve":
            raw = body.get("tds_rupees")
            override = None
            if raw not in (None, ""):
                try:
                    override = round(float(raw) * 100)
                except (TypeError, ValueError, OverflowError) as e:
                    raise ValueError("Enter TDS as a rupee amount") from e
            approve(db, invoice_id, by, note, tds_override_paise=override, retain_gst=bool(body.get("retain_gst")))
        elif path == "/api/reject":
            reject(db, invoice_id, by, note)
        elif path == "/api/recheck":
            recheck(db, src, invoice_id, by)
            if db.execute("SELECT state FROM invoices WHERE id=?", (invoice_id,)).fetchone()[0] in ("HELD", "BLOCKED"):
                investigate(db, invoice_id, src.run_id)
        elif path == "/api/alias":
            add_alias(db, src, invoice_id, by)
            if db.execute("SELECT state FROM invoices WHERE id=?", (invoice_id,)).fetchone()[0] in ("HELD", "BLOCKED"):
                investigate(db, invoice_id, src.run_id)
        else:
            raise ValueError("Unknown action")
        return {"ok": True}


if __name__ == "__main__":
    if "--reset" in sys.argv:
        for suffix in ("", "-wal", "-shm", ".paylock"):
            pathlib.Path(DB + suffix).unlink(missing_ok=True)
    resumed = resume()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Chukta is running on http://127.0.0.1:{PORT}" + (" and resuming interrupted work" if resumed else ""), flush=True)
    server.serve_forever()
