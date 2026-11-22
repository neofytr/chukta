"""Posts bank statement lines to the right payee and account, or says it cannot verify them.

A payee name alone never identifies a business: live, "Sharma Traders" and even "Swiggy" each match several companies.
A line posts only through a payment Chukta issued, or a rule the firm keeps, confirmed against that company's domain.
"""
import hashlib
import re
from collections import Counter

from .desk import _date, _paise, _rupees, now, same_company, today
from .sources import SourceDown

DAY = r"\d{1,2}[ /-][A-Za-z]{3,9}[ /-]\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}"
LINE = re.compile(rf"^\s*(?P<day>{DAY})\s*[·|,\t]+\s*(?P<text>.+?)\s*[·|,\t]+\s*(?:₹|rs\.?|inr)?\s*(?P<amount>\d[\d,]*(?:\.\d{{1,2}})?)\s*$", re.I)
NOISE = {"UPI", "NEFT", "IMPS", "RTGS", "ACH", "POS", "ATM", "PAYTM", "RAZ", "RAZORPAY", "BANGALORE", "BENGALURU", "BLR", "MUMBAI", "DELHI",
         "CHENNAI", "PUNE", "HYDERABAD", "KOLKATA", "INDIA", "PAYMENT", "TXN", "REF"}
LEGAL = {"limited", "ltd", "private", "pvt", "llp", "inc", "india", "corporation", "corp", "co", "company", "the"}


def _norm(text):
    return " ".join(re.sub(r"[^A-Z0-9]+", " ", text.upper()).split())


def _name(narration):
    words = [w for w in _norm(narration).split() if w not in NOISE and not any(c.isdigit() for c in w)]
    return " ".join(words[:3])


def _words(name):
    return set(re.findall(r"[a-z0-9]+", re.sub(r"\(.*?\)", " ", name.lower()))) - LEGAL


def add_payee_rule(db, client_id, keyword, legal_name, domain, account):
    with db:
        db.execute("INSERT OR REPLACE INTO payee_rules VALUES(?,?,?,?,?)", (client_id, _norm(keyword), legal_name, domain.lower(), account))


def import_statement(db, client_id, text):
    """Safe to repeat. Two identical lines stay two lines, because that is what a duplicate charge looks like."""
    seen, added, unread = Counter(), 0, 0
    for raw in (l for l in text.splitlines() if l.strip()):
        m = LINE.match(raw)
        day = _date(m["day"]) if m else None
        amount = _paise(m["amount"]) if m else None
        narration = m["text"].strip() if m else raw.strip()[:200]
        identity = f"{day}|{_norm(narration)}|{amount}"
        seen[identity] += 1
        key = hashlib.sha256(f"{client_id}|{identity}|{seen[identity]}".encode()).hexdigest()
        readable = bool(day and amount)
        unread += not readable
        with db:
            added += db.execute("INSERT OR IGNORE INTO bank_lines(client_id, line_key, raw, txn_date, narration, amount_paise, status, reason, source, "
                                "retrieved_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (client_id, key, raw.strip()[:300], day, narration, amount, "NEW" if readable else "HELD",
                                 None if readable else "I can't verify this line: it has no readable date and amount.", "statement line", today())).rowcount
    return added, unread


def _hold(db, line, reason, source, at=None):
    with db:
        db.execute("UPDATE bank_lines SET status='HELD', reason=?, source=?, retrieved_at=? WHERE id=? AND status='NEW'", (reason, source, at or today(), line["id"]))


def _post(db, line, payee, account, reason, source, at=None):
    with db:
        db.execute("UPDATE bank_lines SET status='POSTED', payee=?, account=?, reason=?, source=?, retrieved_at=? WHERE id=? AND status='NEW'",
                   (payee, account, reason, source, at or today(), line["id"]))


def _issued_payment(db, line):
    words = set(_norm(line["narration"]).split())
    for o in db.execute("SELECT o.payee_name, o.net_paise, i.payment_ref FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id "
                        "WHERE o.client_id=? AND i.state='PAID' AND o.net_paise=?", (line["client_id"], line["amount_paise"])):
        brand = {w.upper() for w in _words(o["payee_name"])} - {"WORKS", "SERVICES", "TECHNOLOGIES", "ENTERPRISES", "TRADERS"}
        if brand and brand <= words:
            return o
    return None


def post_lines(db, src, client_id):
    new = db.execute("SELECT * FROM bank_lines WHERE client_id=? AND status='NEW' ORDER BY id", (client_id,)).fetchall()
    rules = db.execute("SELECT * FROM payee_rules WHERE client_id=?", (client_id,)).fetchall()
    rule_for = lambda line: next((r for r in rules if f" {r['keyword']} " in f" {_norm(line['narration'])} "), None)  # Whole words only.
    domains, names = {r["domain"] for l in new if (r := rule_for(l))}, {n for l in new if not rule_for(l) and (n := _name(l["narration"]))}
    for fetch, items in ((src.identify_many, sorted(domains)), (src.identify_names, sorted(names))):
        try:
            if items:
                fetch(items)
        except SourceDown:
            pass  # Each line below records the outage and is held.
    for line in new:
        twin = db.execute("SELECT id FROM bank_lines WHERE client_id=? AND id<? AND txn_date=? AND amount_paise=? AND status!='REJECTED' AND "
                          "UPPER(narration)=UPPER(?) ORDER BY id LIMIT 1", (client_id, line["id"], line["txn_date"], line["amount_paise"], line["narration"])).fetchone()
        if twin:
            _hold(db, line, f"Same payee, amount and date as line {twin['id']}. Possible duplicate charge.", f"bank_lines.id={twin['id']}")
            continue
        if re.search(r"\b(REFUND|REVERSAL|REVERSED|CHARGEBACK|RETURN)\b", _norm(line["narration"])):
            _hold(db, line, "This looks like a refund or reversal. A person should match it to the original entry.", "statement line")
            continue
        rule_now = rule_for(line)
        if rule_now:
            earlier = next((e for e in db.execute("SELECT id, narration FROM bank_lines WHERE client_id=? AND id<? AND txn_date=? AND amount_paise=? AND status!='REJECTED'",
                                                  (client_id, line["id"], line["txn_date"], line["amount_paise"])) if rule_for(e) and rule_for(e)["keyword"] == rule_now["keyword"]), None)
            if earlier:
                _hold(db, line, f"Same payee, amount and date as line {earlier['id']}. Possible duplicate charge.", f"bank_lines.id={earlier['id']}")
                continue
        paid = _issued_payment(db, line)
        if paid:
            _post(db, line, paid["payee_name"], "Accounts payable", f"Matches payment {paid['payment_ref']} issued by Chukta.", f"payment:{paid['payment_ref']}")
            continue
        rule = rule_for(line)
        if rule:
            try:
                got = src.identify(rule["domain"])
            except SourceDown as e:
                _hold(db, line, f"I can't verify the payee: {e}.", "crustdata:/company/identify")
                continue
            m = got["match"]
            if m and _words(m["name"]) and _words(m["name"]) <= _words(rule["legal_name"]):
                _post(db, line, rule["legal_name"], rule["account"], f"Firm's payee rule, and {rule['domain']} resolves to {m['name'].rstrip('.')}.",
                      f"crustdata:/company/identify#{m['id']}.basic_info.name", got["retrieved_at"])
            else:
                _hold(db, line, f"I can't verify the payee: the record for {rule['domain']} does not match {rule['legal_name']}.", f"payee_rules:{rule['keyword']}")
            continue
        name = _name(line["narration"])
        if not name:
            _hold(db, line, "I can't verify the payee: this line names no business.", "statement line")
            continue
        try:
            got = src.identify_names([name])[name]
        except SourceDown as e:
            _hold(db, line, f"I can't verify the payee: {e}.", "crustdata:/company/identify")
            continue
        same = sum(1 for m in got["matches"] if same_company(name, m["name"]))
        reason = (f"I can't verify the payee: {same} businesses trade as {name.title()}, and no record ties this payment to one of them." if same > 1 else
                  f"I can't verify the payee: nothing ties {name.title()} to a rule or vendor this client uses.")
        _hold(db, line, reason, f"crustdata:/company/identify?name={name}", got["retrieved_at"])


def resolve_line(db, line_id, by, payee, account, note):
    """A person settles a held line. Posting is reversible, and the audit trail keeps who decided."""
    if not all(str(v or "").strip() for v in (by, payee, account, note)):
        raise ValueError("Enter the payee, the account, a note and the reviewer's name")
    with db:
        changed = db.execute("UPDATE bank_lines SET status='POSTED', payee=?, account=?, resolved_by=?, reason=?, source='reviewer', retrieved_at=? "
                             "WHERE id=? AND status='HELD'", (payee.strip()[:120], account.strip()[:80], by.strip()[:80],
                                                              f"Posted by {by.strip()[:80]}: {note.strip()[:200]}", now()[:10], line_id))
        if not changed.rowcount:
            raise ValueError("Only a held line can be resolved")


def dismiss_line(db, line_id, by, note):
    if not str(by or "").strip() or not str(note or "").strip():
        raise ValueError("Enter a note and the reviewer's name")
    with db:
        changed = db.execute("UPDATE bank_lines SET status='REJECTED', resolved_by=?, reason=? WHERE id=? AND status='HELD'",
                             (by.strip()[:80], f"Dismissed by {by.strip()[:80]}: {note.strip()[:200]}", line_id))
        if not changed.rowcount:
            raise ValueError("Only a held line can be dismissed")


def statement_payload(db, client_id):
    rows = [dict(r) for r in db.execute("SELECT id, txn_date, narration, amount_paise, payee, account, status, reason, source, retrieved_at, resolved_by "
                                        "FROM bank_lines WHERE client_id=? ORDER BY id", (client_id,))]
    for r in rows:
        r["amount"] = _rupees(r.pop("amount_paise")) if r["amount_paise"] else "Unclear"
    return {"lines": rows, "posted": sum(r["status"] == "POSTED" for r in rows), "held": sum(r["status"] == "HELD" for r in rows), "at": now()}
