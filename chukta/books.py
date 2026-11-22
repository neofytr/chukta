"""Brings a client's books in: vendor master and purchase orders as CSV, GSTR-2B as the portal's JSON."""
import csv
import io
import json
import re

from .desk import _paise, add_po, add_vendor, gstin_valid, import_gstr2b, norm_po

VENDOR_COLUMNS = ("gstin", "name", "domain", "account", "ifsc")
TDS_CLASSES = ("goods", "contractor", "professional", "technical", "")
MSME_CLASSES = ("micro", "small", "medium", "trader", "none", "")


def _rows(text, needed):
    reader = csv.DictReader(io.StringIO(text.strip()))
    fields = [(f or "").strip().lower() for f in reader.fieldnames or []]
    missing = [c for c in needed if c not in fields]
    if missing:
        raise ValueError(f"The first line must name these columns: {', '.join(missing)}")
    reader.fieldnames = fields
    return [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]


def import_vendors(db, client_id, text):
    """All or nothing. An existing vendor's bank details can change only through the two-person flow."""
    clean = []
    for n, r in enumerate(_rows(text, VENDOR_COLUMNS), 2):
        gstin, ifsc = r["gstin"].upper(), r["ifsc"].upper()
        account = re.sub(r"\D", "", r["account"])
        domain = r["domain"].lower()
        if not gstin_valid(gstin):
            raise ValueError(f"Line {n}: GSTIN {gstin or 'is missing'} is not valid")
        if not r["name"] or not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", domain):
            raise ValueError(f"Line {n}: needs a vendor name and a website domain")
        if not 9 <= len(account) <= 18 or not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc):
            raise ValueError(f"Line {n}: bank account or IFSC is not valid")
        if r.get("tds_class", "").lower() not in TDS_CLASSES or r.get("msme", "").lower() not in MSME_CLASSES:
            raise ValueError(f"Line {n}: unknown TDS category or MSME class")
        old = db.execute("SELECT account, ifsc FROM vendors WHERE client_id=? AND gstin=?", (client_id, gstin)).fetchone()
        if old and (old["account"], old["ifsc"]) != (account, ifsc):
            raise ValueError(f"Line {n}: {r['name']} already has different bank details. Use the two-person bank change.")
        days = r.get("agreement_days", "")
        if days and not days.isdigit():
            raise ValueError(f"Line {n}: agreement_days must be a number")
        clean.append((gstin, r["name"], domain, account, ifsc, r.get("tds_class", "").lower() or None, r.get("msme", "").lower() or None, int(days) if days else None))
    if not clean:
        raise ValueError("Add at least one vendor")
    for gstin, name, domain, account, ifsc, tds, msme, days in clean:
        add_vendor(db, client_id, gstin, name, domain, account, ifsc, tds_class=tds, msme=msme, agreement_days=days)
    return len(clean)


def import_pos(db, client_id, text):
    clean = []
    for n, r in enumerate(_rows(text, ("po", "gstin", "amount")), 2):
        gstin = r["gstin"].upper()
        amount = _paise(r["amount"].replace("₹", ""))
        if not r["po"] or not amount or amount <= 0:
            raise ValueError(f"Line {n}: needs a PO number and a positive amount")
        if not db.execute("SELECT 1 FROM vendors WHERE client_id=? AND gstin=?", (client_id, gstin)).fetchone():
            raise ValueError(f"Line {n}: GSTIN {gstin} is not on the vendor master")
        clean.append((norm_po(r["po"]), gstin, amount))
    if not clean:
        raise ValueError("Add at least one purchase order")
    for po, gstin, amount in clean:
        add_po(db, client_id, po, gstin, amount)
    return len(clean)


def import_2b(db, client_id, text):
    try:
        doc = json.loads(text)
    except ValueError as e:
        raise ValueError("Paste the GSTR-2B JSON file from the GST portal") from e
    if not isinstance(doc, dict):
        raise ValueError("Paste the GSTR-2B JSON file from the GST portal")
    return import_gstr2b(db, client_id, doc)


def books_payload(db, client_id):
    vendors = [dict(r) for r in db.execute("SELECT name, gstin, domain, account, ifsc, tds_class, msme, onboarded_at FROM vendors WHERE client_id=? ORDER BY name", (client_id,))]
    for v in vendors:
        v["account"] = "****" + v["account"][-4:]
    return {"vendors": vendors, "pos": db.execute("SELECT COUNT(*) FROM pos WHERE client_id=?", (client_id,)).fetchone()[0],
            "periods": [r[0] for r in db.execute("SELECT period FROM gstr2b_imports WHERE client_id=? ORDER BY period", (client_id,))],
            "changes": [dict(r) for r in db.execute("SELECT id, invoice_id, proposed_by, approved_by, status FROM vendor_changes WHERE client_id=? ORDER BY id DESC LIMIT 8", (client_id,))]}
