# Build notes: what we tried, and what broke

All times are IST on 22 November 2026.

| Time | What we tried | What happened | What we changed |
| - | - | - | - |
| 10:19 | Handbook rate limits | This key allows 5 requests a minute on identify, not 30 | Batch 25 domains per call and cache by vendor |
| 10:25 | First live run | Fraud and duplicates were caught | Kept fixed policy over evidence |
| 10:30 | Coverage on 20 domains | All 16 established vendors matched, small and fake domains did not | No match means "I can't verify", never "fake" |
| 10:30 | Name matching | `gati.com` resolves to Allcargo Logistics | Person-confirmed aliases |
| 10:39 | GSTR-2B as proof for every invoice | It only arrives on the 14th of the next month | Open periods are "pending", closed-period gaps are credit at risk |
| 10:45 | Independent critic | Reproduced wrong amounts, a bank-change pass, approvals not bound to payments, PO overspend | Rebuilt the core with a regression test for each |
| 11:20 | Live batch | One `.test` domain made Crustdata reject the whole request | Drop only the invalid domain |
| 11:20 | Razorpay Orders with a receipt | **A retry created a second order** | Moved to Payment Links, where Razorpay rejects a repeated reference |
| 11:32 | Kill test on the real app | Account cap and rate limit failed payments, and the run still closed | Refusals go to a person, limits retry, and runs stay open until done |
| 11:38 | `kill -9` during payment, on Razorpay test mode | Six invoices, six payments | Passing |
| 11:39 | Real browser | Queue redraws swallowed clicks, and "Paid" overstated a payment link | Redraw only on change, and label it "Issued" |

## Approaches weighed

1. **An agent with tools decides and pays.** Quick, but rewording can change a decision and a poisoned invoice can steer it.
2. **Rules with no live data.** Repeatable, but a convincing impostor passes.
3. **Models read and explain, code verifies, fixed policy decides.** Chosen.

## Hardest case

A polite bank-change email from the vendor's **real** domain. Domain checks pass because the mailbox may be compromised. Chukta blocks it because payment can only go to the vendor master, and it gives the reviewer a callback script that uses the number already on file.
