"""Scores Chukta on a batch whose right answers were recorded before the run.

python3 eval.py         offline, recorded source answers, no credits
python3 eval.py --live  real Crustdata, IFSC registry and model calls
"""
import json
import sys
import time

from chukta.demo import AS_OF, BATCH, CLIENT, MESSY_READING, SAMPLE_STATEMENT, STATEMENT_EXPECTED, seed
from chukta.desk import SandboxBank, approve, connect, ingest, pay_approved, process
from chukta.reader import ReaderDown, logged_reader, read_invoice
from chukta.sources import Sources
from chukta.statement import import_statement, post_lines

KNOWN = {"moglix.com": "Moglix", "safexpress.com": "Safexpress Private Limited", "zoho.com": "Zoho", "tciexpress.in": "TCI Express Ltd.",
         "gati.com": "Allcargo Logistics", "swiggy.com": "Swiggy", "google.com": "Google"}


def recorded(method, url, headers, body, timeout=20):
    if "ifsc" in url:
        return 200, {}, b'{"BANK":"Recorded Bank","BRANCH":"Recorded Branch"}'
    ask = json.loads(body)
    if "names" in ask:
        same = [{"confidence_score": 1, "company_data": {"crustdata_company_id": n, "basic_info": {"name": "Sharma Traders", "primary_domain": None}}} for n in range(3)]
        return 200, {"x-credits-used": "0.2"}, json.dumps([{"matched_on": n, "match_type": "name", "matches": same} for n in ask["names"]]).encode()
    rows = [{"matched_on": d, "match_type": "domain", "matches": [{"confidence_score": 1, "company_data": {
        "crustdata_company_id": 1, "basic_info": {"name": KNOWN[d], "primary_domain": d}}}] if d in KNOWN else []}
        for d in json.loads(body)["domains"]]
    return 200, {"x-credits-used": str(0.2 * sum(bool(r["matches"]) for r in rows))}, json.dumps(rows).encode()


def recorded_read(text):
    def reply(_):
        if "bhaiya" in text:
            return MESSY_READING, {}
        raise ReaderDown("offline")
    return read_invoice(text, reply)


def main(live):
    db = connect(":memory:")
    seed(db)
    run_id = f"eval-{int(time.time())}"
    src = Sources(db, run_id, credit_limit=5.0, **({} if live else {"keys": ["offline"], "transport": recorded, "sleep": lambda s: None}))
    read = logged_reader(db, run_id) if live else recorded_read
    started = time.monotonic()
    ids = [ingest(db, CLIENT, text, read) for _, text, _, _ in BATCH]
    process(db, src, AS_OF)

    right = 0
    print(f"{'#':>2}  {'expected':8}  {'got':8}  case")
    for n, (i, (case, _, expected, _)) in enumerate(zip(ids, BATCH), 1):
        got = db.execute("SELECT state FROM invoices WHERE id=?", (i,)).fetchone()[0]
        right += got == expected
        print(f"{n:>2}  {expected:8}  {got:8}  {'' if got == expected else 'WRONG: '}{case}")
        if got != expected:
            for r in db.execute("SELECT check_name, status, detail FROM findings WHERE invoice_id=? AND status NOT IN ('pass','info')", (i,)):
                print(f"      {r[0]} [{r[1]}] {r[2]}")

    ready = [i for i in ids if db.execute("SELECT state FROM invoices WHERE id=?", (i,)).fetchone()[0] == "READY"]
    for i in ready:
        approve(db, i, "eval")
    pay_approved(db, SandboxBank(db))
    pay_approved(db, SandboxBank(db))
    paid = db.execute("SELECT COUNT(*) FROM provider_payments").fetchone()[0]
    wrong_paid = db.execute("SELECT COUNT(*) FROM provider_payments p JOIN payment_orders o ON o.idempotency_key=p.idempotency_key "
                            "JOIN vendors v ON v.client_id=o.client_id AND v.gstin=o.payee_gstin WHERE p.account!=v.account").fetchone()[0]
    import_statement(db, CLIENT, SAMPLE_STATEMENT)
    post_lines(db, src, CLIENT)
    lines = db.execute("SELECT status, payee, account, reason FROM bank_lines ORDER BY id").fetchall()
    lines_right = sum((l[0], l[1], l[2]) == want for l, want in zip(lines, STATEMENT_EXPECTED))
    print("\nHandbook bank-statement test case:")
    for l in lines:
        print(f"  {l[0]:7} {l[1] or '-'} / {l[2] or '-'}  ({l[3]})")
    credits, usd = db.execute("SELECT COALESCE(SUM(credits),0), COALESCE(SUM(usd),0) FROM ledger").fetchone()
    print(f"\nDecisions correct: {right}/{len(BATCH)}")
    print(f"Paid after sign-off, run twice: {paid} payments for {len(ready)} approved invoices. Paid to a wrong account: {wrong_paid}")
    print(f"Bank lines correct: {lines_right}/{len(STATEMENT_EXPECTED)}")
    print(f"Straight-through: {len(ready)}/{len(BATCH)}. Exceptions for a person: {len(BATCH) - len(ready)}")
    print(f"Cost: {credits:.2f} Crustdata credits, ${usd:.5f} of model calls, {time.monotonic() - started:.1f}s")
    return right == len(BATCH) and paid == len(ready) and not wrong_paid and lines_right == len(STATEMENT_EXPECTED)


if __name__ == "__main__":
    sys.exit(0 if main("--live" in sys.argv) else 1)
