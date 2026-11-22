"""Chukta reviewer app.

python3 app.py           start on http://127.0.0.1:8765 and resume any interrupted work
python3 app.py --reset   delete the local demo books first
"""
import json
import mimetypes
import os
import pathlib
import re
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from chukta.books import books_payload, import_2b, import_pos, import_vendors
from chukta.demo import BATCH, CLIENT, CLIENT_NAME, SAMPLE_REQUEST, SAMPLE_STATEMENT, seed
from chukta.drills import run_drills
from chukta.desk import (HARD_STOPS, SandboxBank, _paise, _rupees, add_alias, approve, approve_bank_change, compute_tds, evidence_hash, connect, ingest, now, parse, pay_approved, process,
                         propose_bank_change, recheck, reject)
from chukta.exports import audit_file, bank_file, replay_lines, tally_vouchers, verify_audit
from chukta.investigator import ModelDown, investigate, model_chat
from chukta.razorpay import RazorpayBank
from chukta.reader import logged_reader
from chukta.records import mask_text, record
from chukta.runs import apply_instructions, close_finished_runs, create_run, interrupted_runs, latest_run, model_spend, payment_allowed, set_stage
from chukta.sources import Sources
from chukta.statement import dismiss_line, import_statement, post_lines, resolve_line, statement_payload

ROOT = pathlib.Path(__file__).parent
STATIC = ROOT / "static"
DB = str(ROOT / "chukta.db")
PORT = int(os.environ.get("CHUKTA_PORT", 8765))
PAY_DELAY_S = float(os.environ.get("CHUKTA_PAY_DELAY", 0))  # Set to 3 to make a kill during payment easy to show.
MAX_BODY = 1_000_000
MODEL_WORKERS = 4
JOB = {"running": False, "name": "", "message": "", "error": ""}
JOB_LOCK = threading.Lock()
ORDER = {"BLOCKED": 0, "HELD": 1, "NEW": 2, "READY": 3, "APPROVED": 4, "PAID": 5, "REJECTED": 6}


def bank_for(db, run_id="payments", on_wait=None):
    try:
        return RazorpayBank(db, run_id=run_id, on_wait=on_wait)
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
            JOB.update(error=f"{e}", message="Stopped")
        finally:
            JOB["running"] = False
    threading.Thread(target=wrapped, daemon=True).start()
    return True


def _no_model(messages, use_tools):
    raise ModelDown()


def run_batch(run_id):
    """Each stage is safe to repeat, so a restart simply calls this again. Model calls overlap, decisions stay in order."""
    db = connect(DB)
    run = dict(db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone())
    deadline = time.monotonic() + run["time_limit_s"]
    within = lambda conn: time.monotonic() < deadline and model_spend(conn, run_id) < run["model_usd_limit"]

    def read_one(row):
        own = connect(DB)  # SQLite connections stay on one thread.
        try:
            if within(own):
                return logged_reader(own, run_id)(row["text"])
            return parse(row["text"]) | {"reader_notes": ["Run ceiling reached. Used the rule-based parser only."], "usage": None}
        finally:
            own.close()

    def look_into(invoice_id):
        own = connect(DB)
        try:
            investigate(own, invoice_id, run_id, model_chat if within(own) else _no_model)
        finally:
            own.close()

    pending = [dict(r) for r in db.execute("SELECT n, text FROM run_inputs WHERE run_id=? AND done=0 ORDER BY n", (run_id,))]
    total = db.execute("SELECT COUNT(*) FROM run_inputs WHERE run_id=?", (run_id,)).fetchone()[0]
    set_stage(db, run_id, "reading")
    with ThreadPoolExecutor(MODEL_WORKERS) as pool:  # map keeps input order, so duplicates and TDS totals resolve the same way.
        for done, (row, fields) in enumerate(zip(pending, pool.map(read_one, pending)), total - len(pending) + 1):
            JOB["message"] = f"Reading invoice {done} of {total}"
            ingest(db, CLIENT, row["text"], lambda _: fields)
            with db:
                db.execute("UPDATE run_inputs SET done=1 WHERE run_id=? AND n=?", (run_id, row["n"]))
    set_stage(db, run_id, "checking")
    apply_instructions(db, run)
    JOB["message"] = "Checking each invoice against independent records"
    process(db, Sources(db, run_id, credit_limit=run["credit_limit"], time_limit_s=run["time_limit_s"]))
    set_stage(db, run_id, "investigating")
    todo = [r[0] for r in db.execute("SELECT id FROM invoices i WHERE state IN ('HELD','BLOCKED') AND NOT EXISTS "
                                     "(SELECT 1 FROM investigations n WHERE n.invoice_id=i.id)")]
    with ThreadPoolExecutor(MODEL_WORKERS) as pool:
        for n, _ in enumerate(pool.map(look_into, todo), 1):
            JOB["message"] = f"Looking into exception {n} of {len(todo)}"
    set_stage(db, run_id, "review")
    close_finished_runs(db)
    db.close()


def run_pay(pay_row):
    db = connect(DB)
    current = latest_run(db)
    if current:
        set_stage(db, current["id"], "paying")
    JOB["message"] = "Releasing signed payments"
    waiting = lambda seconds: JOB.update(message=f"Razorpay asked us to slow down. Trying again in {seconds} seconds")
    pay_approved(db, SlowBank(bank_for(db, current["id"] if current else "payments", waiting)))
    left = db.execute("SELECT COUNT(*) FROM invoices WHERE state='APPROVED'").fetchone()[0]
    if not left:
        with db:
            db.execute("UPDATE pay_runs SET finished_at=? WHERE finished_at IS NULL", (now(),))
    if current:
        set_stage(db, current["id"], "review")
    close_finished_runs(db)
    db.close()
    if left:  # The run stays open, so a restart or another release finishes it.
        raise RuntimeError(f"{left} signed payments did not go through and are safe to retry")


def run_statement(text):
    db = connect(DB)
    JOB["message"] = "Reading statement lines"
    import_statement(db, CLIENT, text)
    JOB["message"] = "Matching payees"
    post_lines(db, Sources(db, f"statement-{int(time.time())}", credit_limit=5.0, time_limit_s=300), CLIENT)
    db.close()


def resume():
    """After a crash: finish interrupted runs, then any payment run a person already released."""
    db = connect(DB)
    if not db.execute("SELECT 1 FROM clients WHERE id=?", (CLIENT,)).fetchone():
        seed(db)  # Seeded once, so a person's vendor corrections survive a restart.
    runs = interrupted_runs(db)
    open_pay = db.execute("SELECT id FROM pay_runs WHERE finished_at IS NULL ORDER BY id DESC LIMIT 1").fetchone()
    unposted = db.execute("SELECT COUNT(*) FROM bank_lines WHERE status='NEW'").fetchone()[0]
    db.close()

    def work():
        for run_id in runs:
            run_batch(run_id)
        if open_pay:
            run_pay(open_pay[0])
        if unposted:
            run_statement("")
    if runs or open_pay or unposted:
        start_job("Resuming after restart", work)
        return True
    return False


def run_block(db):
    r = latest_run(db)
    if not r:
        return None
    total, done = db.execute("SELECT COUNT(*), COALESCE(SUM(done), 0) FROM run_inputs WHERE run_id=?", (r["id"],)).fetchone()
    credits, usd, calls = db.execute("SELECT COALESCE(SUM(credits),0), COALESCE(SUM(usd),0), COUNT(*) FROM ledger WHERE run_id=?", (r["id"],)).fetchone()
    return {"id": r["id"], "request": r["request"], "understood": json.loads(r["understood"]), "stage": r["stage"], "started_at": r["started_at"],
            "finished_at": r["finished_at"], "inputs_total": total, "inputs_done": done, "credits": round(credits, 2), "usd": round(usd, 4), "calls": calls,
            "credit_limit": r["credit_limit"], "model_usd_limit": r["model_usd_limit"], "time_limit_s": r["time_limit_s"]}


def state_payload(db):
    rows = db.execute("SELECT i.*, v.name vendor_name, o.net_paise order_net, o.tds_paise order_tds, o.retained_gst_paise order_retained, n.action_text FROM invoices i "
                      "LEFT JOIN vendors v ON v.client_id=i.client_id AND v.gstin=i.gstin LEFT JOIN payment_orders o ON o.invoice_id=i.id "
                      "LEFT JOIN investigations n ON n.invoice_id=i.id WHERE i.client_id=?", (CLIENT,)).fetchall()
    out, run_lines = [], []
    totals = {"gross": 0, "tds": 0, "retained": 0, "net": 0}
    for r in rows:
        f = json.loads(r["fields"])
        net, tds = r["order_net"], r["order_tds"]
        if net is None and r["amount_paise"] and r["vendor_name"] and r["state"] in ("READY", "HELD", "BLOCKED"):
            vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (r["client_id"], r["gstin"])).fetchone()
            tds = compute_tds(db, vendor, r)[0]
            net = r["amount_paise"] - tds if tds is not None else None
        if r["state"] in ("READY", "APPROVED") and net:
            run_lines.append({"id": r["id"], "evidence": evidence_hash(db, r["id"]), "vendor": r["vendor_name"], "number": f.get("invoice_no"), "net": _rupees(net), "tds": _rupees(tds or 0),
                              "due": r["due_date"], "state": r["state"]})
            totals["gross"] += r["amount_paise"]
            totals["tds"] += tds or 0
            totals["retained"] += r["order_retained"] or 0
            totals["net"] += net
        reason = db.execute("SELECT detail, check_name FROM findings WHERE invoice_id=? AND status NOT IN ('pass','info') "
                            "ORDER BY severity='block' DESC LIMIT 1", (r["id"],)).fetchone()
        out.append({"id": r["id"], "number": f.get("invoice_no") or "No number", "vendor": r["vendor_name"] or "Unknown vendor", "date": r["invoice_date"],
                    "state": r["state"], "gross": _rupees(r["amount_paise"]) if r["amount_paise"] else "Unclear", "net": _rupees(net) if net else "",
                    "due": r["due_date"], "reason": reason[0] if reason else "", "check": reason[1] if reason else "", "action": r["action_text"] or ""})
    out.sort(key=lambda x: (ORDER.get(x["state"], 9), x["due"] or "9999", x["id"]))
    run_lines.sort(key=lambda x: (x["due"] or "9999", x["id"]))
    counts = {s: sum(1 for x in out if x["state"] == s) for s in ORDER}
    credits, usd, calls = db.execute("SELECT COALESCE(SUM(credits),0), COALESCE(SUM(usd),0), COUNT(*) FROM ledger").fetchone()
    issued = db.execute("SELECT COALESCE(SUM(net_paise),0) FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id WHERE i.state='PAID'").fetchone()[0]
    return {"client": CLIENT_NAME, "provider": "Razorpay test mode" if isinstance(bank_for(db), RazorpayBank) else "Local sandbox",
            "sample_request": SAMPLE_REQUEST, "sample_count": len(BATCH), "invoices": out, "counts": counts, "issued": _rupees(issued),
            "payment_run": {"lines": run_lines, "gross": _rupees(totals["gross"]), "tds": _rupees(totals["tds"]), "retained": _rupees(totals["retained"]), "net": _rupees(totals["net"])},
            "job": dict(JOB), "run": run_block(db), "cost": {"credits": round(credits, 2), "usd": round(usd, 4), "calls": calls},
            "audit_problems": verify_audit(db, CLIENT), "open_pay_run": bool(db.execute("SELECT 1 FROM pay_runs WHERE finished_at IS NULL").fetchone())}


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
    change = db.execute("SELECT id, proposed_by, callback_note, new_account FROM vendor_changes WHERE client_id=? AND gstin=? AND status='PENDING' ORDER BY id DESC LIMIT 1", (r["client_id"], r["gstin"])).fetchone()
    sender_blocked = any(x["check_name"] == "sender" and x["severity"] == "block" for x in findings)
    net = order["net_paise"] if order else (r["amount_paise"] - tds if r["amount_paise"] and tds is not None else None)
    return {"id": r["id"], "state": r["state"], "number": fields.get("invoice_no"), "date": r["invoice_date"], "po": r["po"],
            "vendor": vendor["name"] if vendor else "Unknown vendor", "gstin": r["gstin"], "net": _rupees(net) if net else "Unclear",
            "gross": _rupees(r["amount_paise"]) if r["amount_paise"] else "Unclear", "taxable": _rupees(r["taxable_paise"]) if r["taxable_paise"] else "Unclear",
            "tax": _rupees(r["tax_paise"]) if r["tax_paise"] else "Unclear", "tds": _rupees(tds) if tds is not None else "Needs a person",
            "due": r["due_date"], "findings": findings, "reader_notes": [mask_text(n) for n in fields.get("reader_notes", [])],
            "events": [dict(x) for x in db.execute("SELECT event, actor, detail, at FROM events WHERE invoice_id=? ORDER BY id", (invoice_id,))],
            "investigation": {**dict(note), "citations": json.loads(note["citations"])} if note else None,
            "order": {k: _rupees(order[k]) for k in ("gross_paise", "tds_paise", "retained_gst_paise", "net_paise")} | {"by": order["approved_by"]} if order else None,
            "payment_ref": r["payment_ref"], "raw": mask_text(r["raw"]), "evidence": evidence_hash(db, r["id"]),
            "can_approve": r["state"] in ("READY", "HELD") and not (failing & set(HARD_STOPS)), "needs_tds": tds is None and bool(vendor),
            "can_retain_gst": "gst" in failing and bool(r["tax_paise"]),
            "can_alias": bool(company and company["status"] == "unverified" and "resolves to" in company["detail"]),
            "can_propose_bank": r["state"] == "BLOCKED" and "bank" in failing and not sender_blocked and not change,
            "bank_change": {"id": change["id"], "by": change["proposed_by"], "note": change["callback_note"], "account": "****" + change["new_account"][-4:]} if change else None}


def ledger_payload(db):
    by_source = [dict(r) for r in db.execute("SELECT source, COUNT(*) calls, ROUND(SUM(credits),3) credits, ROUND(SUM(usd),5) usd FROM ledger GROUP BY source ORDER BY calls DESC")]
    calls = [dict(r) for r in db.execute("SELECT id, run_id, source, request, credits, usd, outcome, at FROM ledger ORDER BY id DESC LIMIT 150")]
    invoices = db.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    credits, usd, total = db.execute("SELECT COALESCE(SUM(credits),0), COALESCE(SUM(usd),0), COUNT(*) FROM ledger").fetchone()
    return {"by_source": by_source, "calls": calls, "total_calls": total, "credits": round(credits, 2), "usd": round(usd, 4), "invoices": invoices,
            "per_invoice_credits": round(credits / invoices, 3) if invoices else 0, "per_invoice_usd": round(usd / invoices, 5) if invoices else 0, "run": run_block(db)}


def font_css():
    font = STATIC / "GoogleSansFlex.woff2"
    if not font.exists():
        return b""
    return (b'@font-face{font-family:"Google Sans Flex";src:url(/static/GoogleSansFlex.woff2) format("woff2");font-weight:300 800;font-stretch:87% 112%;font-display:swap}'
            b'@font-face{font-family:"Google Sans Flex";src:url(/static/GoogleSansFlex-Rupee.woff2) format("woff2");font-weight:300 800;font-stretch:87% 112%;font-display:swap;unicode-range:U+20B9}'
            b'@font-face{font-family:"Material Symbols";src:url(/static/MaterialSymbols.woff2) format("woff2");font-weight:300 600;font-display:block}')


class Handler(BaseHTTPRequestHandler):
    server_version = "Chukta"
    sys_version = ""

    def log_message(self, *args):
        pass

    def _send(self, code, body, kind="application/json", name=None, cache=False):
        data = body if isinstance(body, bytes) else (body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode())
        self.send_response(code)
        self.send_header("content-type", kind)
        self.send_header("content-length", str(len(data)))
        self.send_header("x-content-type-options", "nosniff")
        self.send_header("referrer-policy", "no-referrer")
        self.send_header("cache-control", "max-age=60" if cache else "no-store")
        self.send_header("content-security-policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; "
                                                    "font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        if name:
            self.send_header("content-disposition", f'attachment; filename="{name}"')
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        return self.headers.get("host") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        parsed = urllib.parse.urlsplit(self.path)
        path = parsed.path
        if path == "/":
            return self._send(200, (ROOT / "ui.html").read_bytes(), "text/html; charset=utf-8")
        if path == "/favicon.ico":
            return self._send(204, b"")
        if path == "/static/font.css":
            return self._send(200, font_css(), "text/css; charset=utf-8")
        if m := re.fullmatch(r"/static/([A-Za-z0-9_-]+\.(?:css|js|woff2|svg))", path):
            file = STATIC / m.group(1)
            if not file.is_file():
                return self._send(404, {"error": "not found"})
            kind = {"css": "text/css; charset=utf-8", "js": "text/javascript; charset=utf-8", "woff2": "font/woff2", "svg": "image/svg+xml"}.get(file.suffix[1:]) or mimetypes.guess_type(file.name)[0]
            return self._send(200, file.read_bytes(), kind, cache=file.suffix == ".woff2")
        db = connect(DB)
        try:
            if path == "/api/state":
                return self._send(200, state_payload(db))
            if m := re.fullmatch(r"/api/invoice/(\d+)", path):
                got = invoice_payload(db, int(m.group(1)))
                return self._send(200, got) if got else self._send(404, {"error": "not found"})
            if path == "/api/record":
                q = urllib.parse.parse_qs(parsed.query)
                try:
                    got = record(db, int(q.get("invoice", ["0"])[0]), q.get("check", [""])[0])
                except ValueError:
                    got = None
                return self._send(200, got) if got else self._send(404, {"error": "not found"})
            if path == "/api/ledger":
                return self._send(200, ledger_payload(db))
            if path == "/api/statement":
                return self._send(200, statement_payload(db, CLIENT) | {"sample": SAMPLE_STATEMENT})
            if path == "/api/books":
                return self._send(200, books_payload(db, CLIENT))
            if path == "/api/replay":
                return self._send(200, replay_lines(db, CLIENT))
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
            if not 0 <= size <= MAX_BODY:
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
        if path == "/api/drills":
            return run_drills()
        if path == "/api/run":
            if JOB["running"]:
                raise ValueError("Chukta is already working")
            texts = [t for _, t, _, _ in BATCH] if body.get("sample") else [t.strip() for t in str(body.get("text", "")).split("\n---\n") if t.strip()]
            if len(texts) > 100 or any(len(t) > 30000 for t in texts):
                raise ValueError("Add up to 100 invoices, separated by a line with ---")
            run_id = create_run(db, CLIENT, str(body.get("request") or "")[:2000], texts)
            start_job("Running the request", run_batch, run_id)
            return {"ok": True, "run": run_id}
        if path == "/api/statement":
            text = SAMPLE_STATEMENT if body.get("sample") else str(body.get("text", ""))[:60000]
            if not text.strip():
                raise ValueError("Paste at least one statement line")
            if not start_job("Posting the statement", run_statement, text):
                raise ValueError("Chukta is already working")
            return {"ok": True}
        if path in ("/api/books/vendors", "/api/books/pos", "/api/books/gstr2b"):
            if JOB["running"]:
                raise ValueError("Chukta is working. Try again when it finishes.")
            text = str(body.get("text") or "")[:400000]
            result = {"vendors": import_vendors, "pos": import_pos, "gstr2b": import_2b}[path.rsplit("/", 1)[1]](db, CLIENT, text)
            return {"ok": True, "result": result}
        by = str(body.get("by") or "").strip()[:80]
        if not by:
            raise ValueError("Enter the reviewer's name first")
        if JOB["running"]:
            raise ValueError("Chukta is working. Try again when it finishes.")
        note = str(body.get("note") or "").strip()[:500]
        if path in ("/api/line/resolve", "/api/line/dismiss"):
            line_id = int(body.get("id", 0))
            if path.endswith("resolve"):
                resolve_line(db, line_id, by, str(body.get("payee") or ""), str(body.get("account") or ""), note)
            else:
                dismiss_line(db, line_id, by, note)
            return {"ok": True}
        if path in ("/api/signoff", "/api/pay") and not payment_allowed(db):
            raise ValueError("This run was checks only. Start a new run to pay.")
        if path == "/api/signoff":
            items = body.get("items")  # Only what the reviewer saw, with the evidence they saw.
            if not isinstance(items, list) or not items:
                raise ValueError("Nothing was selected to sign")
            for item in items:
                approve(db, int(item["id"]), by, expected_evidence=str(item["evidence"]))
            return {"signed": len(items)}
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
        if path == "/api/bank-change/approve":
            current = latest_run(db)
            src = Sources(db, current["id"] if current else f"review-{int(time.time())}", credit_limit=(current["credit_limit"] if current else 2.0))
            for i in approve_bank_change(db, src, int(body.get("change", 0)), by):
                if db.execute("SELECT state FROM invoices WHERE id=?", (i,)).fetchone()[0] in ("HELD", "BLOCKED"):
                    investigate(db, i, src.run_id)
            close_finished_runs(db)
            return {"ok": True}
        invoice_id = int(body.get("id", 0))
        if not db.execute("SELECT 1 FROM invoices WHERE id=? AND client_id=?", (invoice_id, CLIENT)).fetchone():
            raise ValueError("Unknown invoice")
        current = latest_run(db)
        src = Sources(db, current["id"] if current else f"review-{int(time.time())}", credit_limit=(current["credit_limit"] if current else 2.0))
        if path == "/api/approve":
            raw = body.get("tds_rupees")
            override = None
            if raw not in (None, ""):
                override = _paise(str(raw).replace("₹", "").strip())
                if override is None:
                    raise ValueError("Enter TDS as a rupee amount")
            evidence = str(body.get("evidence") or "")  # The approval covers only the evidence the reviewer saw.
            if not evidence:
                raise ValueError("Open the invoice again before approving")
            approve(db, invoice_id, by, note, tds_override_paise=override, retain_gst=bool(body.get("retain_gst")), expected_evidence=evidence)
        elif path == "/api/reject":
            reject(db, invoice_id, by, note)
        elif path == "/api/recheck":
            recheck(db, src, invoice_id, by)
            if db.execute("SELECT state FROM invoices WHERE id=?", (invoice_id,)).fetchone()[0] in ("HELD", "BLOCKED"):
                investigate(db, invoice_id, src.run_id)
        elif path == "/api/bank-change/propose":
            propose_bank_change(db, invoice_id, by, note)
        elif path == "/api/alias":
            add_alias(db, src, invoice_id, by)
            if db.execute("SELECT state FROM invoices WHERE id=?", (invoice_id,)).fetchone()[0] in ("HELD", "BLOCKED"):
                investigate(db, invoice_id, src.run_id)
        else:
            raise ValueError("Unknown action")
        close_finished_runs(db)
        return {"ok": True}


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)  # Bound first, so a second copy exits before touching the books.
    if "--reset" in sys.argv:
        for suffix in ("", "-wal", "-shm", ".paylock"):
            pathlib.Path(DB + suffix).unlink(missing_ok=True)
    (ROOT / "chukta.pid").write_text(str(os.getpid()))  # Lets a demo kill exactly this process.
    resumed = resume()
    print(f"Chukta is running on http://127.0.0.1:{PORT}" + (" and resuming interrupted work" if resumed else ""), flush=True)
    server.serve_forever()
