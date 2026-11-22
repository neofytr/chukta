# Two-minute demo script

**Before recording:** wait a minute after any earlier run, because Razorpay limits bursts. In one terminal run `CHUKTA_PAY_DELAY=3 python3 app.py --reset`. Open http://127.0.0.1:8765. Keep a second terminal open in the repo folder.

| Time | On screen | Say |
| - | - | - |
| 0:00 | The request | "CA firms are paid to run payables. Here is a client's request, and Chukta does the job." |
| 0:08 | Click **Start the job** | "Twelve invoices, including a messy Hinglish email with a hidden instruction telling the AI to skip checks." |
| 0:25 | The plan completes. Click **Review 6** | "Six are clean. Six need a person. Here are three attempts to take this client's money." |
| 0:32 | **TCI Express, Blocked**, then open **Bank details** | "One: a polite email from the vendor's real domain asks to change bank details. The digits differ from the vendor master, so Chukta blocks it and tells the reviewer to call a number already on file. A real change takes two people." |
| 0:52 | **Moglix, Held**, the duplicate | "Two: the same invoice again, with its number reformatted. It would have been paid twice." |
| 1:02 | **Gati, Held** | "Three is the honest case. Gati's domain now resolves to Allcargo. Chukta says it can't verify this and asks a person, without calling anyone a fraud." |
| 1:12 | **Today**, **Review and sign**, enter a name, **press and hold** | "A person signs, and the payee and amount are frozen." |
| 1:20 | Second terminal: `kill -9 "$(cat chukta.pid)"` | "Now I kill it in the middle of paying." |
| 1:26 | `python3 app.py`, then refresh | "It restarts and carries on by itself." |
| 1:36 | Open **Audit**, click **Replay** | "Six invoices, six payment requests in Razorpay test mode. Each one matches its sign-off." |
| 1:46 | Open **Ledger**, then the exports | "This batch cost about one Crustdata credit and a cent of model calls. The firm gets a bank file, Tally vouchers and an audit file." |
| 1:55 | Hold | "Chukta: every invoice signed by a person and issued once." |

If the live run misbehaves, keep recording. Say plainly that Payment Links are Razorpay's test-mode payment requests, and that settling to a vendor would use RazorpayX.
