# Chukta: the payables desk

ContextCon 05 build, theme 6.1 (Buying and paying). Takes a week's invoices and pays each one once, to the right account, holding anything unusual for a person with the reason. Plan: `docs/PLAN.md`.

## Hard rules from the handbook

- Code freeze is **6:00 PM IST, 22 Nov 2026**. Repo must be public, with history starting after 10:15 AM.
- Agents never contact real people outside the room. No real emails, calls or payments.
- Payments run only in a provider's test mode or the local sandbox.
- A person approves every payment, message and rejection.
- Every claim cites its source, field and retrieval date. If no record settles it, say "I can't verify" and name what is missing.
- A failed or slow source is never read as a pass. It holds the invoice.
- Each run has a time limit and a credit limit, and every call goes in the ledger.
- A crash at any point resumes without paying twice.

## Secrets

The keys live only in `.env` (gitignored, mode 600). Never print them, commit them, or put them in a tracked file. The two `CRUSTDATA_API_KEY_FALLBACK*` keys are spares: move to the next one after a 402 (credits exhausted). Do not rotate keys to get around a 429, because that evades Crustdata's rate limit. Batch instead. `docs/handbook/` and `docs/crustdata/` are also gitignored.

The LLM (`LLM_BASE_URL`, model `deepseek/deepseek-v4.1-flash`) is on a free key whose requests may be stored. Send it fictional invoices only, never real client data.

## Where things are

- `chukta/sources.py`: live data, with throttling, retries, cache and ledger
- `chukta/desk.py`: parsing, checks, decisions, approval, payment
- `test_chukta.py`: offline self-check. Run `python3 test_chukta.py` before saying anything works
- `docs/crustdata/pages/`: full local API docs. Index: `docs/crustdata/llms.txt`
- `docs/crustdata/account-endpoints.json`: this key's real limits and prices

## How to work

- Use the `crustdata` skill before any API call.
- The LLM never decides a payment. Decisions come from deterministic checks in `desk.py`.
- Log what was tried and what failed in `NOTES.md`. The judges ask for it.
- Python 3.12 stdlib only unless a dependency clearly earns its place.
