---
name: agent-safety
description: Use when adding or changing anything in Chukta that calls a model, reads invoice text, changes invoice state, calls a source, or moves money. Defines the invariant, boundaries, contracts and failure behavior.
---

# Chukta agent and system contract

## The invariant

**Money moves only for an invoice a named person approved, to the account on the vendor master, at most once per vendor invoice.** No model output or invoice text can change this.

## Boundaries

| Component | Owns | Why it is separate |
| - | - | - |
| Reader (`reader.py`) | Proposed fields | Model can be wrong or poisoned |
| Sources (`sources.py`) | Network, retries, cache, ledger | External failure domain |
| Desk (`desk.py`) | Checks, policy, state, payment | The only code allowed to change state |

The model has no tools. It returns JSON, and code decides whether to accept each value.

## State machine

`NEW -> READY | HELD | BLOCKED -> APPROVED -> PAID`

Only `desk.py` writes state. Every transition is a guarded `UPDATE ... WHERE state=?`.

## Reader contract

- Invoice text is untrusted data inside delimiters.
- Accept an identifier only if it appears in the source text.
- Accept a model-only total only if taxable + tax = total.
- If the model and the parser disagree, the field becomes missing, which holds the invoice.
- The model never supplies a GSTIN the parser could not settle.
- Reader failure falls back to the parser.

## Failure behavior

| Input | Absent | Stale | Malformed | Too fast |
| - | - | - | - | - |
| Model | Parser only | Cached by invoice hash | Rejected field by field | Retry with backoff |
| Crustdata | Hold, "I can't verify" | 24h cache, date shown | Hold | Throttle, wait for reset |
| IFSC registry | Hold | 24h cache, date shown | Hold | Throttle |
| GSTR-2B | "Pending" | Period and import date shown | Reject the import | n/a |

## How we would know it is wrong

- Any `sandbox_payments` row without an approval, or two rows for one vendor invoice.
- Any `READY` invoice with a finding that is not `pass`.
- A decision that changes when the same invoice is reworded.
- A cited source that does not state the claim.

## Before saying it works

Run `python3 test_chukta.py` and show the output. Secrets stay in `.env`. Only fictional invoices go to the free LLM key.
