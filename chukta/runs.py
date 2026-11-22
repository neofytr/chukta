"""Takes a request in a customer's words, plans the job, and keeps its inputs safe through a crash."""
import json
import re
import time
import uuid

from .desk import now

CREDIT_LIMIT, TIME_LIMIT_S, MODEL_USD_LIMIT = 10.0, 900, 0.50  # Ceiling for each run.
ACTIVE_STAGES = ("reading", "checking", "investigating")
WANTS = (("Match each invoice to its PO", ("match", "purchase order", " po", "po ")),
         ("Check the vendor and bank account", ("vendor", "bank", "account", "verify", "check")),
         ("Draft TDS", ("tds", "tax")),
         ("Pay each invoice once", ("pay", "settle", "clear", "release")),
         ("Hold anything unusual with the reason", ("hold", "unusual", "exception", "flag", "approval")))
UNSAFE = ("skip", "without approval", "no approval", "without check", "don't check", "do not check", "dont check", "bypass", "ignore",
          "auto approve", "auto-approve", "no need to verify", "pay everything", "pay all")
SCOPE_WORDS = ("invoice", "bill", "payable", "payment", "vendor", "supplier", "pay ", "process", "handle", "these", "books")
CHECK_ONLY = ("check only", "only check", "just check", "dry run", "no payment", "without paying", "don't pay anything", "do not pay anything")
NO_PAY = re.compile(r"(?:do not|don't|dont|never)\s+pay\s+([a-z0-9&. -]+?)(?=\s*(?:[,;]|\.(?:\s|$)|\b(?:and|but|this|for|until|yet|today|now)\b|$))")
FINISHED = "A signed payment run, each invoice issued once, every exception explained, and an audit file that replays each decision."


def understand(request, invoice_count):
    """Fixed rules, so wording can never switch a control off."""
    text = f" {' '.join(request.lower().split())} "
    if not text.strip():
        raise ValueError("Tell Chukta what you need done")
    if not invoice_count:
        raise ValueError("Add at least one invoice")
    if not any(w in text for w in SCOPE_WORDS):
        raise ValueError("Chukta runs payables. Tell it what to do with these invoices.")
    check_only = any(w in text for w in CHECK_ONLY)
    no_pay = sorted({m.strip(" .") for m in NO_PAY.findall(text.strip()) if m.strip(" .") not in ("anything", "twice", "it", "them", "any", "all")})
    asked = [label for label, words in WANTS if any(w in text for w in words)]
    assumed = [label for label, _ in WANTS if label not in asked]
    notes = []
    if assumed:
        notes.append("Not mentioned, but always part of the job: " + ", ".join(a[0].lower() + a[1:] for a in assumed) + ".")
    if any(w in text for w in UNSAFE):
        notes.append("The request asks to relax a control. Every check and your sign-off stay on.")
    if check_only:
        notes.append("You asked for checks only. Nothing will be signed or issued in this run.")
    for name in no_pay:
        notes.append(f"You asked not to pay {name.title()}. Its invoices stay held.")
    return {"check_only": check_only, "no_pay": no_pay, "job": f"{'Check' if check_only else 'Run payables for'} {invoice_count if check_only else ''}".replace("  ", " ").strip() + (" invoices" if check_only else "") if check_only else f"Run payables for {invoice_count} invoice{'s' if invoice_count != 1 else ''}", "finished": FINISHED,
            "steps": [label for label, _ in WANTS], "notes": notes}


def route_request(text):
    """Sends a request in a customer's words to the right job. Fixed rules, so it cannot be talked out of a control."""
    t = f" {' '.join(str(text).lower().split())} "
    site = re.search(r"\b(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,})\b", t)
    if any(w in t for w in ("bank statement", "statement line", "bank line", "bank entries", "post these", "post the lines")):
        return {"job": "bank"}
    if re.search(r"\b(month[- ]end|monthly close|close (the |my |our )?(books|month)|close (of )?(january|february|march|april|may|june|july|august|september|october|november|december))\b", t):
        return {"job": "close"}
    if re.search(r"\b(new vendor|new supplier|onboard|is this vendor|vendor check|real,? trading|real business)\b", t) or (site and re.search(r"\b(vendor|supplier)\b", t) and "invoice" not in t):
        named = re.search(r"(?:vendor|supplier)[^:\n]*:\s*([^,\n]+?)\s*,", t)
        return {"job": "vendor", "domain": site.group(1) if site else "", "name": named.group(1).strip().title() if named else ""}
    return {"job": "pay"}


def create_run(db, client_id, request, texts):
    plan = understand(request, len(texts))
    run_id = f"run-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    with db:  # The inputs are stored first, so a crash while reading loses nothing.
        db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (run_id, client_id, request.strip(), json.dumps(plan), "reading", now(), None, CREDIT_LIMIT, TIME_LIMIT_S, MODEL_USD_LIMIT))
        db.executemany("INSERT INTO run_inputs VALUES(?,?,?,0)", [(run_id, n, t) for n, t in enumerate(texts)])
    return run_id


def apply_instructions(db, run):
    """Turns "do not pay X" into a hold that survives rechecks, and that no approval can pass."""
    plan = json.loads(run["understood"])
    with db:
        db.execute("DELETE FROM payment_holds WHERE client_id=?", (run["client_id"],))
        for name in plan.get("no_pay", []):
            words = set(re.findall(r"[a-z0-9]+", name))
            for v in db.execute("SELECT gstin, name FROM vendors WHERE client_id=?", (run["client_id"],)).fetchall():
                if words and words <= set(re.findall(r"[a-z0-9]+", v["name"].lower())):
                    db.execute("INSERT OR REPLACE INTO payment_holds VALUES(?,?,?)", (run["client_id"], v["gstin"], f"The client's request says not to pay {v['name']}."))


def payment_allowed(db):
    run = latest_run(db)
    return not (run and json.loads(run["understood"]).get("check_only"))


def set_stage(db, run_id, stage):
    with db:
        db.execute("UPDATE runs SET stage=?, finished_at=CASE WHEN ?='done' THEN ? ELSE finished_at END WHERE id=?", (stage, stage, now(), run_id))


def latest_run(db):
    return db.execute("SELECT * FROM runs ORDER BY started_at DESC, rowid DESC LIMIT 1").fetchone()


def interrupted_runs(db):
    marks = ",".join("?" * len(ACTIVE_STAGES))
    return [r[0] for r in db.execute(f"SELECT id FROM runs WHERE stage IN ({marks}) ORDER BY started_at", ACTIVE_STAGES)]


def model_spend(db, run_id):
    return db.execute("SELECT COALESCE(SUM(usd), 0) FROM ledger WHERE run_id=?", (run_id,)).fetchone()[0]


def close_finished_runs(db):
    """A run is done once nothing in the books still waits on a person or a payment."""
    waiting = db.execute("SELECT COUNT(*) FROM invoices WHERE state IN ('NEW','READY','HELD','BLOCKED','APPROVED')").fetchone()[0]
    for row in db.execute("SELECT id FROM runs WHERE stage IN ('review','paying')").fetchall():
        set_stage(db, row[0], "done" if not waiting else "review")
