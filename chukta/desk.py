"""The payables desk: parse, check, decide, approve, pay exactly once.

Decisions are fixed policy over evidence. No model output can move money.
State: NEW -> READY | HELD | BLOCKED -> APPROVED -> PAID, or -> REJECTED.
"""
import contextlib
import fcntl
import hashlib
import json
import re
import sqlite3
import time
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from .sources import SourceDown

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vendors(client_id TEXT NOT NULL, gstin TEXT NOT NULL, name TEXT NOT NULL, domain TEXT NOT NULL,
    account TEXT NOT NULL, ifsc TEXT NOT NULL, emails TEXT NOT NULL DEFAULT '[]', aliases TEXT NOT NULL DEFAULT '[]',
    onboarded_at TEXT, msme TEXT, agreement_days INTEGER, tds_class TEXT, payee_type TEXT NOT NULL DEFAULT 'other',
    gst_filing TEXT NOT NULL DEFAULT 'monthly', PRIMARY KEY(client_id, gstin));
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
"""
REQUIRED = ("invoice_no", "invoice_date", "amount_paise", "gstin")
# A person cannot approve past these. The document must be corrected or rejected.
HARD_STOPS = ("required", "document", "vendor", "duplicate", "payment_conflict")
OK_STATUSES = ("pass", "info")
GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
NAME_NOISE = {"limited", "ltd", "private", "pvt", "llp", "inc", "india", "corporation", "corp", "co", "company", "the"}
FREE_MAIL = {"gmail.com", "yahoo.com", "yahoo.co.in", "outlook.com", "hotmail.com", "rediffmail.com", "proton.me", "icloud.com"}
TWO_PART_SUFFIXES = {"co.in", "org.in", "net.in", "firm.in", "gen.in", "ind.in", "ac.in", "gov.in", "co.uk"}
MIN_MATCH_CONFIDENCE = 0.9  # Crustdata identify score. Tune if honest vendors are held.
NUM = r"\d[\d,]*(?:\.\d{1,2})?"
TOTAL_LABELS = ("grand total", "total payable", "amount payable", "net payable", "invoice total", "invoice amount",
                "total amount", "total", "balance due", "amount due")
DATE = r"(\d{1,2}(?:st|nd|rd|th)?[ /.-]+(?:[A-Za-z]{3,9}|\d{1,2})[ /.,-]+\d{4}|\d{4}-\d{2}-\d{2})"


class PaymentConflict(Exception):
    pass


class PaymentUnavailable(Exception):
    """The provider gave no clear answer. The invoice stays APPROVED and the next run asks again."""


def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def today():
    return time.strftime("%Y-%m-%d")


def add_client(db, client_id, name):
    with db:
        db.execute("INSERT OR REPLACE INTO clients VALUES(?,?)", (client_id, name))


def add_vendor(db, client_id, gstin, name, domain, account, ifsc, emails=(), aliases=(), onboarded_at=None, msme=None,
               agreement_days=None, tds_class=None, payee_type="other", gst_filing="monthly"):
    with db:
        db.execute("INSERT OR REPLACE INTO vendors VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (client_id, gstin, name, domain.lower(), account, ifsc, json.dumps([e.lower() for e in emails]),
                    json.dumps(list(aliases)), onboarded_at, msme, agreement_days, tds_class, payee_type, gst_filing))


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
    try:
        return int((Decimal(text.replace(",", "")) * 100).to_integral_exact())
    except (InvalidOperation, ValueError):
        return None


def _date(text):
    text = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text.strip(), flags=re.I)
    text = re.sub(r"[,\s]+", " ", text)
    for fmt in ("%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
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


def _amounts(text):
    """Total, taxable and tax in paise. Anything unclear is None, with an issue recorded."""
    issues, totals, taxable, tax_parts, tax_total = [], {}, None, [], None
    value = rf"\s*[:=-]?\s*(?:₹|rs\.?|inr)?\s*({NUM})\s*(?:/-)?\s*(?:only)?\.?\s*"
    label = "|".join(l.replace(" ", r"\s+") for l in TOTAL_LABELS)
    for line in text.splitlines():
        m = re.match(rf"\W*({label})\b(.*)$", line, re.I)
        if m:
            found = re.fullmatch(value, re.sub(r"\([^)]*\)", "", m.group(2)), re.I)
            if found:
                totals.setdefault(" ".join(m.group(1).lower().split()), set()).add(_paise(found.group(1)))
        numbers = re.findall(NUM, line)
        if numbers and re.match(r"\W*(?:taxable\s+(?:value|amount)|sub[ -]?total)\b", line, re.I):
            taxable = _paise(numbers[-1])
        elif numbers and re.match(r"\W*(?:cgst|sgst|utgst|igst|cess)\b", line, re.I):
            tax_parts.append(_paise(numbers[-1]))
        elif numbers and re.match(r"\W*(?:total\s+(?:tax|gst)|tax\s+amount)\b", line, re.I):
            tax_total = _paise(numbers[-1])
    tax = sum(tax_parts) if tax_parts else tax_total

    amount, locked = None, False
    rank = [l for l in TOTAL_LABELS if l in totals]
    if rank:
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
    if re.search(r"\b(?:usd|eur|gbp|aed|sgd)\b|[$€£]", text, re.I):
        issues.append("Invoice mentions a foreign currency.")
        amount, locked = None, True
    if amount and taxable and tax and abs(taxable + tax - amount) > 100:
        issues.append("Taxable value plus tax does not equal the total.")
        amount, locked = None, True
    return amount, taxable, tax, issues, locked


def _seller_gstin(text):
    found, buyer_block = [], False
    for line in text.splitlines():
        if not line.strip():
            buyer_block = False
        elif re.match(r"\W*(?:details\s+of\s+)?(?:bill(?:ed)?\s*to|ship(?:ped)?\s*to|buyer|customer|consignee|recipient|receiver)\b",
                      line, re.I):
            buyer_block = True
        elif re.match(r"\W*(?:details\s+of\s+)?(?:supplier|seller|vendor|from)\b", line, re.I):
            buyer_block = False
        if not buyer_block:
            found += re.findall(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]Z[A-Z0-9]\b", line.upper())
    # Two different seller GSTINs is ambiguous, so it counts as missing rather than a guess.
    return found[0] if len(set(found)) == 1 else None


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
            return token
    return None


def parse(text):
    amount, taxable, tax, issues, locked = _amounts(text)
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
        "po": _po(text),
        "amount_paise": amount,
        "taxable_paise": taxable,
        "tax_paise": tax,
        "amount_locked": locked,
        "gstin": _seller_gstin(text),
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
                    f["invoice_date"], financial_year(f["invoice_date"]) if f["invoice_date"] else None, int(digits[-1]) if digits else None,
                    fingerprint(client_id, f["gstin"], f["invoice_no"], f["invoice_date"])))
    return db.execute("SELECT id FROM invoices WHERE client_id=? AND raw_hash=?", (client_id, digest)).fetchone()[0]


def same_company(a, b):
    def tokens(name):
        name = re.sub(r"\(.*?\)", " ", name.lower())
        return set(re.findall(r"[a-z0-9]+", name)) - NAME_NOISE
    x = tokens(a)
    return bool(x) and x == tokens(b)


def _edit_distance(a, b):
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
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
    return distance <= (2 if len(real_brand) >= 6 else 1 if len(real_brand) >= 4 else 0)


def _mask(account):
    return f"****{account[-4:]}" if account else "none"


def _rupees(paise):
    whole, frac = divmod(abs(paise), 100)
    text = str(whole)
    if len(text) > 3:
        head, tail = text[:-3], text[-3:]
        text = ",".join(re.findall(r"\d{1,2}(?=(?:\d{2})*$)", head)) + "," + tail
    return f"₹{text}.{frac:02d}"


def msme_due(vendor, invoice_date):
    """Section 15 runs from acceptance. ponytail: uses invoice date, the earliest case, until goods-receipt dates exist."""
    if not vendor or vendor["msme"] not in ("micro", "small") or not invoice_date:
        return None
    days = min(vendor["agreement_days"] or 15, 45)
    return (date.fromisoformat(invoice_date) + timedelta(days=days)).isoformat()


def _check_msme(add, vendor, inv, as_of):
    source = "vendors.msme; Income-tax Act 1961 s.43B(h) and its 2025 Act equivalent; MSMED Act s.15"
    kind = vendor["msme"]
    if kind is None:
        add("msme", "info", "I can't verify MSME status: the vendor master has no Udyam details.", "vendors.msme")
    elif kind == "trader":
        add("msme", "info", "Registered as a trader. Whether the payment deadline applies needs a person's review.", source)
    elif kind not in ("micro", "small"):
        add("msme", "info", f"Vendor is {kind}, so the micro and small enterprise deadline does not apply.", "vendors.msme")
    elif inv["invoice_date"]:
        due = msme_due(vendor, inv["invoice_date"])
        left = (date.fromisoformat(due) - date.fromisoformat(as_of)).days
        state = f"overdue by {-left} days, so the tax deduction moves to the year it is paid" if left < 0 else f"{left} days left"
        add("msme", "info", f"{kind.title()} enterprise. Pay by {due} ({state}).", source)


TDS_THRESHOLD_PAISE = {"contractor": 100_000_00, "professional": 50_000_00, "technical": 50_000_00}


def compute_tds(db, vendor, inv):
    """Returns (paise or None, status, detail). Always a draft for the reviewer to confirm."""
    kind = vendor["tds_class"]
    if kind == "goods":
        return 0, "info", "Goods purchase. No contractor or professional TDS is drafted."
    if kind not in TDS_THRESHOLD_PAISE:
        return None, "unverified", "I can't verify TDS: the vendor master has no payment category."
    base = inv["taxable_paise"]
    if not base:
        return None, "unverified", "I can't verify TDS: the taxable value is unclear."
    prior = db.execute("SELECT COALESCE(SUM(taxable_paise), 0) FROM invoices WHERE client_id=? AND gstin=? AND fy=? AND id<? AND state IN "
                       "('READY','HELD','APPROVED','PAID') AND id NOT IN (SELECT invoice_id FROM findings WHERE check_name='duplicate' "
                       "AND status='fail')", (inv["client_id"], inv["gstin"], inv["fy"], inv["id"])).fetchone()[0]
    limit = TDS_THRESHOLD_PAISE[kind]
    if kind == "contractor":
        basis_points, entry = (100 if vendor["payee_type"] == "individual" else 200), "6(i)"
        exempt = base <= 30_000_00 and prior + base <= limit
    else:
        basis_points, entry = (1000 if kind == "professional" else 200), "6(iii)"
        exempt = prior + base <= limit
    if exempt:
        return 0, "pass", f"Draft TDS nil: below the threshold in s.393(1) Table {entry}."
    tds = (base * basis_points // 10000 + 50) // 100 * 100  # Nearest rupee.
    detail = f"Draft TDS {_rupees(tds)}: {basis_points / 100:g}% of {_rupees(base)} under s.393(1) Table {entry}."
    if 0 < prior <= limit < prior + base:
        return tds, "unverified", f"{detail} The financial-year total just crossed {_rupees(limit)}, so earlier invoices may need TDS too."
    return tds, "pass", detail


def _check_gst(add, db, inv, f, vendor):
    if not (inv["gstin"] and f.get("invoice_no") and inv["invoice_date"]):
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
        add("gst", "fail", f"Not in the imported GSTR-2B for {closes}. {_rupees(tax)} of GST credit is at risk. "
            "Consider retaining the GST until the supplier files.", f"gstr2b_imports:{closes}", imported["imported_at"][:10])
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
        for r in db.execute("SELECT id, fy, number_core, amount_paise, invoice_date FROM invoices WHERE client_id=? AND gstin=? AND id<? "
                            "AND state!='REJECTED' AND fingerprint IS NOT ? AND invoice_date IS NOT NULL ORDER BY id DESC",
                            (client, inv["gstin"], inv["id"], inv["fingerprint"])):
            if r["fy"] == inv["fy"] and inv["number_core"] is not None and r["number_core"] == inv["number_core"]:
                add("near_duplicate", "fail", f"Invoice #{r['id']} has the same number with a different format.", f"invoices.id={r['id']}")
                break
            if r["amount_paise"] == inv["amount_paise"] and abs((date.fromisoformat(r["invoice_date"]) - this_day).days) <= 7:
                add("near_duplicate", "fail", f"Invoice #{r['id']} has the same amount within 7 days.", f"invoices.id={r['id']}")
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
            add("po", "pass" if ok else "fail", f"{_rupees(inv['amount_paise'])} against {_rupees(left)} left on {f['po']}.", f"pos.po={f['po']}")

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
        _check_sender(add, vendor, f["sender_emails"])
        _check_company(add, src, vendor)
        _check_msme(add, vendor, inv, as_of)
        _, tds_status, tds_detail = compute_tds(db, vendor, inv)
        add("tds", tds_status, tds_detail, "vendors.tds_class; Income-tax Act 2025 s.393")
    return out


def _check_sender(add, vendor, emails):
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
    if (m.get("confidence") or 0) < MIN_MATCH_CONFIDENCE:
        add("company", "unverified", f"I can't verify the company: the match for {real} is low confidence.", cite, got["retrieved_at"])
    elif any(same_company(n, m["name"]) for n in names):
        add("company", "pass", f"{real} resolves to {m['name']}.", cite, got["retrieved_at"])
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
        except (KeyError, TypeError, ValueError, AttributeError, IndexError, sqlite3.DataError) as e:
            # One unreadable record must not stop the batch or be read as clean.
            findings = [(inv["id"], "internal", "unverified", "hold", f"I can't verify this invoice: checks stopped ({type(e).__name__}).",
                         "chukta", today())]
        with db:
            db.execute("DELETE FROM findings WHERE invoice_id=?", (inv["id"],))
            db.executemany("INSERT OR REPLACE INTO findings VALUES(?,?,?,?,?,?,?)", findings)
            state = decide(findings)
            vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (inv["client_id"], inv["gstin"])).fetchone()
            db.execute("UPDATE invoices SET state=?, due_date=? WHERE id=? AND state='NEW'",
                       (state, msme_due(vendor, inv["invoice_date"]), inv["id"]))
            _event(db, inv["id"], "checked", "chukta", state)


def _event(db, invoice_id, event, actor, detail):
    db.execute("INSERT INTO events(invoice_id, event, actor, detail, at) VALUES(?,?,?,?,?)", (invoice_id, event, actor, detail, now()))


def approve(db, invoice_id, by, note="", tds_override_paise=None, retain_gst=False):
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
        rows = [tuple(r) for r in db.execute("SELECT check_name, status, detail, source, retrieved_at FROM findings "
                                             "WHERE invoice_id=? ORDER BY check_name", (invoice_id,))]
        evidence = hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()
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
        db.execute("INSERT OR REPLACE INTO payment_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (invoice_id, inv["client_id"], f"chukta:{inv['fingerprint']}", vendor["gstin"], vendor["name"], vendor["account"],
                    vendor["ifsc"], inv["amount_paise"], tds, retained, net, evidence, by, now()))
        db.execute("UPDATE invoices SET state='APPROVED' WHERE id=?", (invoice_id,))
        _event(db, invoice_id, "approved", by, f"{note or 'clean invoice'} | gross {_rupees(inv['amount_paise'])}, TDS {_rupees(tds)}, "
               f"GST retained {_rupees(retained)}, net {_rupees(net)}")


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
    with db:
        db.execute("BEGIN IMMEDIATE")
        inv = db.execute("SELECT state FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv or inv["state"] not in ("READY", "HELD", "BLOCKED", "APPROVED"):
            raise ValueError(f"invoice {invoice_id} cannot be rechecked")
        order = db.execute("SELECT idempotency_key FROM payment_orders WHERE invoice_id=?", (invoice_id,)).fetchone()
        if order and db.execute("SELECT 1 FROM provider_payments WHERE idempotency_key=?", (order[0],)).fetchone():
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
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def pay_approved(db, bank):
    """Pays only the frozen order, never the current master or the invoice text."""
    with _pay_lock(db):
        orders = db.execute("SELECT o.* FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id WHERE i.state='APPROVED' "
                            "ORDER BY COALESCE(i.due_date, '9999'), o.invoice_id").fetchall()
        for o in orders:
            try:
                ref = bank.pay(o["idempotency_key"], o["account"], o["ifsc"], o["net_paise"])
            except PaymentUnavailable as e:
                with db:
                    _event(db, o["invoice_id"], "payment_retry_needed", "chukta", str(e))
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
