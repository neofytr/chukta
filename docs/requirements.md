# Handbook requirements, checked one by one

Re-read against the ContextCon 05 Builder Handbook on 22 November 2026.

## What every service must do (Annexure D)

| Requirement | Status | Where to see it |
| - | - | - |
| At least one decision rests on live data | Met | Crustdata Identify and the IFSC registry decide the company and bank checks |
| Each claim links to its record, field and date | Met | Open any line under Evidence |
| "I can't verify" names what is missing | Met | Unknown vendors, held bank lines, source outages |
| A person approves what cannot be taken back | Met | Press-and-hold sign-off, named rejection, two named people for a bank change. Names are typed, with no login |
| Payments run in a provider's test mode | Met | Razorpay Payment Links. The app refuses live keys |
| Each run has a time limit and a credit limit | Met | Today, "This run's ceiling" |
| Every call is in a ledger, model calls included | Met | Ledger |
| Stop at any moment, resume, act exactly once | Met | `kill -9` test on the real app |
| A timeout holds the case, never reads as an answer | Met | Offline regression tests |

## A service, step by step

| Step | How Chukta handles it |
| - | - |
| Take the request | Reads the customer's words. A vague request gets the full job, and a request to skip checks is refused |
| Plan | Seven visible steps, with inputs stored before work starts |
| Gather the facts | Independent records, each with a source. A disagreement holds the invoice |
| Decide | Fixed policy, so rewording does not change the answer |
| Act, or hand over | One idempotent payment after sign-off. Exceptions go to a person |
| Show its work | Evidence, audit trail, replay and export files |

## Judging criteria

| Criterion | Points | Evidence |
| - | - | - |
| End-to-end execution | 25 | A request routes to one of five jobs and ends in finished work: a run sheet, receipts, a posted statement or a close pack. A person appears only when the answer changes the result |
| Facts and verification | 20 | Every finding opens its record, field and date. Aliases keep one company as one record. Unknowns say "I can't verify" |
| Robustness and edge cases | 20 | Twelve live attacks, real `kill -9` tests, masked accounts, and a person on anything irreversible |
| Customer value and idea | 20 | A job firms are paid for. An invoice is never evidence for itself, and Imposter Radar finds fake domains before they email |
| Demo and understanding | 15 | `demo/GUIDE.md`, `docs/two-minute-script.md`, `NOTES.md`, the README |

## Submission

| Item | Status |
| - | - |
| Public repo with history starting after 10:15 AM | First commit 10:29 AM. Confirm the repo is public before submitting |
| README | Done |
| Diagram link | `docs/architecture.md` |
| Notes on what was tried | `NOTES.md` |
| Two-minute video | **You record it** |
| Submission form with every member's details | **You submit it** |
| Price in rupees and cost of one job | ₹40 per invoice proposed. A 12-invoice job uses 1.15 credits and about ₹0.92 of model calls. It stays profitable unless a credit costs more than about ₹416 |
