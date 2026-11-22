# Submission answers

## How does your product work?

**What it does today.** Chukta is an AI payables desk for CA firms. It takes a request in plain words and a week of invoices. A model reads each invoice, code verifies every field, and up to 15 checks compare its claims with records the sender doesn't control: the vendor master, purchase orders, GSTR-2B, the IFSC registry and Crustdata. Fixed policy marks each invoice Ready, Held or Blocked, and a read-only agent explains each exception with sources. After sign-off, each payment is issued exactly once in Razorpay test mode, even through a crash. Chukta then produces a run sheet, proof receipts, Tally vouchers and a line-by-line audit replay. It also posts bank statements, checks new vendors, prepares the month-end close, and runs Imposter Radar, which finds lookalikes of vendor domains on the live internet before their first email.

**Where it still needs a person.** Every payment sign-off, rejection and exception, each message to a client, and the month-end close. A bank-detail change takes two named people, and clearing a lookalike domain takes one.

**The approaches we considered.** (1) An agent that decides and pays: fast, but rewording could change a decision and a poisoned invoice could steer it. (2) Rules with no live data: repeatable, but a convincing impostor passes. (3) Models read and explain, code verifies, fixed policy decides. We chose the third, because the same case gets the same answer and no invoice text can move money.

**The models and tools we used.** DeepSeek V4.1 Flash; Crustdata Identify, Search and Enrich; Razorpay test mode; the IFSC registry; public DNS and RDAP; Python's standard library; SQLite.

**What we would build next.** RazorpayX payouts, OCR for scanned invoices, Tally sync, real logins and scheduled radar alerts. Each needs a real firm's bank mandate, documents, books or access rules, so we left them until a firm validates the workflow.
