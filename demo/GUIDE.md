# The complete guide to Chukta

Everything about this app and this repo: what it is, how it works, how to test it, and how to answer the judges. To install it, start with [SETUP.md](SETUP.md).

## 1. What Chukta is

**Chukta is an AI payables desk for CA firms.** Chukta (चुकता) means "paid in full".

Small businesses pay CA firms to handle their vendor payments. Someone reads each invoice, matches it to a purchase order, checks the vendor and bank account, deducts TDS, pays it, and keeps books an auditor can follow. Mistakes are costly: duplicates get paid twice, and one polite fake email can redirect lakhs of rupees.

You give Chukta a request in plain words and a week of invoices. It does the work and only stops for a person when the answer changes the result.

**The one idea behind it: an invoice is never evidence for itself.** If an invoice says "pay this account", Chukta believes the vendor master. If it says "you ordered this", Chukta checks the PO. Each claim must agree with a record the sender does not control.

**The one promise it keeps:** money moves only for an invoice a named person approved, to the account on the vendor master, at most once. No model output or invoice text can change that.

## 2. How it works

```text
A request in plain words
        ↓
Route to the right job and store the inputs
        ↓
AI reads each invoice, and code verifies every field
        ↓
Up to 15 checks against independent records
        ↓
Fixed policy decides:  READY  |  HELD  |  BLOCKED
        ↓
AI investigator explains each exception, with sources
        ↓
A named person signs, freezing payee and amount
        ↓
Each payment issued exactly once, with a proof receipt
        ↓
Run sheet, bank file, Tally vouchers, audit replay, month-end close
```

**What the AI does:** it reads messy text and explains exceptions. **What the AI cannot do:** decide, approve or pay. Those are fixed code, so a poisoned invoice has nothing to steer.

### The invoice states

| State | Meaning |
| - | - |
| **Ready** | Every record agrees. Waiting for sign-off |
| **Held** | Something is unusual or can't be verified. A person decides |
| **Blocked** | A fraud or hard-stop signal. It can't be approved as it stands |
| **Signed** | A person approved it, and the payee and amount are frozen |
| **Issued** | The payment request went out, exactly once |
| **Rejected** | A person refused it, with a reason |

### The 15 checks

| Check | Question it answers |
| - | - |
| Invoice fields | Are the number, date, amount and GSTIN present? |
| Document | Is this really an invoice? |
| GSTIN | Is the GST number valid? |
| Vendor master | Is this vendor known to the client? |
| Duplicate | Has this invoice already been booked, even in another format? |
| Purchase order | Does the PO exist, belong to this vendor and have enough balance? |
| Bank details | Does the account match the vendor master? |
| Bank change request | Does the text ask to change bank details? |
| IFSC registry | Does this bank branch really exist? |
| GSTR-2B | Did the supplier actually file this invoice? |
| GST credit clock | When must credit be claimed or reversed? |
| Sender | Did it come from the vendor's real domain or a lookalike? |
| Company record | Does Crustdata's record match this vendor? |
| MSME deadline | Must this vendor be paid by a legal date? |
| TDS draft | How much tax should be deducted? |

Further stops cover a future or stale invoice date, an invoice billed to someone else, a missing e-invoice number, your own "don't pay X" instruction, and facts that changed after sign-off.

## 3. Test it yourself

Start clean with `CHUKTA_PAY_DELAY=3 python3 app.py --reset`, and open http://127.0.0.1:8765. These steps assume Crustdata, model and Razorpay test keys are set.

### Test 1: the main run

1. On **Today**, leave the sample request and click **Run**.
2. Watch the invoices arrive. It takes about 30 seconds.
3. **You should see:** Ready to sign, **₹42,100.00**, with 6 Cleared, 4 Held and 2 Blocked, and **₹15,340.00** stopped before paying.

| Invoice | Result | Why |
| - | - | - |
| Moglix MG-5521 | Ready | Clean goods invoice |
| Safexpress SX/26-27/1180 | Ready | Clean, with TDS |
| Zoho ZB-90312 | Ready | Current month, GSTR-2B not due yet |
| TCI TE-7734 | Ready | Clean courier invoice |
| Sharma SP-204 | Ready | MSME vendor, pay by 27 Nov |
| Mehta MC/26-27/0088 | Ready | Messy Hinglish email with a hidden instruction, which is ignored |
| Moglix mg/5521 | Held | The same invoice, reformatted |
| TCI TE-7801 | Blocked | Bank change from the vendor's real domain |
| Safexpress SX/26-27/1204 | Blocked | Bank change from a lookalike domain |
| Moglix MG-5602 | Held | Above the PO balance |
| Safexpress SX/26-27/1191 | Held | Missing from a filed GSTR-2B |
| Gati GL-3390 | Held | Domain now resolves to Allcargo, so it can't verify the name |

### Test 2: inspect the fraud

1. Click **Review 6**. TCI Express opens.
2. See the highlighted digits that differ from the account on file.
3. Click **Why this was flagged** to read the agent's reasoning.
4. Under **Evidence**, open **Bank details** to see the exact record, field and date.

### Test 3: approve and undo

1. Open **Safexpress, Missing from GSTR-2B**.
2. Click **Approve**, type a note, tick **Retain GST**, and submit.
3. Press **Undo** within 5 seconds, and the invoice returns. Approve it again if you want it in the run.

Keyboard shortcuts in Review: `J`/`K` move, `N` next exception, `A` approve, `R` reject, `C` recheck, `E` open evidence, `Z` undo, `?` help.

### Test 4: kill it mid-payment

1. On **Today**, click **Review and sign**, type your name, and **press and hold**.
2. Within 5 seconds, run `kill -9 "$(cat chukta.pid)"` in another terminal.
3. The page says Chukta is not responding.
4. Run `python3 app.py`, without `--reset`.
5. **You should see:** it resumes by itself and finishes with each payment issued once.

### Test 5: receipts

1. Go to **Audit, Receipts**.
2. Click **Try a real code**, and it shows Genuine.
3. Click **Try a forged code**, and it shows Not genuine.
4. Open any receipt to see what the vendor would get.

### Test 6: audit replay

1. Go to **Audit, Replay** and click **Play**. Every line is rechecked.
2. Click **Change one rupee**. It edits a private copy, and the replay stops on the exact line.
3. Click **Back to the real books**. The real books were never touched.

### Test 7: attack it

Go to **Audit, Break it** and click **Run all attacks**. **You should see 12 of 12 stopped.**

### Test 8: Imposter Radar

1. Go to **Vendors, Imposter Radar** and click **Start the sweep**. It takes about a minute.
2. See which lookalikes of your vendors are already registered.
3. Results come from the live internet, so numbers can change.

### Test 9: check a new vendor

Go to **Vendors, Check a vendor** and try the three buttons:

| Button | Expected result |
| - | - |
| Try a real one | Real and trading |
| Try a lookalike | Do not onboard yet |
| Try an unknown | A person should confirm this |

### Test 10: a bank statement

Go to **Close, Bank statement** and click **Use October sample**.

| Line | Result |
| - | - |
| Swiggy ₹1,240 | Posted to Swiggy Limited, staff meals |
| Google Cloud ₹18,500 | Posted to Google Cloud India, cloud hosting |
| Google Cloud ₹18,500, again | Held as a possible duplicate |
| UPI Sharma Traders ₹4,000 | Held: "I can't verify" |

### Test 11: close the month

Go to **Close**. You see what is stopping October, payables by age and TDS by section. It can't be signed until all six checks pass.

### Test 12: client update

Go to **Audit, Client brief** and switch between English and हिन्दी.

### Test 13: an invoice it has never seen

Start a new run with **+**, choose **Paste**, and paste this fictional invoice:

```text
From: Accounts <billing@moglix.cam>
Seller: Moglix
Supplier GSTIN: 09ZZZCM1111A1ZL
Invoice No: MG-7777
Invoice Date: 12 Nov 2026
PO Number: PO-2001
Taxable Value: 1,000.00
IGST 18%: 180.00
Grand Total: ₹1,180.00
Account No: 00001000000011
IFSC: HDFC0000001
Bill To: Kaveri Foods Private Limited (fictional)
GSTIN: 29ZZZCK0001K1Z5
```

**You should see it Blocked**, because `moglix.cam` imitates `moglix.com`. Everything else on the invoice looks right.

### Test 14: a two-person bank change

Do this on a fresh run, because it changes the vendor master.

1. Open **TCI Express, TE-7801**, click **Log the call**, and write a note.
2. Trying to approve under the same name fails.
3. Click the avatar at the bottom left and change the reviewer name.
4. Click **Approve change**. TE-7801 becomes Ready, and TCI's other open invoice, which names the old account, is now Blocked.

## 4. Every screen

| Screen | What it is for |
| - | - |
| **Today** | Give a request, watch the run, see money stopped and deadlines, and sign |
| **Review** | Work through exceptions with reasons and evidence |
| **Vendors, Check a vendor** | Prove a new vendor is real |
| **Vendors, Imposter Radar** | Find fake lookalike domains |
| **Vendors, The books** | Vendor master, and import of vendors, POs and GSTR-2B |
| **Close, Month end** | The close checklist, ageing, TDS and close pack |
| **Close, Bank statement** | Post statement lines to the right payee |
| **Audit, Run sheet** | The finished, printable payment run and downloads |
| **Audit, Replay** | Line-by-line replay of the books |
| **Audit, Receipts** | Receipts and proof-code verification |
| **Audit, Client brief** | An update for the client in English or Hindi |
| **Audit, Break it** | Twelve live attacks |
| **Audit, Ledger** | Every source call and what it cost |

The request box also understands plain words. "Post these bank statement lines", "Close October", "Check this new vendor" and "Any lookalike domains?" each go to the right job.

## 5. What is in this repo

| Path | What it does |
| - | - |
| `app.py` | Web server, API routes, background jobs and crash resume |
| `ui.html`, `static/` | The interface, theme, fonts and icons |
| `chukta/desk.py` | **The core:** parsing, checks, policy, approval and payment |
| `chukta/reader.py` | AI invoice reader, verified by code |
| `chukta/investigator.py` | Read-only AI that explains exceptions |
| `chukta/sources.py` | Crustdata and IFSC calls, with retries, cache, limits and ledger |
| `chukta/runs.py` | Understands the request, routes it, and stores inputs |
| `chukta/razorpay.py` | Razorpay test-mode payments. Refuses live keys |
| `chukta/radar.py` | Imposter Radar |
| `chukta/receipts.py` | Proof receipts and test-inbox email |
| `chukta/vendorcheck.py` | New vendor check |
| `chukta/close.py` | Month-end close |
| `chukta/brief.py` | English and Hindi client update |
| `chukta/statement.py` | Bank statement posting |
| `chukta/books.py` | Vendor, PO and GSTR-2B imports |
| `chukta/records.py` | Opens the exact record behind a finding |
| `chukta/exports.py` | Bank file, Tally vouchers, audit file and replay |
| `chukta/drills.py` | The twelve live attacks |
| `chukta/demo.py` | The fictional client, vendors and invoices |
| `test_chukta.py` | Offline regression checks |
| `eval.py` | Scores the labelled batch, offline or `--live` |
| `scripts/` | Theme generator and benchmark |
| `docs/architecture.md` | The diagram and failure table |
| `docs/requirements.md` | Each requirement mapped to its evidence |
| `docs/benchmark.json` | Results on 2,994 real companies |
| `docs/demo-script.md` | Recording and submission guide |
| `docs/two-minute-script.md` | The read-aloud video script |
| `NOTES.md` | What we tried and what broke, with times |

All state lives in one SQLite file, `chukta.db`, which is not committed. Keys live only in `.env`, also not committed.

## 6. Why it is safe

- **The AI has no authority.** It proposes and explains. Code decides.
- **Every irreversible step needs a person:** payment, rejection, a bank change (two people), a radar clearance, the month-end close and any message to a client.
- **A failed source is never a pass.** A timeout or garbled reply holds the invoice with "I can't verify".
- **Exactly once.** Each vendor invoice has one payment key, and Razorpay rejects a repeat. After a crash, Chukta resumes without paying twice.
- **Receipts are never sent twice.** If a crash leaves delivery unknown, the receipt is marked unclear for a person.
- **Each run has a ceiling:** 10 credits, $0.50 of model spend and 15 minutes.
- **Test mode only.** Live Razorpay keys are refused. Mail goes only to your test inbox.
- **Minimal personal data.** Bank accounts are masked on screen, and the investigator never sees raw invoice text.
- **Tamper-evident books.** Events are hash-chained, so an edit is detected on replay.

## 7. How it meets the judging criteria

| Criterion | Points | How Chukta meets it | Show this |
| - | - | - | - |
| End-to-end execution | 25 | A plain request becomes an issued, documented payment run. A person appears only when the answer changes the result | Tests 1, 4 |
| Facts and verification | 20 | Every finding cites its record, field and date. One company under two names stays one record. Unknowns say "I can't verify" | Tests 2, 9 |
| Robustness and edge cases | 20 | Messy text, missing fields, dead sources, nonsense replies, crashes and retries, with a person on anything irreversible | Tests 4, 7, 13 |
| Customer value and idea | 20 | A job firms are paid for. An invoice is never evidence for itself, and the radar finds fraud before it arrives | Tests 8, 11 |
| Demo and understanding | 15 | A clear story, and the answers below | The video |

## 8. What to tell the judges

**The service, who pays, and why we picked it.** Payables. Small businesses pay CA firms to run it. We picked it because one mistake is expensive, and the job has clear right answers an agent can prove.

**The business case.** The buyer is a CA firm serving many small clients. We propose ₹40 per invoice, a price still to test. Reported Indian costs for manual or outsourced processing run from about ₹60 to ₹250. A 12-invoice job uses 1.15 Crustdata credits and about ₹0.92 of model calls at an assumed ₹90 to the dollar. It earns ₹480, so it stays profitable unless a credit costs more than about ₹416.

**The approaches we looked at.** An agent that decides and pays was fast, but rewording could change a decision and a poisoned invoice could steer it. Rules without live data were repeatable, but a convincing impostor passes. We chose models that read and explain, code that verifies, and fixed policy that decides.

**What worked and what didn't.** Fixed policy gave the same answer however a request was worded. Razorpay Orders created a second order on retry, so we moved to Payment Links, which reject a repeated reference. Matching a payee by name failed because a third of sampled company names are shared. Our first radar flagged decades-old domains, so we added age, name-server and company checks.

**The hardest case.** A polite bank-change email from the vendor's real domain. Domain checks pass because the mailbox may be compromised. Chukta only pays the account on the vendor master, blocks the invoice, gives a callback script using a number on file, and needs two people for a real change.

**Who it could get wrong, and the guard.** An honest small vendor with no data record gets "I can't verify" and a person, never a fraud label. An innocent business with a similar domain is separated out by age, company and name-server checks, and a person can clear it.

**How we tested it.** 12 of 12 labelled decisions on live sources, a real `kill -9` during reading and during payment, twelve live attacks, and a benchmark on 2,994 real Indian companies. The 12 cases are ones we wrote, so they show behavior rather than real-world accuracy.

**What we left out.** Real payouts, real vendor email, OCR for scanned PDFs, logins and live GSTIN status.

**What's next, and why not now.** RazorpayX payouts need a firm's bank mandate. OCR needs a labelled set of real scans. Tally sync and logins need a real firm's books and access rules.

**If asked about scale.** Crustdata's rate limit comes first, so we batch 25 domains per call and cache by vendor. Cost grows with new vendors, not invoices. SQLite would move to Postgres with a job queue per firm.

**If asked about a second client.** All data is keyed by client, and a live drill shows one client can't use another's vendors or POs. The screen shows one client until real logins exist.

## 9. Honest limits

Say these plainly if asked:

- Payment Links are **test-mode payment requests**. No money moves.
- Reviewer names are typed, so the two-person rule **compares names and does not prove identity**.
- Email delivery **has not been tested against a real mail server**, and never goes to real vendors.
- A domain on the radar is **not proof of fraud**.
- TDS is a **draft** for a CA to confirm.
- The sample client and invoices are **fictional**. Vendor names are real companies used only as test data.
- Windows support **has not been tested**.

## 10. Submission answers to paste

**One line:** Chukta is a payables desk for CA firms: it checks each invoice against independent records, stops fraud before it arrives, and issues each signed payment exactly once.

**Theme:** 6.1, The Payables Desk.

**Diagram:** https://github.com/neofytr/chukta/blob/main/docs/architecture.md

**How does your product work?**

> Chukta takes a request in plain words and a week of invoices. A model reads each invoice, code verifies every field, and up to 15 checks compare its claims with records the sender doesn't control: the vendor master, POs, GSTR-2B, the IFSC registry and Crustdata. Fixed policy marks each invoice Ready, Held or Blocked, and a read-only agent explains each exception with sources. A named person signs, and each payment is issued exactly once in Razorpay test mode, even through a crash. It then produces a run sheet, proof receipts, Tally vouchers and a replayable audit file. Imposter Radar also finds lookalikes of vendor domains on the live internet before their first email.
>
> It still needs a person for every sign-off, rejection, exception, bank change and month-end close.
>
> We considered an agent that decides and pays, and rules with no live data. We chose models that read and explain, code that verifies, and fixed policy that decides, so a poisoned invoice can't steer a payment.
>
> Built with Python's standard library, SQLite, DeepSeek V4.1 Flash, Crustdata Identify, Search and Enrich, Razorpay test mode, the IFSC registry, and public DNS and RDAP.
>
> Next: RazorpayX payouts, OCR for scanned invoices, Tally sync and real logins, each of which needs a real firm's bank, documents or books.
