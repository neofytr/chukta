# Chukta

**Chukta (चुकता, "paid in full") is a payables desk for CA firms.** It takes a client's week of invoices, checks each one against records the sender does not control, drafts TDS, and prepares a payment run a reviewer can sign. Each approved invoice is issued once, even if the process is killed mid-payment.

ContextCon 05, BITS Pilani. Theme 6.1, The Payables Desk.

## The service

**Who does this today:** CA firms and outsourced accounting teams, paid by small and mid-size businesses to match invoices, verify vendors, deduct TDS and release payments.

**Why it matters:** duplicates and bank-detail fraud are the expensive failures. A [Pune company lost ₹10.45 lakh](https://the420.in/?p=87114) after a supplier's domain was changed from `.com` to `.cam`, and a [Vadodara business lost ₹19.75 lakh](https://the420.in/vadodara-businessman-duped-fake-supplier-email-fraud/) to a fake supplier email.

**The idea:** an invoice is never evidence for itself.

| What the invoice claims | Record that must agree |
| - | - |
| "This invoice was issued" | The client's GSTR-2B, for closed periods |
| "Pay this account" | The vendor master, never the invoice |
| "You ordered this" | The client's PO and its remaining balance |
| "This bank branch exists" | The live IFSC registry |
| "We are this company" | Crustdata's company record for the vendor's known domain |

## What it does now

1. Takes the request in the customer's words, plans the job and stores its inputs, so a crash loses nothing. Wording cannot switch off a control.
2. Reads messy invoices and emails. A model proposes fields, and code accepts each only if the source text supports it.
3. Runs 15 checks and decides **Ready**, **Held** or **Blocked** using fixed policy.
4. Catches reformatted duplicates, bank changes, lookalike domains, PO overspend, GST credit at risk and renamed vendors.
5. Drafts TDS under section 393 and orders payment by MSME deadline.
6. An investigator agent explains each exception using read-only tools. Code verifies its citations and numbers.
7. A named reviewer signs with a press-and-hold, which freezes the payee and amount.
8. Issues payment requests in Razorpay test mode, then produces a bank file, Tally vouchers and an audit file that checks each payment against its sign-off.
9. Posts bank statement lines to the right payee and account, holds duplicate charges, and says "I can't verify" when no record ties a payment to one business.
10. Opens the exact record behind every finding, with the supporting field marked and its retrieval date.

**Where it still needs a person:** every payment sign-off, every rejection and every exception. Changing a vendor's bank details takes two named people.

## Run it

Needs Python 3.12. There is nothing to install.

```bash
git clone https://github.com/neofytr/chukta && cd chukta
python3 test_chukta.py    # offline self-check
python3 eval.py           # labelled batch, offline
python3 app.py --reset    # http://127.0.0.1:8765
```

For live data, run `cp .env.example .env` and fill it in, then `python3 eval.py --live`. Without keys, Chukta still runs, uses a local sandbox, and holds what it cannot verify. Use fictional data only on a free model key.

To show a crash, start with `CHUKTA_PAY_DELAY=3 python3 app.py --reset`, release payments, run `kill -9 "$(cat chukta.pid)"`, then start `python3 app.py`.

## How it's built

The diagram, component boundaries and failure table are in [docs/architecture.md](docs/architecture.md). It uses Python's standard library, SQLite in WAL mode and one HTML page. Models: DeepSeek V4.1 Flash as reader and investigator, with no route to approval or payment.

## Sources and checks

| Source | Used for | Live? |
| - | - | - |
| Crustdata `/company/identify` | Vendor domain to company record | Yes |
| [Razorpay IFSC API](https://ifsc.razorpay.com/) | Bank branch exists | Yes |
| Razorpay Payment Links, test mode | One payment request per vendor invoice | Yes |
| GSTR-2B JSON | Supplier filed this invoice | Client file |
| Vendor master and POs | Payee, order and balance | Client records |

**Person approves:** every payment, rejection, held invoice and vendor alias.

**Ledger:** every Crustdata, IFSC and model call is recorded with its cost, and each run has a credit and time ceiling.

## How we know it works

| Test | Result |
| - | - |
| Labelled batch on live sources (`eval.py --live`) | 12 of 12 decisions correct |
| The handbook's bank-statement test case, using payee rules we seeded | 4 of 4 lines correct |
| Signed orders naming an account other than the vendor master | 0 |
| Lookalike domains generated from 2,994 real Indian company domains | 99.8% blocked. The same brand on another TLD is held instead |
| Honest domain pairs wrongly blocked | 14 of 300,000 |
| Sampled company names shared by two or more companies | 33.2% of 500, which is why a name alone never identifies a payee |
| `kill -9` during payment on the real app, Razorpay test mode | 6 invoices, 6 payments |
| Regression checks (`test_chukta.py`) | All pass, including each bug an independent critic reproduced |
| Prompt injection in an invoice | No effect on the decision |

The 12 cases are fictional and were written by us before the run, so they show the behavior but not real-world accuracy. The lookalike attacks are generated edits of real domains, not observed fraud. The full numbers are in [docs/benchmark.json](docs/benchmark.json). Build notes, including what failed, are in [NOTES.md](NOTES.md).

## Approaches we tried

| Approach | What worked | What did not | Verdict |
| - | - | - | - |
| An agent with tools decides and pays | Fast to build | Rewording can change a decision, and a poisoned invoice can steer it | Rejected |
| Rules with no live data | Repeatable | A convincing impostor passes | Rejected |
| Models read and explain, code verifies, fixed policy decides | Same decision however it is worded, with a source for each | Needs a vendor master and POs | **Chosen** |
| Razorpay Orders with a receipt | Simple | A live retry created a second order | Replaced by Payment Links, which reject a repeated reference |
| Payee from a company name | Easy lookup | "Sharma Traders" matched five businesses | Replaced by firm rules confirmed by domain |

**Hardest case:** a polite bank-change email from the vendor's real domain. Domain checks pass because the mailbox may be compromised. Chukta still blocks it, since it can only pay the account on the vendor master, and gives the reviewer a callback script that uses the number already on file.

The full build log is in [NOTES.md](NOTES.md), and each handbook requirement is mapped to its evidence in [docs/requirements.md](docs/requirements.md).

## Business case

- **Buyer:** a CA firm running payables for many SME clients.
- **Proposed price:** ₹40 per invoice, a hypothesis to test with firms. Indian benchmarks for manual or outsourced processing run from roughly [₹60 to ₹150](https://tallysolutions.com/accounting/the-roi-of-accounts-payable-automation-calculating-the-cost-of-a-manual-invoice/) up to [₹250](https://www.incorpx.io/accounts-payable-services), mostly from vendor sources.
- **Measured cost of a 12-invoice run:** 1.15 Crustdata credits and about $0.01 of model calls, or 0.096 credits and $0.00085 per invoice. Half went straight through, and six needed a reviewer. Company lookups are cached, so repeat vendors cost less.

## Who it could get wrong

- **An honest small vendor unknown to data sources.** It gets "I can't verify", never a fraud label. Established vendors are not held for this alone.
- **A vendor paid late because of a hold.** MSME deadlines are shown and paid first.
- **Personal data.** Accounts are masked on screen, and the investigator never sees raw invoice text.

## Left out, and why

- **Settlement to vendors.** Payment Links are Razorpay test-mode payment requests. Real vendor payouts need RazorpayX and a firm's approval.
- **Login.** Reviewer names are typed, so the two-person rule compares names and does not prove identity. A firm deployment needs real accounts.
- **OCR for scanned invoices.** Text and email came first.
- **Live GSTIN status.** We found no free official API and did not scrape the portal.
- **Binding tax advice.** TDS is a draft for the reviewer. Rates came from official Income Tax pages, but a CA must confirm each case.

## What comes next

RazorpayX payouts with webhook confirmation, OCR, direct Tally sync, and vendor callback tracking. These wait until a real firm validates the workflow, because each depends on that firm's bank and books.

## The future of this service

Once agents can do the whole job, a CA firm's payables work shifts from preparing entries to reviewing exceptions. The trust layer then becomes the product: evidence for each payment, and a record that survives an audit.
