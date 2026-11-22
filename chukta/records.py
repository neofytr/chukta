"""Opens the exact record behind a finding, with the field that supports it marked."""
import json
import re

from .desk import _mask, _rupees, number_key


def _row(label, value, hit=False):
    return {"label": label, "value": "Not recorded" if value in (None, "", []) else str(value), "hit": hit}


def mask_text(text):
    return re.sub(r"\b\d(?:[\s.-]*\d){8,17}\b", lambda m: "****" + re.sub(r"\D", "", m.group(0))[-4:], text)


def _passage(inv, pattern, title, source):
    text = mask_text(inv["raw"])
    lines = [l for l in text.splitlines() if l.strip()] or [text]
    hits = [l.strip() for l in lines if re.search(pattern, l, re.I)]
    return {"title": title, "kind": "passage", "source": source, "lines": [{"text": l.strip(), "hit": bool(re.search(pattern, l, re.I))} for l in lines[:24]],
            "found": bool(hits)}


def _vendor_rows(v, marks=()):
    return [_row("Legal name", v["name"], "name" in marks), _row("GSTIN", v["gstin"], "gstin" in marks), _row("Domain", v["domain"], "domain" in marks),
            _row("Bank account", _mask(v["account"]), "account" in marks), _row("IFSC", v["ifsc"], "account" in marks),
            _row("Onboarded", v["onboarded_at"]), _row("MSME class", v["msme"], "msme" in marks), _row("Payment terms (days)", v["agreement_days"], "msme" in marks),
            _row("TDS category", v["tds_class"], "tds" in marks), _row("Taxable paid this year before Chukta", _rupees(v["opening_taxable_paise"]), "tds" in marks)]


def _invoice_rows(r):
    f = json.loads(r["fields"])
    return [_row("Invoice", f"#{r['id']}", True), _row("Number", f.get("invoice_no"), True), _row("Date", r["invoice_date"]), _row("PO", r["po"]),
            _row("Amount", _rupees(r["amount_paise"]) if r["amount_paise"] else None), _row("Status", r["state"])]


def record(db, invoice_id, check):
    inv = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    finding = db.execute("SELECT * FROM findings WHERE invoice_id=? AND check_name=?", (invoice_id, check)).fetchone()
    if not inv or not finding:
        return None
    f = json.loads(inv["fields"])
    vendor = db.execute("SELECT * FROM vendors WHERE client_id=? AND gstin=?", (inv["client_id"], inv["gstin"])).fetchone()
    base = {"check": check, "status": finding["status"], "claim": finding["detail"], "source": finding["source"], "retrieved": finding["retrieved_at"], "url": None}

    if check in ("required", "document", "internal"):
        return base | _passage(inv, r"invoice no|inv #|bill no|invoice date|grand total|total|taxable|igst|cgst|sgst|gstin", "Invoice text", finding["source"])
    if check == "sender":
        return base | _passage(inv, r"^\s*(from|sender|reply-to|return-path)\b|from -", "Email header, as received", finding["source"])
    if check == "bank_request":
        return base | _passage(inv, r"\b(new|changed?|updated?|revised|different)\b.*\b(bank|account|a/c|ifsc)\b|\b(bank|account|a/c|ifsc)\b.*\b(changed?|updated?|revised)\b",
                               "The sentence in the invoice", finding["source"])
    if check == "gstin":
        return base | {"title": "GSTIN checksum", "kind": "fields", "rows": [_row("GSTIN on invoice", inv["gstin"], True),
                       _row("Result", "Check digit is valid" if finding["status"] == "pass" else "Check digit is wrong", True), _row("Method", "GST check-digit algorithm, computed locally")]}
    if check in ("vendor", "bank", "msme", "tds", "credit") and vendor:
        marks = {"vendor": ("name", "gstin"), "bank": ("account",), "msme": ("msme",), "tds": ("tds",), "credit": ()}[check]
        rows = _vendor_rows(vendor, marks)
        if check == "bank":
            rows = [_row("Account on invoice", ", ".join(_mask(a) for a in f["accounts"]) or "None", finding["status"] != "pass"),
                    _row("IFSC on invoice", ", ".join(f["ifscs"]) or "None", finding["status"] != "pass")] + rows
        if check == "tds" and inv["taxable_paise"]:
            rows.insert(0, _row("Taxable value on this invoice", _rupees(inv["taxable_paise"]), True))
        out = base | {"title": "Vendor master", "kind": "fields", "rows": rows}
        if check == "bank" and f["accounts"]:
            out["compare"] = [{"label": "Account", "invoice": _mask(f["accounts"][0]), "master": _mask(vendor["account"])},
                              {"label": "IFSC", "invoice": (f["ifscs"] or ["Not stated"])[0], "master": vendor["ifsc"]}]
        return out
    if check in ("duplicate", "near_duplicate"):
        m = re.search(r"invoices\.id=(\d+)", finding["source"])
        twin = db.execute("SELECT * FROM invoices WHERE id=?", (int(m.group(1)),)).fetchone() if m else None
        rows = _invoice_rows(twin) if twin else [_row("Earlier invoices", "None with this vendor, year and number", True)]
        return base | {"title": "Earlier invoice" if twin else "Invoice history", "kind": "fields", "rows": rows}
    if check == "po":
        po = db.execute("SELECT * FROM pos WHERE client_id=? AND po=?", (inv["client_id"], inv["po"])).fetchone()
        rows = [_row("PO", po["po"], True), _row("Issued to", vendor["name"] if vendor and po["gstin"] == vendor["gstin"] else po["gstin"]),
                _row("PO value", _rupees(po["amount_paise"]), True), _row("This invoice", _rupees(inv["amount_paise"]) if inv["amount_paise"] else None, True)] if po else [_row("PO on invoice", inv["po"], True), _row("Purchase order table", "No such PO", True)]
        return base | {"title": "Purchase order", "kind": "fields", "rows": rows}
    if check == "ifsc":
        code = vendor["ifsc"] if vendor else (f["ifscs"] or [None])[0]
        hit = db.execute("SELECT body FROM source_cache WHERE key=?", (f"ifsc:{code}",)).fetchone()
        rec = (json.loads(hit[0]).get("record") if hit else None) or {}
        return base | {"title": "IFSC registry", "kind": "fields", "url": f"https://ifsc.razorpay.com/{code}",
                       "rows": [_row("IFSC", code, True), _row("Bank", rec.get("bank"), True), _row("Branch", rec.get("branch"), True)]}
    if check == "company" and vendor:
        hit = db.execute("SELECT body FROM source_cache WHERE key=?", (f"identify:{vendor['domain']}",)).fetchone()
        match = (json.loads(hit[0]).get("match") if hit else None) or {}
        return base | {"title": "Crustdata company record", "kind": "fields",
                       "rows": [_row("Looked up", vendor["domain"]), _row("basic_info.name", match.get("name"), True), _row("Crustdata company ID", match.get("id")),
                                _row("Primary domain", match.get("domain")), _row("All domains", ", ".join(match.get("all_domains") or [])), _row("Match confidence", match.get("confidence")), _row("Status", match.get("status"), True), _row("Record last updated", (match.get("updated_at") or "")[:10]),
                                _row("Name on vendor master", vendor["name"], True), _row("Confirmed other names", ", ".join(json.loads(vendor["aliases"])))]}
    if check == "gst":
        key = number_key(f.get("invoice_no") or "")
        row = db.execute("SELECT * FROM gstr2b WHERE client_id=? AND gstin=? AND number_key=? ORDER BY period LIMIT 1", (inv["client_id"], inv["gstin"], key)).fetchone()
        if row:
            rows = [_row("Return period", row["period"], True), _row("Supplier GSTIN", row["gstin"]), _row("Invoice", row["number_key"].replace("|", "-"), True),
                    _row("Invoice date", row["invoice_date"]), _row("Value in GSTR-2B", _rupees(row["value_paise"]), True), _row("Value on invoice", _rupees(inv["amount_paise"]) if inv["amount_paise"] else None, True)]
        else:
            periods = [r[0] for r in db.execute("SELECT period FROM gstr2b_imports WHERE client_id=? ORDER BY period", (inv["client_id"],))]
            rows = [_row("Invoice period", (inv["invoice_date"] or "")[:7], True), _row("Statements imported", ", ".join(periods)),
                    _row("This invoice in GSTR-2B", "Not found", True), _row("GST at stake", _rupees(inv["tax_paise"]) if inv["tax_paise"] else None, True)]
        return base | {"title": "GSTR-2B", "kind": "fields", "rows": rows}
    return base | {"title": "Record", "kind": "fields", "rows": [_row("Source", finding["source"], True)]}
