"""Scores Chukta on a batch whose right answers were recorded before the run.

python3 eval.py         offline, recorded source answers, no credits
python3 eval.py --live  real Crustdata, IFSC registry and model calls
"""
import json
import sys
import time

from chukta.demo import AS_OF, BATCH, CLIENT, SAMPLE_STATEMENT, STATEMENT_EXPECTED, recorded, recorded_read, seed
from chukta.desk import SandboxBank, approve, connect, ingest, pay_approved, process
from chukta.reader import logged_reader
from chukta.sources import Sources
from chukta.statement import import_statement, post_lines

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
