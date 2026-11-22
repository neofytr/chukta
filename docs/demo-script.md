# Two-minute demo script

**Before recording:** in one terminal run `CHUKTA_PAY_DELAY=3 python3 app.py --reset`. Open http://127.0.0.1:8765 and enter a reviewer name. Keep a second terminal ready.

| Time | On screen | Say |
| - | - | - |
| 0:00 | The request | "CA firms are paid to run payables. Here is a client's real request, and Chukta does the job." |
| 0:08 | Click **Run this week's invoices** | "Twelve invoices, including a messy Hinglish email with a hidden instruction telling the AI to skip checks." |
| 0:25 | Queue fills | "Six are clean. Six need a person, and each has a reason." |
| 0:32 | Open **TCI Express, Blocked** | "This is the costliest fraud. The email comes from the vendor's real domain and asks to change bank details. Chukta never pays an account from an invoice. It blocks this and tells the reviewer to call a number already on file." |
| 0:52 | Scroll Evidence | "Every line cites its record and date: the IFSC registry, Crustdata, GSTR-2B, the PO." |
| 1:02 | Open **Gati, Held** | "When it can't verify something, it says so. Gati now resolves to Allcargo, so a person confirms it." |
| 1:12 | Click **Sign off 6 invoices**, then **Release 6 payments** | "A person signs, and the payee and amount are frozen." |
| 1:20 | Second terminal: `pkill -9 -f "python3 app.py"` | "Now I kill it in the middle of paying." |
| 1:26 | `python3 app.py`, refresh | "It restarts and carries on by itself." |
| 1:36 | Six issued, audit line | "Six invoices, six payments in Razorpay test mode. The audit replay confirms each one matches its sign-off." |
| 1:46 | Point to cost, open exports | "This batch cost one Crustdata credit and about a cent of model calls. The firm gets a bank file, Tally vouchers and an audit file." |
| 1:55 | Hold | "Chukta: each invoice, paid once." |

If the live run misbehaves, keep going with the recording. Say plainly that Payment Links are Razorpay's test-mode payment requests, and that settling to a vendor would use RazorpayX.
