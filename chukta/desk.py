"""The payables desk: parse, check, decide, approve, pay exactly once.

Decisions are fixed policy over evidence. No model output can move money.
"""
import difflib
import hashlib
import json
import re
import sqlite3
import time
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .sources import SourceDown

SCHEMA = """
CREATE TABLE IF NOT EXISTS vendors(gstin TEXT PRIMARY KEY, name TEXT NOT NULL, domain TEXT NOT NULL,
    account TEXT NOT NULL, ifsc TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pos(po TEXT PRIMARY KEY, gstin TEXT NOT NULL, amount_paise INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, raw TEXT NOT NULL, raw_hash TEXT NOT NULL UNIQUE,
    fields TEXT NOT NULL, gstin TEXT, po TEXT, amount_paise INTEGER, invoice_date TEXT, fingerprint TEXT,
    state TEXT NOT NULL DEFAULT 'NEW', payment_ref TEXT);
CREATE TABLE IF NOT EXISTS findings(invoice_id INTEGER NOT NULL, check_name TEXT NOT NULL, status TEXT NOT NULL,
    severity TEXT NOT NULL, detail TEXT NOT NULL, source TEXT NOT NULL, retrieved_at TEXT NOT NULL,
    PRIMARY KEY(invoice_id, check_name));
CREATE TABLE IF NOT EXISTS approvals(invoice_id INTEGER NOT NULL, approved_by TEXT NOT NULL, note TEXT, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, source TEXT NOT NULL,
    request TEXT NOT NULL, credits REAL NOT NULL, outcome TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS source_cache(key TEXT PRIMARY KEY, body TEXT NOT NULL, retrieved_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sandbox_payments(idempotency_key TEXT PRIMARY KEY, ref TEXT NOT NULL, account TEXT NOT NULL,
    ifsc TEXT NOT NULL, amount_paise INTEGER NOT NULL, at TEXT NOT NULL);
"""
REQUIRED = ("invoice_no", "invoice_date", "po", "amount_paise", "gstin", "account", "ifsc")
# A person cannot approve past these: the invoice cannot be paid safely even with a note.
HARD_STOPS = ("required", "vendor", "duplicate")
GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
NAME_NOISE = {"limited", "ltd", "private", "pvt", "llp", "inc", "india", "corporation", "corp", "co", "company"}


def connect(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def today():
    return time.strftime("%Y-%m-%d")


def gstin_check(body):
    total = 0
    for i, c in enumerate(body):
        v = GST_CHARS.index(c) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return GST_CHARS[(36 - total % 36) % 36]


def gstin_valid(g):
    if not re.fullmatch(r"\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]", g or ""):
        return False
    state = int(g[:2])
    return (1 <= state <= 38 or state in (97, 99)) and gstin_check(g[:14]) == g[14]


def _paise(text):
    try:
        return int((Decimal(text.replace(",", "")) * 100).to_integral_exact())
    except (InvalidOperation, ValueError):
        return None


def _date(text):
    text = re.sub(r"[,\s]+", " ", text.strip())
    for fmt in ("%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _amount(text):
    number = r"(\d[\d,]*(?:\.\d{1,2})?)"
    for label in (r"grand\s+total", r"(?:total|net|amount)\s+payable", r"invoice\s+(?:total|amount)",
                  r"total\s+amount", r"total"):
        for pattern in (rf"(?<!sub )(?<!sub-)\b{label}\b[^\n]*?(?:₹|\brs\.?|\binr\b|:)\s*(?:₹|rs\.?|inr)?\s*{number}",
                        rf"(?<!sub )(?<!sub-)\b{label}\s+{number}"):
            m = re.search(pattern, text, re.I)
            if m:
                return _paise(m.group(1))
    return None


def _seller_gstin(text):
    found, buyer_block = [], False
    for line in text.splitlines():
        if not line.strip():
            buyer_block = False
        elif re.match(r"\s*(bill(ed)?\s*to|ship(ped)?\s*to|buyer|customer)\b", line, re.I):
            buyer_block = True
        if not buyer_block:
            found += re.findall(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b", line.upper())
    # Two different seller GSTINs is ambiguous, so it counts as missing rather than a guess.
    return found[0] if len(set(found)) == 1 else None


def parse(text):
    def first(pattern):
        m = re.search(pattern, text, re.I | re.M)
        return m.group(1).strip() if m else None

    invoice_no = first(r"\binv(?:oice)?\.?\s*(?:no|number|num|#)\.?\s*[:#-]?\s*"
                       r"([A-Z]{1,10}[ /_-]?\d[A-Z0-9/_-]*|\d[A-Z0-9/_-]*)")
    raw_date = first(r"\b(?:invoice\s+date|inv\.?\s*date|dated?)\b\s*[:-]?\s*"
                     r"(\d{1,2}[ /.-][A-Za-z]{3,9}[ /.,-]*\d{4}|\d{1,2}[/.-]\d{1,2}[/.-]\d{4}|\d{4}-\d{2}-\d{2})")
    po = first(r"\b(?:p\.?o\.?|purchase\s+order)\s*(?:no|number|#|ref)?\.?\s*[:#-]?\s*(?:PO[ /_-]?)?(\d+)\b")
    account = first(r"\b(?:a/?c|acct|account)\b(?:\s*(?:no|number|#))?\.?\s*[:-]?\s*(\d[\d -]{7,20}\d)")
    ifsc = first(r"\bifsc\b(?:\s*code)?\s*[:-]?\s*([A-Z]{4}0[A-Z0-9]{6})\b")
    senders = re.findall(r"^\s*(?:from|sender|reply-to)\s*:.*?[\w.+-]+@([\w-]+(?:\.[\w-]+)+)", text, re.I | re.M)
    return {
        "invoice_no": invoice_no,
        "invoice_date": _date(raw_date) if raw_date else None,
        "po": f"PO-{int(po)}" if po else None,
        "amount_paise": _amount(text),
        "gstin": _seller_gstin(text),
        "account": re.sub(r"\D", "", account) if account else None,
        "ifsc": ifsc.upper() if ifsc else None,
        "sender_domains": sorted({s.lower() for s in senders}),
    }


def fingerprint(gstin, invoice_no):
    """INV-0042, inv 42 and INV/42 from one vendor are the same invoice."""
    if not gstin or not invoice_no:
        return None
    parts = [str(int(p)) if p.isdigit() else p for p in re.findall(r"[A-Z]+|\d+", invoice_no.upper())]
    return hashlib.sha256(f"{gstin}|{'|'.join(parts)}".encode()).hexdigest()


def ingest(db, raw):
    """Safe to repeat after a crash: the same text is one invoice."""
    digest = hashlib.sha256(" ".join(raw.split()).encode()).hexdigest()
    f = parse(raw)
    with db:
        db.execute("INSERT OR IGNORE INTO invoices(raw, raw_hash, fields, gstin, po, amount_paise, invoice_date, "
                   "fingerprint) VALUES(?,?,?,?,?,?,?,?)",
                   (raw, digest, json.dumps(f), f["gstin"], f["po"], f["amount_paise"], f["invoice_date"],
                    fingerprint(f["gstin"], f["invoice_no"])))
    return db.execute("SELECT id FROM invoices WHERE raw_hash=?", (digest,)).fetchone()[0]


def same_company(a, b):
    def tokens(name):
        name = re.sub(r"\(.*?\)", " ", name.lower())
        return set(re.findall(r"[a-z0-9]+", name)) - NAME_NOISE
    x, y = tokens(a), tokens(b)
    return bool(x and y) and (x <= y or y <= x)


def _lookalike(domain, real):
    brand = real.split(".")[0]
    return (not domain.isascii() or domain.startswith("xn--") or brand in domain
            or difflib.SequenceMatcher(None, domain, real).ratio() >= 0.75)


def _mask(account):
    return f"****{account[-4:]}" if account else "none"


def run_checks(db, src, inv):
    f = json.loads(inv["fields"])
    out = []

    def add(check, status, detail, source, at=None, block=False):
        severity = "block" if block else ("hold" if status != "pass" else "none")
        out.append((inv["id"], check, status, severity, detail, source, at or today()))

    missing = [k for k in REQUIRED if not f.get(k)]
    if missing:
        add("required", "unverified", f"I can't verify this invoice: missing or ambiguous {', '.join(missing)}.",
            "invoice text")
    else:
        add("required", "pass", "All required fields are present.", "invoice text")

    if f["gstin"]:
        ok = gstin_valid(f["gstin"])
        add("gstin", "pass" if ok else "fail",
            f"GSTIN {f['gstin']} {'passes' if ok else 'fails'} the checksum.", "GSTIN checksum algorithm", block=not ok)

    vendor = db.execute("SELECT * FROM vendors WHERE gstin=?", (f["gstin"],)).fetchone() if f["gstin"] else None
    if vendor:
        add("vendor", "pass", f"GSTIN belongs to {vendor['name']} on the vendor master.", "vendors.gstin")
    else:
        add("vendor", "unverified", "I can't verify this vendor: its GSTIN is not on the vendor master.", "vendors.gstin")

    if inv["fingerprint"]:
        dup = db.execute("SELECT id FROM invoices WHERE fingerprint=? AND id<? ORDER BY id LIMIT 1",
                         (inv["fingerprint"], inv["id"])).fetchone()
        if dup:
            add("duplicate", "fail", f"Same vendor and invoice number as invoice #{dup['id']}.", f"invoices.id={dup['id']}")
        else:
            add("duplicate", "pass", "No earlier invoice has this vendor and number.", "invoices.fingerprint")
    if inv["gstin"] and inv["amount_paise"] and inv["invoice_date"]:
        near = db.execute("SELECT id FROM invoices WHERE gstin=? AND amount_paise=? AND invoice_date=? AND id<? "
                          "AND fingerprint IS NOT ? LIMIT 1",
                          (inv["gstin"], inv["amount_paise"], inv["invoice_date"], inv["id"], inv["fingerprint"])).fetchone()
        if near:
            add("near_duplicate", "fail", f"Same vendor, amount and date as invoice #{near['id']}, different number.",
                f"invoices.id={near['id']}")

    if f["po"]:
        po = db.execute("SELECT * FROM pos WHERE po=?", (f["po"],)).fetchone()
        if not po:
            add("po", "fail", f"{f['po']} is not in the purchase order table.", "pos.po")
        elif po["gstin"] != f["gstin"]:
            add("po", "fail", f"{f['po']} was issued to a different vendor.", f"pos.po={f['po']}")
        elif inv["amount_paise"] is not None:
            used = db.execute("SELECT COALESCE(SUM(amount_paise), 0) FROM invoices WHERE po=? AND id<? AND state IN "
                              "('READY','APPROVED','PAID')", (f["po"], inv["id"])).fetchone()[0]
            left = po["amount_paise"] - used
            ok = inv["amount_paise"] <= left
            add("po", "pass" if ok else "fail",
                f"₹{inv['amount_paise'] / 100:,.2f} against ₹{left / 100:,.2f} left on {f['po']}.", f"pos.po={f['po']}")

    if vendor and f["account"] and f["ifsc"]:
        ok = f["account"] == vendor["account"] and f["ifsc"] == vendor["ifsc"]
        add("bank", "pass" if ok else "fail",
            f"Bank details match the master ({_mask(vendor['account'])})." if ok else
            f"Invoice pays {_mask(f['account'])} / {f['ifsc']}, master has {_mask(vendor['account'])} / "
            f"{vendor['ifsc']}. Confirm by calling a known number.", "vendors.account", block=not ok)

    if f["ifsc"]:
        try:
            got = src.ifsc(f["ifsc"])
            if got["record"]:
                add("ifsc", "pass", f"{f['ifsc']} is {got['record']['bank']}, {got['record']['branch']}.",
                    f"https://ifsc.razorpay.com/{f['ifsc']}", got["retrieved_at"])
            else:
                add("ifsc", "fail", f"{f['ifsc']} is not in the IFSC registry.",
                    f"https://ifsc.razorpay.com/{f['ifsc']}", got["retrieved_at"], block=True)
        except SourceDown as e:
            add("ifsc", "unverified", f"I can't verify the IFSC: {e}.", "ifsc.razorpay.com")

    if vendor:
        real = vendor["domain"]
        if not f["sender_domains"]:
            add("sender", "unverified", "I can't verify the sender: no email address on this invoice.", "invoice text")
        for domain in f["sender_domains"]:
            if domain == real or domain.endswith("." + real):
                continue
            if _lookalike(domain, real):
                add("sender", "fail", f"Sender domain {domain} imitates the vendor's {real}.", "invoice email header", block=True)
            else:
                add("sender", "fail", f"Sender domain {domain} is not the vendor's {real}.", "invoice email header")
            break
        else:
            if f["sender_domains"]:
                add("sender", "pass", f"Sender domain matches {real}.", "invoice email header")

        try:
            got = src.identify(real)
            m = got["match"]
            where = "crustdata:/company/identify"
            if not m:
                add("company", "unverified", f"I can't verify the company: Crustdata has no record for {real}.",
                    f"{where}?domain={real}", got["retrieved_at"])
            elif same_company(vendor["name"], m["name"]):
                add("company", "pass", f"{real} resolves to {m['name']}.",
                    f"{where}#{m['id']}.basic_info.name", got["retrieved_at"])
            else:
                add("company", "unverified", f"I can't verify the company: {real} resolves to {m['name']}, "
                    f"the master says {vendor['name']}.", f"{where}#{m['id']}.basic_info.name", got["retrieved_at"])
        except SourceDown as e:
            add("company", "unverified", f"I can't verify the company: {e}.", "crustdata:/company/identify")
    return out


def decide(findings):
    if any(row[3] == "block" for row in findings):
        return "BLOCKED"
    return "HELD" if any(row[2] != "pass" for row in findings) else "READY"


def process(db, src):
    """Check every NEW invoice. A crash leaves it NEW, and cached sources make the rerun free."""
    new = db.execute("SELECT * FROM invoices WHERE state='NEW' ORDER BY id").fetchall()
    gstins = {i["gstin"] for i in new if i["gstin"]}
    domains = [r["domain"] for g in gstins for r in db.execute("SELECT domain FROM vendors WHERE gstin=?", (g,))]
    if domains:
        try:
            src.identify_many(domains)
        except SourceDown:
            pass  # Each invoice retries through src.identify and holds if the source stays down.
    for inv in new:
        findings = run_checks(db, src, inv)
        with db:
            db.execute("DELETE FROM findings WHERE invoice_id=?", (inv["id"],))
            db.executemany("INSERT OR REPLACE INTO findings VALUES(?,?,?,?,?,?,?)", findings)
            db.execute("UPDATE invoices SET state=? WHERE id=? AND state='NEW'", (decide(findings), inv["id"]))


def approve(db, invoice_id, by, note=""):
    inv = db.execute("SELECT state FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    if not inv or inv["state"] not in ("READY", "HELD"):
        raise ValueError(f"invoice {invoice_id} cannot be approved from {inv and inv['state']}")
    marks = ",".join("?" * len(HARD_STOPS))
    stop = db.execute(f"SELECT check_name FROM findings WHERE invoice_id=? AND status!='pass' AND check_name IN ({marks})",
                      (invoice_id, *HARD_STOPS)).fetchone()
    if stop:
        raise ValueError(f"invoice {invoice_id} cannot be paid: {stop['check_name']} check")
    if inv["state"] == "HELD" and not note.strip():
        raise ValueError("approving a held invoice needs a note saying what the person checked")
    with db:
        db.execute("INSERT INTO approvals VALUES(?,?,?,?)", (invoice_id, by, note, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
        db.execute("UPDATE invoices SET state='APPROVED' WHERE id=?", (invoice_id,))


class SandboxBank:
    """Local stand-in for a provider's test mode. The idempotency key makes a repeat return the first payment."""

    def __init__(self, db):
        self.db = db

    def pay(self, key, account, ifsc, amount_paise):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO sandbox_payments VALUES(?,?,?,?,?,?)",
                            (key, f"sandbox_{uuid.uuid4().hex[:12]}", account, ifsc, amount_paise,
                             time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
        return self.db.execute("SELECT ref FROM sandbox_payments WHERE idempotency_key=?", (key,)).fetchone()[0]


def pay_approved(db, bank):
    """Pays the account on the vendor master, never one read from the invoice."""
    rows = db.execute("SELECT i.id, i.fingerprint, i.amount_paise, v.account, v.ifsc FROM invoices i "
                      "JOIN vendors v ON v.gstin=i.gstin WHERE i.state='APPROVED' ORDER BY i.id").fetchall()
    for r in rows:
        ref = bank.pay(f"chukta:{r['fingerprint']}", r["account"], r["ifsc"], r["amount_paise"])
        with db:
            db.execute("UPDATE invoices SET state='PAID', payment_ref=? WHERE id=? AND state='APPROVED'", (ref, r["id"]))
