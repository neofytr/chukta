"""The payables desk: parse, check, decide, approve, pay exactly once.

Decisions are fixed policy over evidence. No model output can move money.
State: NEW -> READY | HELD | BLOCKED -> APPROVED -> PAID, or -> REJECTED.
"""
import contextlib
try:
    import fcntl
except ImportError:  # Windows.
    fcntl = None
    import msvcrt
import hashlib
import json
import re
import sqlite3
import time
import unicodedata
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from .sources import SourceDown

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vendors(client_id TEXT NOT NULL, gstin TEXT NOT NULL, name TEXT NOT NULL, domain TEXT NOT NULL,
    account TEXT NOT NULL, ifsc TEXT NOT NULL, emails TEXT NOT NULL DEFAULT '[]', aliases TEXT NOT NULL DEFAULT '[]',
    onboarded_at TEXT, msme TEXT, agreement_days INTEGER, tds_class TEXT, payee_type TEXT NOT NULL DEFAULT 'other',
    gst_filing TEXT NOT NULL DEFAULT 'monthly', opening_fy TEXT, opening_taxable_paise INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(client_id, gstin));
CREATE TABLE IF NOT EXISTS pos(client_id TEXT NOT NULL, po TEXT NOT NULL, gstin TEXT NOT NULL, amount_paise INTEGER NOT NULL,
    PRIMARY KEY(client_id, po));
CREATE TABLE IF NOT EXISTS invoices(id INTEGER PRIMARY KEY, client_id TEXT NOT NULL, raw TEXT NOT NULL, raw_hash TEXT NOT NULL,
    fields TEXT NOT NULL, gstin TEXT, po TEXT, amount_paise INTEGER, taxable_paise INTEGER, tax_paise INTEGER, due_date TEXT,
    invoice_date TEXT, fy TEXT, number_core INTEGER, fingerprint TEXT, state TEXT NOT NULL DEFAULT 'NEW', payment_ref TEXT, UNIQUE(client_id, raw_hash));
CREATE TABLE IF NOT EXISTS findings(invoice_id INTEGER NOT NULL, check_name TEXT NOT NULL, status TEXT NOT NULL,
    severity TEXT NOT NULL, detail TEXT NOT NULL, source TEXT NOT NULL, retrieved_at TEXT NOT NULL,
    PRIMARY KEY(invoice_id, check_name));
CREATE TABLE IF NOT EXISTS payment_orders(invoice_id INTEGER PRIMARY KEY, client_id TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE,
    payee_gstin TEXT NOT NULL, payee_name TEXT NOT NULL, account TEXT NOT NULL, ifsc TEXT NOT NULL, gross_paise INTEGER NOT NULL,
    tds_paise INTEGER NOT NULL, retained_gst_paise INTEGER NOT NULL, net_paise INTEGER NOT NULL, evidence_hash TEXT NOT NULL, approved_by TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, invoice_id INTEGER NOT NULL, event TEXT NOT NULL, actor TEXT NOT NULL,
    detail TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, source TEXT NOT NULL, request TEXT NOT NULL,
    credits REAL NOT NULL, outcome TEXT NOT NULL, at TEXT NOT NULL, usd REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS source_cache(key TEXT PRIMARY KEY, body TEXT NOT NULL, retrieved_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS provider_payments(idempotency_key TEXT PRIMARY KEY, provider TEXT NOT NULL, ref TEXT NOT NULL,
    account TEXT NOT NULL, ifsc TEXT NOT NULL, amount_paise INTEGER NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS gstr2b(client_id TEXT NOT NULL, period TEXT NOT NULL, gstin TEXT NOT NULL, number_key TEXT NOT NULL,
    invoice_date TEXT NOT NULL, value_paise INTEGER NOT NULL, PRIMARY KEY(client_id, period, gstin, number_key));
CREATE TABLE IF NOT EXISTS gstr2b_imports(client_id TEXT NOT NULL, period TEXT NOT NULL, imported_at TEXT NOT NULL,
    PRIMARY KEY(client_id, period));
CREATE TABLE IF NOT EXISTS investigations(invoice_id INTEGER PRIMARY KEY, evidence_hash TEXT NOT NULL, explanation TEXT NOT NULL,
    action TEXT NOT NULL, action_text TEXT NOT NULL, citations TEXT NOT NULL, callback TEXT, author TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS pay_runs(id INTEGER PRIMARY KEY, started_by TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS radar_hits(client_id TEXT NOT NULL, domain TEXT NOT NULL, vendor TEXT NOT NULL, real TEXT NOT NULL, level TEXT NOT NULL, mail INTEGER NOT NULL, created TEXT, company TEXT, checked_at TEXT NOT NULL, PRIMARY KEY(client_id, domain));
CREATE TABLE IF NOT EXISTS receipts(invoice_id INTEGER PRIMARY KEY, client_id TEXT NOT NULL, code TEXT NOT NULL UNIQUE, intended TEXT, status TEXT NOT NULL, delivered_to TEXT, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS closes(client_id TEXT NOT NULL, period TEXT NOT NULL, signed_by TEXT NOT NULL, pack_hash TEXT NOT NULL, at TEXT NOT NULL, PRIMARY KEY(client_id, period));
CREATE TABLE IF NOT EXISTS vendor_changes(id INTEGER PRIMARY KEY, client_id TEXT NOT NULL, gstin TEXT NOT NULL, invoice_id INTEGER NOT NULL, old_account TEXT NOT NULL,
    old_ifsc TEXT NOT NULL, new_account TEXT NOT NULL, new_ifsc TEXT NOT NULL, proposed_by TEXT NOT NULL, callback_note TEXT NOT NULL, proposed_at TEXT NOT NULL,
    approved_by TEXT, approved_at TEXT, status TEXT NOT NULL DEFAULT 'PENDING');
CREATE TABLE IF NOT EXISTS payment_holds(client_id TEXT NOT NULL, gstin TEXT NOT NULL, reason TEXT NOT NULL, PRIMARY KEY(client_id, gstin));
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, client_id TEXT NOT NULL, request TEXT NOT NULL, understood TEXT NOT NULL, stage TEXT NOT NULL,
    started_at TEXT NOT NULL, finished_at TEXT, credit_limit REAL NOT NULL, time_limit_s INTEGER NOT NULL, model_usd_limit REAL NOT NULL);
CREATE TABLE IF NOT EXISTS run_inputs(run_id TEXT NOT NULL, n INTEGER NOT NULL, text TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(run_id, n));
CREATE TABLE IF NOT EXISTS payee_rules(client_id TEXT NOT NULL, keyword TEXT NOT NULL, legal_name TEXT NOT NULL, domain TEXT NOT NULL, account TEXT NOT NULL,
    PRIMARY KEY(client_id, keyword));
CREATE TABLE IF NOT EXISTS bank_lines(id INTEGER PRIMARY KEY, client_id TEXT NOT NULL, line_key TEXT NOT NULL UNIQUE, raw TEXT NOT NULL, txn_date TEXT,
    narration TEXT NOT NULL, amount_paise INTEGER, payee TEXT, account TEXT, status TEXT NOT NULL, reason TEXT, source TEXT, retrieved_at TEXT, resolved_by TEXT);
"""
REQUIRED = ("invoice_no", "invoice_date", "amount_paise", "gstin")
# A person cannot approve past these. The document must be corrected or rejected.
HARD_STOPS = ("required", "document", "vendor", "duplicate", "payment_conflict", "invoice_date", "instruction", "internal", "buyer", "master_changed")
MIGRATIONS = (("clients", "gstin", "TEXT"), ("vendors", "pan_status", "TEXT NOT NULL DEFAULT 'operative'"), ("vendors", "transporter_declared", "INTEGER NOT NULL DEFAULT 0"),
              ("vendors", "rcm", "TEXT"), ("vendors", "einvoice_required", "INTEGER NOT NULL DEFAULT 0"), ("invoices", "master_hash", "TEXT"), ("events", "prev_hash", "TEXT NOT NULL DEFAULT ''"), ("events", "hash", "TEXT NOT NULL DEFAULT ''"))
STALE_INVOICE_DAYS = 365  # Older than this needs a person. Tune per client.
REPEAT_ON_PO_DAYS = 180  # Same amount on the same PO inside this window is held as a possible re-presentation.
OK_STATUSES = ("pass", "info")
GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
NAME_NOISE = {"limited", "ltd", "private", "pvt", "llp", "inc", "india", "corporation", "corp", "co", "company", "the"}
FREE_MAIL = {"gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com", "proton.me", "icloud.com"}
TWO_PART_SUFFIXES = {"co.in", "org.in", "net.in", "firm.in", "gen.in", "ind.in", "ac.in", "gov.in", "co.uk"}
MIN_MATCH_CONFIDENCE = 0.9  # Crustdata identify score. Tune if honest vendors are held.
NUM = r"\d[\d,]*(?:\.\d{1,2})?"
STRICT_NUM = re.compile(r"(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d{1,2})?")
MAX_PAISE = 10 ** 13
CURRENCIES = r"usd|eur|gbp|aed|sgd|jpy|cny|chf|aud|cad|hkd|sar|qar"
TOTAL_LABELS = ("grand total", "total payable", "amount payable", "net payable", "invoice total", "invoice amount",
                "total amount", "total", "balance due", "amount due")
DATE = r"(\d{1,2}(?:st|nd|rd|th)?[ /.-]+(?:[A-Za-z]{3,9}|\d{1,2})[ /.,-]+\d{4}|\d{4}-\d{2}-\d{2})"


class PaymentConflict(Exception):
    pass


class PaymentUnavailable(Exception):
    """The provider gave no clear answer. The invoice stays APPROVED and the next run asks again."""


class PaymentRejected(Exception):
    """The provider clearly refused and created nothing. A person must decide what happens next."""


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    for table, column, kind in MIGRATIONS:
        if column not in {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
    with db:  # Scopes provider references to this set of books, so a fresh demo database cannot collide with an old one.
        db.execute("INSERT OR IGNORE INTO meta VALUES('books_id', ?)", (uuid.uuid4().hex[:12],))
    return db


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def today():
    return time.strftime("%Y-%m-%d")


def add_client(db, client_id, name, gstin=None):
    with db:
        db.execute("INSERT OR REPLACE INTO clients(id, name, gstin) VALUES(?,?,?)", (client_id, name, gstin))


def add_vendor(db, client_id, gstin, name, domain, account, ifsc, emails=(), aliases=(), onboarded_at=None, msme=None,
               agreement_days=None, tds_class=None, payee_type="other", gst_filing="monthly", opening_fy=None, opening_taxable_paise=0,
               pan_status="operative", transporter_declared=False, rcm=None, einvoice_required=False):
    with db:
        db.execute("INSERT OR REPLACE INTO vendors(client_id, gstin, name, domain, account, ifsc, emails, aliases, onboarded_at, msme, agreement_days, tds_class, "
                   "payee_type, gst_filing, opening_fy, opening_taxable_paise, pan_status, transporter_declared, rcm, einvoice_required) "
                   "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (client_id, gstin, name, domain.lower(), account, ifsc, json.dumps([e.lower() for e in emails]),
                    json.dumps(list(aliases)), onboarded_at, msme, agreement_days, tds_class, payee_type, gst_filing,
                    opening_fy, opening_taxable_paise, pan_status, int(transporter_declared), rcm, int(einvoice_required)))


def add_po(db, client_id, po, gstin, amount_paise):
    with db:
        db.execute("INSERT OR REPLACE INTO pos VALUES(?,?,?,?)", (client_id, norm_po(po), gstin, amount_paise))


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
    if not STRICT_NUM.fullmatch(str(text).strip()):
        return None  # 1180,00 must never be read as 1,18,000.
    try:
        paise = int((Decimal(str(text).replace(",", "")) * 100).to_integral_exact())
    except (InvalidOperation, ValueError, OverflowError):
        return None
    return paise if paise <= MAX_PAISE else None


def _date(text):
    text = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text.strip(), flags=re.I)
    text = re.sub(r"[,\s]+", " ", text)
    for fmt in ("%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%Y-%m-%d") if 2000 <= parsed.year <= 2100 else None
        except ValueError:
            pass
    return None


def _invoice_date(text):
    m = re.search(rf"\b(?:invoice\s+date|inv\.?\s*date|bill\s+date)\b\s*[:#-]?\s*{DATE}", text, re.I)
    if m:
        return _date(m.group(1))
    for m in re.finditer(rf"(\w+)?[ \t]*\b(?:dated?|dt)\b\.?\s*[:-]?\s*{DATE}", text, re.I):
        if (m.group(1) or "").lower() not in ("due", "po", "order", "delivery", "payment", "ship", "shipping", "dispatch"):
            return _date(m.group(2))
    return None


def _delivery_date(text):
    m = re.search(rf"\b(?:delivery|delivered|goods\s+received|grn|services?\s+rendered)(?:\s+date|\s+on)?\b\s*[:#-]?\s*{DATE}", text, re.I)
    return _date(m.group(1)) if m else None


def _amounts(text):
    """Total, taxable and tax in paise. Anything unclear is None, with an issue recorded."""
    issues, totals, taxable, tax_parts, tax_total, locked = [], {}, None, [], None, False
    value = rf"\s*(?:[:=]|-\s)?\s*(?:₹|rs\.?|inr)?\s*({NUM})\s*(?:/-)?\s*(?:only)?\.?\s*"
    label = "|".join(l.replace(" ", r"\s+") for l in TOTAL_LABELS)
    for line in text.splitlines():
        m = re.match(rf"\W*({label})\b(.*)$", line, re.I)
        if m:
            found = re.fullmatch(value, re.sub(r"\([^)]*\)", "", m.group(2)), re.I)
            if found:
                paise = _paise(found.group(1))
                if paise is None:
                    issues.append("A total is written in an unclear number format.")
                    locked = True
                else:
                    totals.setdefault(" ".join(m.group(1).lower().split()), set()).add(paise)
        numbers = re.findall(NUM, re.sub(r"\([^)]*\)", " ", line))  # (HSN 9983) and (18%) are not amounts.
        if numbers and re.match(r"\W*(?:taxable\s+(?:value|amount)|sub[ -]?total)\b", line, re.I):
            taxable = _paise(numbers[-1])
        elif numbers and re.match(r"\W*(?:cgst|sgst|utgst|igst|cess)\b", line, re.I):
            tax_parts.append(_paise(numbers[-1]))
        elif numbers and re.match(r"\W*(?:total\s+(?:tax|gst)|tax\s+amount)\b", line, re.I):
            tax_total = _paise(numbers[-1])
    tax = None if None in tax_parts else sum(tax_parts) if tax_parts else tax_total

    amount = None
    rank = [l for l in TOTAL_LABELS if l in totals]
    strong = {v for l in TOTAL_LABELS[:7] for v in totals.get(l, ())}
    if len(strong) > 1:  # Grand total 1,18,000 with net payable 68,000 needs a person.
        issues.append("The invoice states different totals.")
        locked = True
    elif rank and not locked:
        values = totals[rank[0]]
        if len(values) == 1:
            amount = next(iter(values))
        else:
            issues.append(f"Conflicting {rank[0]} values.")
            locked = True
    due = next((totals[l] for l in ("balance due", "amount due") if l in totals), None)
    if amount and due and due != {amount}:
        issues.append("Balance due differs from the invoice total, so this looks part-paid.")
        amount, locked = None, True
    if re.search(rf"\b(?:{CURRENCIES})\b|[$€£¥]", text, re.I):
        issues.append("Invoice mentions a foreign currency.")
        amount, locked = None, True
    if amount and taxable and tax and abs(taxable + tax - amount) > 100:
        issues.append("Taxable value plus tax does not equal the total.")
        amount, locked = None, True
    return amount, taxable, tax, issues, locked


def _seller_gstin(text):
    return _gstins(text)[0]


def _gstins(text):
    """Returns the seller GSTIN, or None if unclear, and the first GSTIN in a buyer block."""
    found, buyers, buyer_block = [], [], False
    for line in text.splitlines():
        if not line.strip():
            buyer_block = False
        elif re.match(r"\W*(?:details\s+of\s+)?(?:bill(?:ed)?\s*to|ship(?:ped)?\s*to|invoice\s*to|sold\s*to|buyer|customer|consignee|recipient|receiver)\b",
                      line, re.I):
            buyer_block = True
        elif re.match(r"\W*(?:details\s+of\s+)?(?:supplier|seller|vendor|from)\b", line, re.I):
            buyer_block = False
        hits = re.findall(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b", line.upper())
        (buyers if buyer_block else found).extend(hits)
    # Two different seller GSTINs is ambiguous, so it counts as missing rather than a guess.
    return (found[0] if len(set(found)) == 1 else None), (buyers[0] if buyers else None)


def norm_po(value):
    """PO-1001, po 1001 and 1001 are one PO. PO-1001-B and PO-2026-1001 stay distinct."""
    token = re.sub(r"^P\.?O\.?[ /_-]*", "", str(value).strip().upper())
    return f"PO-{int(token)}" if token.isdigit() else f"PO-{token}"


def _po(text):
    for m in re.finditer(r"\b(?:p\.?o\b\.?|purchase\s+order)\s*(?:no|number|num|#|ref)?\.?\s*[:#-]?\s*([A-Z0-9][A-Z0-9/_-]*)", text, re.I):
        token = m.group(1).rstrip("/_-")
        if re.search(r"\d", token):
            return norm_po(token)
    return None


def _invoice_no(text):
    for m in re.finditer(r"\b(?:invoice|inv|bill)\.?\s*(?:no|number|num|#)\.?\s*[:#-]?\s*"
                         r"([A-Z]{1,10} \d[A-Z0-9/._-]*|[A-Z0-9][A-Z0-9/._-]*)", text, re.I):
        token = m.group(1).rstrip("/._-")
        if re.search(r"\d", token):
            return token if len(token) <= 40 else None
    return None


def parse(text):
    amount, taxable, tax, issues, locked = _amounts(text)
    if any(unicodedata.category(c) == "Cf" or (c.isdigit() and not c.isascii()) for c in text):
        issues.append("The text contains hidden characters or non-standard digits.")
        amount, locked = None, True
    kind = re.search(r"\b(credit note|debit note|pro-?forma|quotation|statement of account|delivery challan)\b", text, re.I)
    if kind:
        issues.append(f"This document is a {kind.group(1).lower()}, not a tax invoice.")
    headers = re.findall(r"^\s*(?:from|sender|reply-to|return-path)\s*:\s*(.+)$", text, re.I | re.M)
    # Every address in a header counts, so a real address in a display name cannot hide the actual one.
    emails = {e.lower() for h in headers for e in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", h)}
    accounts = re.findall(r"\b(?:a/c|ac|acct|account)\b\.?(?:\s*(?:no|number|num|#))?\.?\s*[:#-]?\s*(\d[\d -]{7,22}\d)", text, re.I)
    return {
        "invoice_no": _invoice_no(text),
        "invoice_date": _invoice_date(text),
        "delivery_date": _delivery_date(text),
        "irn": (re.search(r"\bIRN\b\s*[:#-]?\s*([0-9a-f]{64})\b", text, re.I) or [None, None])[1],
        "po": _po(text),
        "amount_paise": amount,
        "taxable_paise": taxable,
        "tax_paise": tax,
        "amount_locked": locked,
        "gstin": _seller_gstin(text),
        "buyer_gstin": _gstins(text)[1],
        "accounts": sorted({re.sub(r"\D", "", a) for a in accounts}),
        "ifscs": sorted({c.upper() for c in re.findall(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", text, re.I)}),
        "sender_emails": sorted(emails),
        "issues": issues,
    }


def financial_year(iso):
    year, month = int(iso[:4]), int(iso[5:7])
    start = year if month >= 4 else year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def number_key(invoice_no):
    return "|".join(str(int(p)) if p.isdigit() else p for p in re.findall(r"[A-Z]+|\d+", str(invoice_no).upper()))


def number_tokens(invoice_no):
    """The parts of an invoice number that identify it: MG-5521 and 5521/MG/26-27 are the same set."""
    text = re.sub(r"(?<!\d)(?:20)?\d{2}-\d{2}(?!\d)", " ", str(invoice_no or "").upper())
    parts = re.findall(r"[A-Z]+|\d+", text)
    return frozenset(str(int(p)) if p.isdigit() else p for p in parts if p not in ("INV", "INVOICE", "BILL", "NO"))


def master_hash(vendor):
    return hashlib.sha256(f"{vendor['account']}|{vendor['ifsc']}".encode()).hexdigest() if vendor else None


def fingerprint(client_id, gstin, invoice_no, iso_date):
    """INV-0042, inv 42 and INV/42 from one vendor in one financial year are the same invoice."""
    if not (gstin and invoice_no and iso_date):
        return None
    return hashlib.sha256(f"{client_id}|{gstin}|{financial_year(iso_date)}|{number_key(invoice_no)}".encode()).hexdigest()


def import_gstr2b(db, client_id, doc):
    """Reads the portal's JSON shape. One unusable record rejects the whole file."""
    try:
        data = doc.get("data", doc)
        period_raw = str(data["rtnprd"])
        if not re.fullmatch(r"(0[1-9]|1[0-2])\d{4}", period_raw):
            raise ValueError("bad return period")
        period = f"{period_raw[2:]}-{period_raw[:2]}"
        rows = []
        for supplier in data["docdata"]["b2b"]:
            for item in supplier["inv"]:
                iso, paise = _date(item["dt"]), _paise(str(item["val"]))
                if not iso or paise is None:
                    raise ValueError("bad invoice record")
                rows.append((client_id, period, supplier["ctin"].upper(), number_key(item["inum"]), iso, paise))
    except (KeyError, TypeError, AttributeError, ValueError) as e:
        raise ValueError(f"Not a usable GSTR-2B file: {e}") from e
    with db:
        db.execute("DELETE FROM gstr2b WHERE client_id=? AND period=?", (client_id, period))
        db.executemany("INSERT OR REPLACE INTO gstr2b VALUES(?,?,?,?,?,?)", rows)
        db.execute("INSERT OR REPLACE INTO gstr2b_imports VALUES(?,?,?)", (client_id, period, now()))
    return period, len(rows)


def ingest(db, client_id, raw, read=parse):
    """Safe to repeat after a crash: the same text for the same client is one invoice."""
    digest = hashlib.sha256(" ".join(raw.split()).encode()).hexdigest()
    row = db.execute("SELECT id FROM invoices WHERE client_id=? AND raw_hash=?", (client_id, digest)).fetchone()
    if row:
        return row[0]
    f = read(raw)
    digits = re.findall(r"\d+", f["invoice_no"] or "")
    with db:
        db.execute("INSERT OR IGNORE INTO invoices(client_id, raw, raw_hash, fields, gstin, po, amount_paise, taxable_paise, tax_paise, "
                   "invoice_date, fy, number_core, fingerprint) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (client_id, raw, digest, json.dumps(f), f["gstin"], f["po"], f["amount_paise"], f["taxable_paise"], f["tax_paise"],
                    f["invoice_date"], financial_year(f["invoice_date"]) if f["invoice_date"] else None, int(digits[-1]) if digits and len(digits[-1]) <= 15 else None,
                    fingerprint(client_id, f["gstin"], f["invoice_no"], f["invoice_date"])))
    return db.execute("SELECT id FROM invoices WHERE client_id=? AND raw_hash=?", (client_id, digest)).fetchone()[0]


def same_company(a, b):
    def tokens(name):
        name = re.sub(r"\(.*?\)", " ", name.lower())
        return set(re.findall(r"[a-z0-9]+", name)) - NAME_NOISE
    x = tokens(a)
    return bool(x) and x == tokens(b)


def _edit_distance(a, b):
    """Edits needed to turn a into b. Swapping two neighbouring letters counts as one."""
    before, row = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            cost = min(row[j] + 1, current[j - 1] + 1, row[j - 1] + (ca != cb))
            if before and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cost = min(cost, before[j - 2] + 1)
            current.append(cost)
        before, row = row, current
    return row[-1]


def _skeleton(brand):
    text = brand.lower().replace("rn", "m").replace("vv", "w")
    return text.translate(str.maketrans("013578i", "oletsbl", "-_"))


def _brand_suffix(domain):
    labels = domain.split(".")
    n = 2 if ".".join(labels[-2:]) in TWO_PART_SUFFIXES else 1
    return labels[-n - 1] if len(labels) > n else labels[0], ".".join(labels[-n:])


def imitates(domain, real):
    """True for a domain built to pass as the real one. Any other non-match is a plain hold."""
    if not domain.isascii() or any(l.startswith("xn--") for l in domain.split(".")):
        return True
    brand, suffix = _brand_suffix(domain)
    real_brand, real_suffix = _brand_suffix(real)
    distance = _edit_distance(_skeleton(brand), _skeleton(real_brand))
    if distance == 0:
        return brand != real_brand or _edit_distance(suffix, real_suffix) <= 1
    return distance <= (2 if len(real_brand) >= 8 else 1 if len(real_brand) >= 4 else 0)  # Tuned on 2,994 real Indian domains.


def _mask(account):
    return f"****{account[-4:]}" if account else "none"


def _rupees(paise):
    whole, frac = divmod(abs(paise), 100)
    text = str(whole)
    if len(text) > 3:
        head, tail = text[:-3], text[-3:]
        text = ",".join(re.findall(r"\d{1,2}(?=(?:\d{2})*$)", head)) + "," + tail
    return f"₹{text}.{frac:02d}"


def msme_due(vendor, invoice_date, delivery_date=None):
    """MSMED s.15 runs from delivery or rendering. Without that date the invoice date is used, and the finding says so."""
    start = delivery_date or invoice_date
    if not vendor or vendor["msme"] not in ("micro", "small") or not start:
        return None
    days = min(vendor["agreement_days"] or 15, 45)
    return (date.fromisoformat(start) + timedelta(days=days)).isoformat()


def _check_msme(add, vendor, inv, as_of):
    source = "vendors.msme; MSMED Act s.15; Income-tax Act 1961 s.43B(h), carried into the 2025 Act as s.37(2)(g)"
    delivery = json.loads(inv["fields"]).get("delivery_date")
    kind = vendor["msme"]
    if kind is None:
        add("msme", "info", "I can't verify MSME status: the vendor master has no Udyam details.", "vendors.msme")
    elif kind == "trader":
        add("msme", "info", "Registered as a trader, which is generally outside section 15. Confirm the Udyam activity.", source)
    elif kind not in ("micro", "small"):
        add("msme", "info", f"Vendor is {kind}, so the micro and small enterprise deadline does not apply.", "vendors.msme")
    elif inv["invoice_date"]:
        due = msme_due(vendor, inv["invoice_date"], delivery)
        left = (date.fromisoformat(due) - date.fromisoformat(as_of)).days
        state = f"overdue by {-left} days, so the tax deduction moves to the year it is paid" if left < 0 else f"{left} days left"
        basis = "from the delivery date" if delivery else "from the invoice date, because no delivery date is recorded. Delivery may be earlier"
        add("msme", "info", f"{kind.title()} enterprise. Pay by {due} ({state}), counted {basis}.", source)


TDS_THRESHOLD_PAISE = {"contractor": 100_000_00, "professional": 50_000_00, "technical": 50_000_00}


def compute_tds(db, vendor, inv):
    """Returns (paise or None, status, detail). Always a draft for the reviewer to confirm."""
    kind = vendor["tds_class"]
    if kind == "goods":
        return 0, "info", "Goods purchase. No contractor or professional TDS is drafted."
    if kind not in TDS_THRESHOLD_PAISE:
        return None, "unverified", "I can't verify TDS: the vendor master has no payment category."
    base = inv["taxable_paise"]
    if not base or inv["amount_paise"] is None or abs(base + (inv["tax_paise"] or 0) - inv["amount_paise"]) > 100:
        return None, "unverified", "I can't verify TDS: the taxable value and tax do not add up to the invoice total."
    pan_ok = vendor["pan_status"] == "operative"
    if kind == "contractor" and vendor["transporter_declared"] and pan_ok:
        return 0, "pass", "Nil TDS: transporter with up to 10 goods carriages, PAN and declaration on file. Report it in the TDS return."
    prior = db.execute("SELECT COALESCE(SUM(taxable_paise), 0) FROM invoices WHERE client_id=? AND gstin=? AND fy=? AND id<? AND state IN "
                       "('READY','HELD','APPROVED','PAID') AND id NOT IN (SELECT invoice_id FROM findings WHERE check_name='duplicate' "
                       "AND status='fail')", (inv["client_id"], inv["gstin"], inv["fy"], inv["id"])).fetchone()[0]
    if vendor["opening_fy"] == inv["fy"]:  # Paid this year before Chukta started. Thresholds count the whole year.
        prior += vendor["opening_taxable_paise"]
    limit = TDS_THRESHOLD_PAISE[kind]
    if kind == "contractor":
        personal = vendor["payee_type"] == "individual" or (len(vendor["gstin"]) >= 12 and vendor["gstin"][5] in "PH")  # PAN's fourth letter.
        basis_points, entry = (100 if personal else 200), "6(i)"
        exempt = base <= 30_000_00 and prior + base <= limit
    else:
        basis_points, entry = (1000 if kind == "professional" else 200), "6(iii)"
        exempt = prior + base <= limit
    if exempt:
        return 0, "pass", f"Draft TDS nil: below the threshold in s.393(1) Table {entry}."
    if not pan_ok:
        basis_points = max(basis_points, 2000)
    nearest = lambda paise: (paise * basis_points // 10000 + 50) // 100 * 100  # Nearest rupee.
    tds = nearest(base)
    detail = f"Draft TDS {_rupees(tds)}: {basis_points / 100:g}% of {_rupees(base)} under s.393(1) Table {entry}."
    if not pan_ok:
        return tds, "unverified", f"{detail} PAN is missing or inoperative, so the higher 20% rate under s.397(2) applies."
    if 0 < prior <= limit < prior + base:
        already = db.execute("SELECT COALESCE(SUM(o.tds_paise), 0) FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id WHERE i.client_id=? AND i.gstin=? AND i.fy=? "
                             "AND i.id<?", (inv["client_id"], inv["gstin"], inv["fy"], inv["id"])).fetchone()[0]
        catch_up = max(tds, nearest(prior + base) - already)
        return catch_up, "unverified", (f"Draft TDS {_rupees(catch_up)}: the financial-year total crossed {_rupees(limit)}, so TDS applies to the whole {_rupees(prior + base)}. "
                                        "Confirm what was already deducted.")
    return tds, "pass", detail


def _check_credit(add, inv, as_of):
    """Section 16(4) claim deadline and the 180-day payment rule in CGST Rule 37."""
    if not inv["invoice_date"] or not inv["tax_paise"]:
        return
    day, today_ = date.fromisoformat(inv["invoice_date"]), date.fromisoformat(as_of)
    start = day.year if day.month >= 4 else day.year - 1
    claim_by, pay_by = date(start + 1, 11, 30), day + timedelta(days=180)
    source = "CGST Act s.16(4); CGST Rule 37"
    if today_ > claim_by:
        add("credit", "info", f"The s.16(4) window for this invoice's credit closed on {claim_by}, or earlier if the annual return was filed.", source)
    elif today_ > pay_by:
        add("credit", "info", f"Unpaid past 180 days ({pay_by}). Reverse {_rupees(inv['tax_paise'])} of credit with interest until it is paid.", source)
    else:
        urgent = "Claim soon. " if (claim_by - today_).days <= 15 else ""
        add("credit", "info", f"{urgent}Claim GST credit by {claim_by}. Pay by {pay_by} to avoid reversing it.", source)


def _check_gst(add, db, inv, f, vendor):
    if not (inv["gstin"] and f.get("invoice_no") and inv["invoice_date"]):
        return
    if vendor and vendor["rcm"]:
        add("gst", "info", f"Reverse charge ({vendor['rcm']}): the client pays this tax, so it is not expected in the supplier's GSTR-2B.", "vendors.rcm")
        return
    period = inv["invoice_date"][:7]
    year, month = int(period[:4]), int(period[5:])
    if vendor and vendor["gst_filing"] == "quarterly":  # A quarterly filer's invoices appear after the quarter ends.
        month = ((month - 1) // 3 + 1) * 3
    closes = f"{year}-{month:02d}"
    tax = inv["tax_paise"] or 0
    found = db.execute("SELECT period, value_paise FROM gstr2b WHERE client_id=? AND gstin=? AND number_key=? ORDER BY period LIMIT 1",
                       (inv["client_id"], inv["gstin"], number_key(f["invoice_no"]))).fetchone()
    if found:
        source = f"gstr2b:{found['period']}:{inv['gstin']}:{number_key(f['invoice_no'])}.val"
        if inv["amount_paise"] is not None and abs(found["value_paise"] - inv["amount_paise"]) > 100:
            add("gst", "fail", f"GSTR-2B for {found['period']} shows {_rupees(found['value_paise'])}, the invoice says "
                f"{_rupees(inv['amount_paise'])}.", source)
        else:
            add("gst", "pass", f"Matches the supplier's filing in GSTR-2B for {found['period']}.", source)
        return
    imported = db.execute("SELECT imported_at FROM gstr2b_imports WHERE client_id=? AND period=?", (inv["client_id"], closes)).fetchone()
    if imported:
        add("gst", "fail", f"Not yet reflected in the imported GSTR-2B for {closes}. {_rupees(tax)} of GST credit is at risk. "
            "A late filing can appear in a later statement, so consider retaining the GST until it does.", f"gstr2b_imports:{closes}", imported["imported_at"][:10])
    else:
        next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
        add("gst", "info", f"GST credit pending: GSTR-2B for {closes} is expected from {next_year}-{next_month:02d}-14 and is not imported yet.",
            "gstr2b_imports")


def run_checks(db, src, inv, as_of=None):
    as_of = as_of or today()
    f = json.loads(inv["fields"])
    client = inv["client_id"]
    out = []

    def add(check, status, detail, source, at=None, block=False):
        severity = "block" if block else ("hold" if status not in OK_STATUSES else "none")
        out.append((inv["id"], check, status, severity, detail, source, at or today()))

    missing = [k for k in REQUIRED if not f.get(k)]
    if missing:
        add("required", "unverified", f"I can't verify this invoice: missing or unclear {', '.join(missing)}.", "invoice text")
    else:
        add("required", "pass", "Invoice number, date, amount and GSTIN are present.", "invoice text")
    if f["issues"]:
        add("document", "fail", " ".join(f["issues"]), "invoice text")
    else:
        add("document", "pass", "Reads as a tax invoice in rupees and its totals agree.", "invoice text")

    buyer = db.execute("SELECT gstin FROM clients WHERE id=?", (client,)).fetchone()
    if buyer and buyer["gstin"] and f.get("buyer_gstin") and f["buyer_gstin"] != buyer["gstin"]:
        add("buyer", "fail", f"This invoice is billed to GSTIN {f['buyer_gstin']}, not this client.", "invoice text")

    if inv["invoice_date"]:
        age = (date.fromisoformat(as_of) - date.fromisoformat(inv["invoice_date"])).days
        if age < 0:
            add("invoice_date", "fail", f"The invoice is dated {inv['invoice_date']}, after today.", "invoice text")
        elif age > STALE_INVOICE_DAYS:
            add("invoice_date", "fail", f"The invoice is {age} days old. Confirm it is still payable.", "invoice text")

    if f["gstin"]:
        ok = gstin_valid(f["gstin"])
        add("gstin", "pass" if ok else "fail", f"GSTIN {f['gstin']} {'passes' if ok else 'fails'} the checksum.",
            "GSTIN checksum algorithm", block=not ok)

    vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (client, f["gstin"])).fetchone() if f["gstin"] else None
    if vendor:
        add("vendor", "pass", f"GSTIN belongs to {vendor['name']} on this client's vendor master.", "vendors.gstin")
    else:
        add("vendor", "unverified", "I can't verify this vendor: its GSTIN is not on this client's vendor master.", "vendors.gstin")

    if inv["fingerprint"]:
        dup = db.execute("SELECT id FROM invoices WHERE client_id=? AND fingerprint=? AND id<? AND state!='REJECTED' ORDER BY id LIMIT 1",
                         (client, inv["fingerprint"], inv["id"])).fetchone()
        if dup:
            add("duplicate", "fail", f"Same vendor, financial year and invoice number as invoice #{dup['id']}.", f"invoices.id={dup['id']}")
        else:
            add("duplicate", "pass", "No earlier invoice has this vendor, year and number.", "invoices.fingerprint")
    if inv["gstin"] and inv["amount_paise"] and inv["invoice_date"]:
        this_day = date.fromisoformat(inv["invoice_date"])
        tokens = number_tokens(f["invoice_no"])
        for r in db.execute("SELECT id, fy, po, fields, amount_paise, invoice_date FROM invoices WHERE client_id=? AND gstin=? AND id<? "
                            "AND state!='REJECTED' AND fingerprint IS NOT ? AND invoice_date IS NOT NULL ORDER BY id DESC",
                            (client, inv["gstin"], inv["id"], inv["fingerprint"])):
            same_amount = r["amount_paise"] == inv["amount_paise"]
            days = abs((date.fromisoformat(r["invoice_date"]) - this_day).days)
            if tokens and tokens == number_tokens(json.loads(r["fields"]).get("invoice_no")) and (r["fy"] == inv["fy"] or same_amount):
                add("near_duplicate", "fail", f"Invoice #{r['id']} has the same number written differently.", f"invoices.id={r['id']}")
                break
            if same_amount and days <= 7:
                add("near_duplicate", "fail", f"Invoice #{r['id']} has the same amount within 7 days.", f"invoices.id={r['id']}")
                break
            if same_amount and inv["po"] and r["po"] == inv["po"] and days <= REPEAT_ON_PO_DAYS:
                add("near_duplicate", "fail", f"Invoice #{r['id']} billed the same amount on {inv['po']} {days} days apart.", f"invoices.id={r['id']}")
                break

    if not f["po"]:
        add("po", "unverified", "I can't verify the order: no PO number on this invoice.", "invoice text")
    else:
        po = db.execute("SELECT * FROM pos WHERE client_id=? AND po=?", (client, f["po"])).fetchone()
        if not po:
            add("po", "fail", f"{f['po']} is not in this client's purchase orders.", "pos.po")
        elif po["gstin"] != f["gstin"]:
            add("po", "fail", f"{f['po']} was issued to a different vendor.", f"pos.po={f['po']}")
        elif inv["amount_paise"] is not None:
            # Held invoices keep their claim on the PO, except duplicates of another invoice.
            used = db.execute("SELECT COALESCE(SUM(amount_paise), 0) FROM invoices WHERE client_id=? AND po=? AND id<? AND state IN "
                              "('READY','HELD','APPROVED','PAID') AND id NOT IN (SELECT invoice_id FROM findings WHERE "
                              "check_name='duplicate' AND status='fail')", (client, f["po"], inv["id"])).fetchone()[0]
            left = po["amount_paise"] - used
            ok = inv["amount_paise"] <= left
            balance = f"{_rupees(left)} left on {f['po']}" if left >= 0 else f"{f['po']}, which open invoices already exceed by {_rupees(-left)}"
            add("po", "pass" if ok else "fail", f"{_rupees(inv['amount_paise'])} against {balance}.", f"pos.po={f['po']}")

    if vendor:
        odd_accounts = [a for a in f["accounts"] if a != vendor["account"]]
        odd_ifscs = [c for c in f["ifscs"] if c != vendor["ifsc"]]
        if odd_accounts or odd_ifscs:
            shown = ", ".join([_mask(a) for a in odd_accounts] + odd_ifscs)
            add("bank", "fail", f"Invoice names {shown}, but the master has {_mask(vendor['account'])} / {vendor['ifsc']}. "
                "Confirm on a known phone number before changing anything.", "vendors.account", block=True)
        elif f["accounts"]:
            add("bank", "pass", f"Bank details match the master ({_mask(vendor['account'])}).", "vendors.account")
        else:
            add("bank", "info", "No bank details on the invoice. Payment uses the vendor master.", "vendors.account")
    if re.search(r"\b(?:new|changed?|updated?|revised|different)\b[^.\n]{0,40}\b(?:bank|account|a/c|ifsc)\b|"
                 r"\b(?:bank|account|a/c|ifsc)\b[^.\n]{0,40}\b(?:changed?|updated?|revised)\b", inv["raw"], re.I):
        confirmed = vendor and db.execute("SELECT id, approved_by FROM vendor_changes WHERE client_id=? AND gstin=? AND status='APPROVED' AND new_account=? "
                                          "ORDER BY id DESC LIMIT 1", (client, vendor["gstin"], vendor["account"])).fetchone()
        if confirmed and f["accounts"] == [vendor["account"]]:
            add("bank_request", "pass", f"This bank change was confirmed by callback and approved by {confirmed['approved_by']}.", f"vendor_changes.id={confirmed['id']}")
        else:
            add("bank_request", "fail", "The text asks to change or use new bank details. Confirm on a known phone number.", "invoice text")

    code = vendor["ifsc"] if vendor else (f["ifscs"][0] if f["ifscs"] else None)
    if code:
        url = f"https://ifsc.razorpay.com/{code}"
        try:
            got = src.ifsc(code)
            if got["record"]:
                add("ifsc", "pass", f"{code} is {got['record']['bank']}, {got['record']['branch']}.", url, got["retrieved_at"])
            else:
                add("ifsc", "fail", f"{code} is not in the IFSC registry.", url, got["retrieved_at"], block=True)
        except SourceDown as e:
            add("ifsc", "unverified", f"I can't verify the IFSC: {e}.", "ifsc.razorpay.com")

    _check_gst(add, db, inv, f, vendor)
    if vendor:
        hold = db.execute("SELECT reason FROM payment_holds WHERE client_id=? AND gstin=?", (client, vendor["gstin"])).fetchone()
        if hold:
            add("instruction", "fail", hold["reason"], "the client's request")
        _check_sender(db, add, vendor, f["sender_emails"])
        _check_company(add, src, vendor)
        _check_msme(add, vendor, inv, as_of)
        _check_credit(add, inv, as_of)
        if vendor["einvoice_required"]:
            if f.get("irn"):
                add("einvoice", "pass", "An IRN in the right format is on this invoice. It was not checked against the e-invoice portal.", "invoice text")
            else:
                add("einvoice", "fail", "This supplier must issue e-invoices, and no valid IRN is on this document.", "CGST Rule 48")
        _, tds_status, tds_detail = compute_tds(db, vendor, inv)
        add("tds", tds_status, tds_detail, "vendors.tds_class; Income-tax Act 2025 s.393")
    return out


def _check_sender(db, add, vendor, emails):
    real = vendor["domain"]
    source = "email header (a claim, not authenticated)"
    if not emails:
        add("sender", "info", "No sender address was supplied, so the sender was not checked.", "invoice text")
        return
    known = json.loads(vendor["emails"])
    for address in emails:
        domain = address.split("@")[1]
        if real in FREE_MAIL:
            if address not in known:
                add("sender", "fail", f"This vendor uses {real}, and this address is not one on the master.", source)
                return
        elif not (domain == real or domain.endswith("." + real)):
            if imitates(domain, real):
                add("sender", "fail", f"Sender domain {domain} imitates the vendor's {real}.", source, block=True)
            elif db.execute("SELECT 1 FROM radar_hits WHERE client_id=? AND domain=? AND level='watch'", (vendor["client_id"], domain)).fetchone():
                add("sender", "fail", f"Imposter Radar already found {domain}, a lookalike of {real} that can send email.", "radar_hits.domain", block=True)
            else:
                add("sender", "fail", f"Sender domain {domain} is not the vendor's {real}.", source)
            return
    add("sender", "pass", f"Sender matches the vendor master ({real}).", source)


def _check_company(add, src, vendor):
    real = vendor["domain"]
    where = "crustdata:/company/identify"
    established = vendor["onboarded_at"]
    if real in FREE_MAIL:
        if established:
            add("company", "info", f"I can't verify this from company data: the vendor uses {real}. Onboarded {established}.", "vendors.onboarded_at")
        else:
            add("company", "unverified", f"I can't verify the company: new vendor on {real}, with no company domain.", "vendors.domain")
        return
    try:
        got = src.identify(real)
    except SourceDown as e:
        add("company", "unverified", f"I can't verify the company: {e}.", where)
        return
    m = got["match"]
    if not m:
        if established:
            add("company", "info", f"I can't verify this from Crustdata, which has no record for {real}. Vendor onboarded {established}.",
                f"{where}?domain={real}", got["retrieved_at"])
        else:
            add("company", "unverified", f"I can't verify the company: Crustdata has no record for {real}, and this is a new vendor.",
                f"{where}?domain={real}", got["retrieved_at"])
        return
    cite = f"{where}#{m['id']}.basic_info.name"
    names = [vendor["name"], *json.loads(vendor["aliases"])]
    if m.get("status") and m["status"] != "active":
        add("company", "unverified", f"I can't verify the company is trading: its record for {real} says {m['status']}.", cite, got["retrieved_at"])
    elif (m.get("confidence") or 0) < MIN_MATCH_CONFIDENCE:
        add("company", "unverified", f"I can't verify the company: the match for {real} is low confidence.", cite, got["retrieved_at"])
    elif any(same_company(n, m["name"]) for n in names):
        add("company", "pass", f"{real} resolves to {m['name'].rstrip('.')}" + (f", {m['status']}, record updated {m['updated_at'][:10]}." if m.get("status") and m.get("updated_at") else "."),
            cite, got["retrieved_at"])
    else:
        add("company", "unverified", f"I can't verify the company: {real} resolves to {m['name']}, but the master says {vendor['name']}.",
            cite, got["retrieved_at"])


def decide(findings):
    if any(row[3] == "block" for row in findings):
        return "BLOCKED"
    return "HELD" if any(row[2] not in OK_STATUSES for row in findings) else "READY"


def process(db, src, as_of=None):
    """Check every NEW invoice. A crash leaves it NEW, and cached sources make the rerun free."""
    new = db.execute("SELECT * FROM invoices WHERE state='NEW' ORDER BY id").fetchall()
    domains = {r["domain"] for i in new if i["gstin"] for r in
               db.execute("SELECT domain FROM vendors WHERE client_id=? AND gstin=?", (i["client_id"], i["gstin"]))} - FREE_MAIL
    if domains:
        try:
            src.identify_many(sorted(domains))
        except SourceDown:
            pass  # Each invoice then records the outage in its own finding and is held.
    for inv in new:
        try:
            findings = run_checks(db, src, inv, as_of)
            vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (inv["client_id"], inv["gstin"])).fetchone()
            due = msme_due(vendor, inv["invoice_date"], json.loads(inv["fields"]).get("delivery_date"))
        except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError, sqlite3.DataError) as e:
            # One unreadable record must not stop the batch or be read as clean.
            findings = [(inv["id"], "internal", "unverified", "hold", f"I can't verify this invoice: checks stopped ({type(e).__name__}).",
                         "chukta", today())]
            vendor, due = None, None
        with db:
            state = decide(findings)
            moved = db.execute("UPDATE invoices SET state=?, due_date=?, master_hash=? WHERE id=? AND state='NEW'",
                               (state, due, master_hash(vendor), inv["id"])).rowcount
            if moved:  # A stale worker can never rewrite the evidence of a signed invoice.
                db.execute("DELETE FROM findings WHERE invoice_id=?", (inv["id"],))
                db.executemany("INSERT INTO findings VALUES(?,?,?,?,?,?,?)", findings)
                _event(db, inv["id"], "checked", "chukta", state)


def event_hash(previous, invoice_id, event, actor, detail, at):
    return hashlib.sha256(json.dumps([previous, invoice_id, event, actor, detail, at], ensure_ascii=False).encode()).hexdigest()


def _event(db, invoice_id, event, actor, detail):
    """Each event commits to the one before it, so an edited history no longer replays."""
    if not db.in_transaction:
        db.execute("BEGIN IMMEDIATE")
    last = db.execute("SELECT hash FROM events ORDER BY id DESC LIMIT 1").fetchone()
    previous, at = last[0] if last else "", now()
    db.execute("INSERT INTO events(invoice_id, event, actor, detail, at, prev_hash, hash) VALUES(?,?,?,?,?,?,?)",
               (invoice_id, event, actor, detail, at, previous, event_hash(previous, invoice_id, event, actor, detail, at)))


def evidence_hash(db, invoice_id):
    rows = [tuple(r) for r in db.execute("SELECT check_name, status, detail, source, retrieved_at FROM findings "
                                         "WHERE invoice_id=? ORDER BY check_name", (invoice_id,))]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def add_alias(db, src, invoice_id, by):
    """A person confirms that the company record's name is this vendor, then the invoice is rechecked."""
    inv = db.execute("SELECT client_id, gstin FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    vendor = inv and db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (inv["client_id"], inv["gstin"])).fetchone()
    if not vendor or not by.strip():
        raise ValueError("alias needs a known vendor and a named person")
    match = src.identify(vendor["domain"])["match"]
    if not match:
        raise ValueError("no company record to confirm")
    aliases = sorted({*json.loads(vendor["aliases"]), match["name"]})
    with db:
        db.execute("UPDATE vendors SET aliases=? WHERE client_id=? AND gstin=?", (json.dumps(aliases), inv["client_id"], inv["gstin"]))
        _event(db, invoice_id, "alias_confirmed", by, f"{vendor['name']} is also {match['name']}")
    return recheck(db, src, invoice_id, by)


def approve(db, invoice_id, by, note="", tds_override_paise=None, retain_gst=False, expected_evidence=None):
    """A named person signs. The exact payee and amount are frozen here, and payment uses only this record."""
    if not by.strip():
        raise ValueError("approval needs a named person")
    with db:
        db.execute("BEGIN IMMEDIATE")
        inv = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv or inv["state"] not in ("READY", "HELD"):
            raise ValueError(f"invoice {invoice_id} cannot be approved from {inv and inv['state']}")
        marks = ",".join("?" * len(HARD_STOPS))
        stop = db.execute(f"SELECT check_name FROM findings WHERE invoice_id=? AND status NOT IN ('pass','info') "
                          f"AND check_name IN ({marks})", (invoice_id, *HARD_STOPS)).fetchone()
        if stop:
            raise ValueError(f"invoice {invoice_id} cannot be paid: {stop['check_name']} check")
        if inv["state"] == "HELD" and not note.strip():
            raise ValueError("approving a held invoice needs a note saying what the person checked")
        vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (inv["client_id"], inv["gstin"])).fetchone()
        if inv["master_hash"] != master_hash(vendor):
            raise ValueError(f"invoice {invoice_id}: the vendor's bank details changed after this check. Recheck it first.")
        if inv["po"]:
            po = db.execute("SELECT * FROM pos WHERE client_id=? AND po=?", (inv["client_id"], inv["po"])).fetchone()
            if po and po["gstin"] != inv["gstin"]:
                raise ValueError(f"invoice {invoice_id} cannot be paid: {inv['po']} belongs to another vendor")
            if po:
                signed = db.execute("SELECT COALESCE(SUM(o.gross_paise), 0) FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id "
                                    "WHERE i.client_id=? AND i.po=? AND i.state IN ('APPROVED','PAID')",
                                    (inv["client_id"], inv["po"])).fetchone()[0]
                if signed + inv["amount_paise"] > po["amount_paise"]:
                    raise ValueError(f"invoice {invoice_id} would overspend {inv['po']}")
        evidence = evidence_hash(db, invoice_id)
        if expected_evidence and expected_evidence != evidence:
            raise ValueError(f"invoice {invoice_id} changed after you reviewed it. Review it again.")
        tds = compute_tds(db, vendor, inv)[0]
        if tds_override_paise is not None:
            if tds_override_paise < 0 or not note.strip():
                raise ValueError("changing the TDS draft needs a valid amount and a note")
            tds = tds_override_paise
        if tds is None:
            raise ValueError(f"invoice {invoice_id}: TDS is unverified, so a person must enter the amount")
        retained = 0
        if retain_gst:
            if not inv["tax_paise"]:
                raise ValueError(f"invoice {invoice_id} has no GST amount to retain")
            retained = inv["tax_paise"]
        net = inv["amount_paise"] - tds - retained
        if net <= 0:
            raise ValueError(f"invoice {invoice_id}: net payable must be above zero")
        books = db.execute("SELECT value FROM meta WHERE key='books_id'").fetchone()[0]
        try:
            db.execute("INSERT INTO payment_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (invoice_id, inv["client_id"], f"chukta:{books}:{inv['fingerprint']}", vendor["gstin"], vendor["name"], vendor["account"],
                        vendor["ifsc"], inv["amount_paise"], tds, retained, net, evidence, by, now()))
        except sqlite3.IntegrityError as e:
            raise ValueError(f"invoice {invoice_id} already has a signed payment") from e
        db.execute("UPDATE invoices SET state='APPROVED' WHERE id=?", (invoice_id,))
        _event(db, invoice_id, "approved", by, f"{note or 'clean invoice'} | gross {_rupees(inv['amount_paise'])}, TDS {_rupees(tds)}, "
               f"GST retained {_rupees(retained)}, net {_rupees(net)}")


def propose_bank_change(db, invoice_id, by, callback_note):
    """Maker: records the phone call that confirmed new bank details. Nothing changes until a second person approves."""
    if not by.strip() or len(callback_note.strip()) < 10:
        raise ValueError("Record who you called, on which known number, and what they confirmed")
    with db:
        db.execute("BEGIN IMMEDIATE")
        inv = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv or inv["state"] != "BLOCKED":
            raise ValueError("Only a blocked invoice can start a bank change")
        if db.execute("SELECT 1 FROM findings WHERE invoice_id=? AND check_name='sender' AND severity='block'", (invoice_id,)).fetchone():
            raise ValueError("This came from an imitation domain. Reject it instead of changing the vendor's bank details.")
        vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (inv["client_id"], inv["gstin"])).fetchone()
        f = json.loads(inv["fields"])
        if not vendor or len(f["accounts"]) != 1 or len(f["ifscs"]) != 1 or f["accounts"][0] == vendor["account"]:
            raise ValueError("This invoice does not name one clear new bank account")
        if db.execute("SELECT 1 FROM vendor_changes WHERE client_id=? AND gstin=? AND status='PENDING'", (inv["client_id"], vendor["gstin"])).fetchone():
            raise ValueError("A bank change for this vendor is already waiting for approval")
        change = db.execute("INSERT INTO vendor_changes(client_id, gstin, invoice_id, old_account, old_ifsc, new_account, new_ifsc, proposed_by, callback_note, proposed_at) "
                            "VALUES(?,?,?,?,?,?,?,?,?,?)", (inv["client_id"], vendor["gstin"], invoice_id, vendor["account"], vendor["ifsc"], f["accounts"][0], f["ifscs"][0],
                                                           by.strip(), callback_note.strip()[:500], now())).lastrowid
        _event(db, invoice_id, "bank_change_proposed", by.strip(), f"{_mask(vendor['account'])} to {_mask(f['accounts'][0])}. {callback_note.strip()[:300]}")
    return change


def approve_bank_change(db, src, change_id, by):
    """Checker: a different person applies the change, then every open invoice for the vendor is checked again."""
    with db:
        db.execute("BEGIN IMMEDIATE")
        c = db.execute("SELECT * FROM vendor_changes WHERE id=?", (change_id,)).fetchone()
        if not c or c["status"] != "PENDING":
            raise ValueError("This bank change is not waiting for approval")
        if not by.strip() or by.strip().casefold() == c["proposed_by"].casefold():
            raise ValueError("A second person must approve a bank change")
        vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (c["client_id"], c["gstin"])).fetchone()
        if (vendor["account"], vendor["ifsc"]) != (c["old_account"], c["old_ifsc"]):
            raise ValueError("The vendor master changed since this was proposed")
        db.execute("UPDATE vendors SET account=?, ifsc=? WHERE client_id=? AND gstin=?", (c["new_account"], c["new_ifsc"], c["client_id"], c["gstin"]))
        db.execute("UPDATE vendor_changes SET status='APPROVED', approved_by=?, approved_at=? WHERE id=?", (by.strip(), now(), change_id))
        _event(db, c["invoice_id"], "bank_change_approved", by.strip(), f"{_mask(c['old_account'])} to {_mask(c['new_account'])}")
        open_ids = [r[0] for r in db.execute("SELECT id FROM invoices WHERE client_id=? AND gstin=? AND state IN ('READY','HELD','BLOCKED')", (c["client_id"], c["gstin"]))]
        for i in open_ids:
            db.execute("UPDATE invoices SET state='NEW' WHERE id=?", (i,))
            _event(db, i, "recheck", by.strip(), "vendor bank details changed")
    process(db, src)
    return open_ids


def reject(db, invoice_id, by, reason):
    if not by.strip() or not reason.strip():
        raise ValueError("rejection needs a named person and a reason")
    with db:
        db.execute("BEGIN IMMEDIATE")
        changed = db.execute("UPDATE invoices SET state='REJECTED' WHERE id=? AND state IN ('READY','HELD','BLOCKED')", (invoice_id,))
        if not changed.rowcount:
            raise ValueError(f"invoice {invoice_id} cannot be rejected from its current state")
        _event(db, invoice_id, "rejected", by, reason)


def recheck(db, src, invoice_id, by):
    """Run the checks again after a fact changed. Any earlier sign-off no longer counts."""
    with _pay_lock(db), db:  # Waits for a payment run in progress, so a recheck cannot race it.
        db.execute("BEGIN IMMEDIATE")
        inv = db.execute("SELECT state FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv or inv["state"] not in ("READY", "HELD", "BLOCKED", "APPROVED"):
            raise ValueError(f"invoice {invoice_id} cannot be rechecked")
        order = db.execute("SELECT idempotency_key FROM payment_orders WHERE invoice_id=?", (invoice_id,)).fetchone()
        if order and (db.execute("SELECT 1 FROM provider_payments WHERE idempotency_key=?", (order[0],)).fetchone() or
                      db.execute("SELECT 1 FROM events WHERE invoice_id=? AND event='payment_attempt' AND detail=?", (invoice_id, order[0])).fetchone()):
            raise ValueError(f"invoice {invoice_id} already has a payment. Run the payment step to record it.")
        db.execute("DELETE FROM payment_orders WHERE invoice_id=?", (invoice_id,))
        db.execute("UPDATE invoices SET state='NEW' WHERE id=?", (invoice_id,))
        _event(db, invoice_id, "recheck", by, f"was {inv['state']}")
    process(db, src)
    return db.execute("SELECT state FROM invoices WHERE id=?", (invoice_id,)).fetchone()[0]


class SandboxBank:
    """Local stand-in for a provider's test mode. A repeated key returns the first payment."""

    def __init__(self, db):
        self.db = db

    def pay(self, key, account, ifsc, amount_paise):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO provider_payments VALUES(?,?,?,?,?,?,?)",
                            (key, "sandbox", f"sandbox_{uuid.uuid4().hex[:12]}", account, ifsc, amount_paise, now()))
        row = self.db.execute("SELECT * FROM provider_payments WHERE idempotency_key=?", (key,)).fetchone()
        if (row["account"], row["ifsc"], row["amount_paise"]) != (account, ifsc, amount_paise):
            raise PaymentConflict(key)
        return row["ref"]


@contextlib.contextmanager
def _pay_lock(db):
    """One payer at a time. The OS releases this lock if the process is killed."""
    path = db.execute("PRAGMA database_list").fetchone()["file"]
    if not path:
        yield
        return
    with open(path + ".paylock", "w") as handle:
        if fcntl:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield
            return
        while True:
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.2)
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def pay_approved(db, bank):
    """Pays only the frozen order, never the current master or the invoice text."""
    with _pay_lock(db):
        orders = db.execute("SELECT o.* FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id WHERE i.state='APPROVED' "
                            "ORDER BY COALESCE(i.due_date, '9999'), o.invoice_id").fetchall()
        for o in orders:
            if db.execute("SELECT state FROM invoices WHERE id=?", (o["invoice_id"],)).fetchone()[0] != "APPROVED":
                continue  # Rejected or rechecked after this batch was read.
            vendor = db.execute("SELECT account, ifsc FROM vendors WHERE client_id=? AND gstin=?", (o["client_id"], o["payee_gstin"])).fetchone()
            sent = db.execute("SELECT 1 FROM provider_payments WHERE idempotency_key=?", (o["idempotency_key"],)).fetchone()
            inv_po = db.execute("SELECT po FROM invoices WHERE id=?", (o["invoice_id"],)).fetchone()[0]
            po = db.execute("SELECT * FROM pos WHERE client_id=? AND po=?", (o["client_id"], inv_po)).fetchone() if inv_po else None
            signed = db.execute("SELECT COALESCE(SUM(x.gross_paise), 0) FROM payment_orders x JOIN invoices i ON i.id=x.invoice_id WHERE i.client_id=? AND i.po=? "
                                "AND i.state IN ('APPROVED','PAID')", (o["client_id"], inv_po)).fetchone()[0] if inv_po else 0
            po_moved = bool(po) and (po["gstin"] != o["payee_gstin"] or signed > po["amount_paise"])
            if not sent and (po_moved or not vendor or (vendor["account"], vendor["ifsc"]) != (o["account"], o["ifsc"])):
                with db:  # A signed payment never goes out on facts that have moved on. A person must look again.
                    db.execute("INSERT OR REPLACE INTO findings VALUES(?,?,?,?,?,?,?)",
                               (o["invoice_id"], "master_changed", "fail", "hold", "The vendor's bank details or PO changed after sign-off. Recheck and sign again.", "vendors.account", today()))
                    db.execute("DELETE FROM payment_orders WHERE invoice_id=?", (o["invoice_id"],))
                    db.execute("UPDATE invoices SET state='HELD' WHERE id=? AND state='APPROVED'", (o["invoice_id"],))
                    _event(db, o["invoice_id"], "master_changed", "chukta", "payment stopped")
                continue
            with db:  # Recorded first, so an unclear provider reply can never be rechecked away.
                _event(db, o["invoice_id"], "payment_attempt", "chukta", o["idempotency_key"])
            try:
                ref = bank.pay(o["idempotency_key"], o["account"], o["ifsc"], o["net_paise"])
            except PaymentUnavailable as e:
                with db:
                    _event(db, o["invoice_id"], "payment_retry_needed", "chukta", str(e))
                continue
            except PaymentRejected as e:
                with db:
                    db.execute("INSERT OR REPLACE INTO findings VALUES(?,?,?,?,?,?,?)",
                               (o["invoice_id"], "payment", "fail", "hold", f"The payment provider refused this payment: {e}.",
                                "provider response", today()))
                    db.execute("DELETE FROM payment_orders WHERE invoice_id=?", (o["invoice_id"],))
                    db.execute("UPDATE invoices SET state='HELD' WHERE id=? AND state='APPROVED'", (o["invoice_id"],))
                    _event(db, o["invoice_id"], "payment_rejected", "chukta", str(e))
                continue
            except PaymentConflict:
                with db:
                    db.execute("INSERT OR REPLACE INTO findings VALUES(?,?,?,?,?,?,?)",
                               (o["invoice_id"], "payment_conflict", "fail", "hold",
                                "A payment with this key already exists for different details.", "provider_payments", today()))
                    db.execute("DELETE FROM payment_orders WHERE invoice_id=?", (o["invoice_id"],))
                    db.execute("UPDATE invoices SET state='HELD' WHERE id=? AND state='APPROVED'", (o["invoice_id"],))
                    _event(db, o["invoice_id"], "payment_conflict", "chukta", o["idempotency_key"])
                continue
            with db:
                db.execute("UPDATE invoices SET state='PAID', payment_ref=? WHERE id=? AND state='APPROVED'", (ref, o["invoice_id"]))
                _event(db, o["invoice_id"], "paid", "chukta", ref)
