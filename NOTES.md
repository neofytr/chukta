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
| 11:45 | Re-read the handbook line by line | No request intake, no visible plan, sources that did not open, no ledger view, no bank posting, and a crash could lose unread inputs | Built each one |
| 11:49 | Payee by company name | "Swiggy" and "Sharma Traders" each match several companies at top confidence | Post only through issued payments or firm rules confirmed by domain |
| 12:27 | Real payment run | Razorpay throttled the sixth payment for about a minute | Retries safely, and the screen says why it is waiting |
| 14:54 | Red-team review | A re-presented duplicate could pay twice, and a master or PO could change after signing | Fixed each, with a regression test |
| 14:54 | Benchmark on 2,994 real Indian companies | 33.2% of 500 sampled names were shared. After tuning, 99.8% of generated lookalikes were blocked and 14 of 300,000 honest pairs were wrongly blocked | Never identify a payee by name alone |
| 15:12 | Browser click-through of the rebuilt UI | Approving a held invoice did not prove which evidence the reviewer had seen | Approvals now carry the evidence hash and fail if it changed |
| 15:43 | Font audit | The font had no ₹ glyph, so every amount fell back to another typeface | Rebuilt the subset with ₹ and the rounded axis |
| 15:54 | Restarting the app | A second copy started with `--reset` deleted the running app's books before failing on the port | Bind the port first |
| 16:01 | Timed a full run from the ledger | About 115 seconds, nearly all waiting on one model call at a time | Four concurrent calls, with invoices still applied in order. About 30 seconds, same decisions |
| 16:05 | Judges name a duplicate, changed fact, failed call and restart | Showing them took a terminal and luck | Built nine live drills on a private copy of the books |

## Approaches weighed

1. **An agent with tools decides and pays.** Quick, but rewording can change a decision and a poisoned invoice can steer it.
2. **Rules with no live data.** Repeatable, but a convincing impostor passes.
3. **Models read and explain, code verifies, fixed policy decides.** Chosen.

## Hardest case

A polite bank-change email from the vendor's **real** domain. Domain checks pass because the mailbox may be compromised. Chukta blocks it because payment can only go to the vendor master, and it gives the reviewer a callback script that uses the number already on file.
