# Two-minute demo script

**Before recording:** wait a minute after any earlier run, because Razorpay limits bursts. Stop any running copy, then run `CHUKTA_PAY_DELAY=3 python3 app.py --reset`. Open http://127.0.0.1:8765 at full screen. Keep a second terminal open in the repo folder. The run takes about 30 seconds, so trim that wait in Loom or talk over it.

| Time | On screen | Say |
| - | - | - |
| 0:00 | The request | "CA firms are paid to run payables. Here is a client's request, and Chukta does the job." |
| 0:06 | Click **Run**. Invoices arrive live | "Twelve invoices, including a messy Hinglish email with a hidden instruction telling the AI to skip checks. An invoice is never evidence for itself, so each claim is checked against a record the sender doesn't control." |
| 0:26 | Run ends. Click **Review 6** | "Six are clean. Six need a person. Here are three attempts to take this client's money." |
| 0:32 | **TCI Express** opens first. Point at the red digits | "One: a polite email from the vendor's real domain asks to change bank details. The digits differ from the account on file, so Chukta blocks it and tells the reviewer to call a number already in their records. A real change takes two people." |
| 0:50 | Click **Moglix, Already on the books** | "Two: the same invoice again, with its number reformatted. It would have been paid twice." |
| 0:58 | Open **Gati, Can't verify the company** | "Three is the honest case. Gati's domain now resolves to Allcargo. Chukta says it can't verify this and asks a person, without calling anyone a fraud." |
| 1:06 | **Today**, **Review and sign**, enter a name, **touch and hold** | "A person signs, and the payee and amount are frozen." |
| 1:14 | Second terminal: `kill -9 "$(cat chukta.pid)"` | "Now I kill it in the middle of paying." |
| 1:18 | `python3 app.py`, then refresh | "It restarts and carries on by itself." |
| 1:28 | The seal lands. **Open run sheet** | "Six invoices, six payment requests in Razorpay test mode, each issued once. This is the finished work: the run sheet, TDS by section, and what was left out and why." |
| 1:40 | **Break it**, **Run all attacks** | "Anyone can attack it. Duplicates, changed facts, a dead source, a crash, a second client. Nine of nine stopped." |
| 1:50 | **Ledger** | "This batch cost about one Crustdata credit and a cent of model calls." |
| 1:56 | Hold | "Chukta: every invoice signed by a person and issued once." |

If the live run misbehaves, keep recording. Say plainly that Payment Links are Razorpay's test-mode payment requests, and that settling to a vendor would use RazorpayX.
