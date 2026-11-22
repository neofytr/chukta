# Recording the Chukta demo

Everything you need to run the demo, record the two-minute video and submit. **Code freeze is 6:00 PM IST. Aim to have the video uploaded by 5:30 PM.**

## 1. Pick a laptop

**Easiest: record on the laptop where Chukta already runs.** Its keys are already set up, so skip to step 3.

To use another laptop, you need Python 3.11 or newer, Git and Chrome. Then do step 2.

## 2. Set up another laptop

**Mac or Linux:**

```bash
git clone https://github.com/neofytr/chukta
cd chukta
cp .env.example .env
```

**Windows (PowerShell):**

```powershell
git clone https://github.com/neofytr/chukta
cd chukta
copy .env.example .env
```

Windows support is new and has not been tested on a real Windows machine. If it fails, use the laptop where it already runs.

Open `.env` and fill in these values:

| Line in `.env` | Where to get it |
| - | - |
| `CRUSTDATA_API_KEY` | Your Crustdata key from the event |
| `LLM_BASE_URL` | `https://api.goedelmachines.com/v1` |
| `LLM_API_KEY` | A key from the Keys page on that site |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | Razorpay dashboard, in **Test mode**, under API Keys. The ID must start with `rzp_test_` |

- **Never show `.env` on screen, and never paste keys into a group chat or commit them.**
- With no keys the app still runs, but it holds nearly every invoice, so the story below will not work. You need the Crustdata and model keys.
- With no Razorpay keys it uses a local sandbox. The demo still works, but say "local sandbox" instead of "Razorpay test mode".

## 3. Start it

Wait one minute after any earlier run, because Razorpay limits bursts. Stop any copy that is running, then start a clean one.

**Mac or Linux:**

```bash
kill "$(cat chukta.pid)" 2>/dev/null
CHUKTA_PAY_DELAY=3 python3 app.py --reset
```

**Windows (PowerShell):**

```powershell
$env:PYTHONUTF8=1; $env:CHUKTA_PAY_DELAY=3; python app.py --reset
```

Open **http://127.0.0.1:8765** in Chrome. Keep a **second terminal** open in the same folder. `CHUKTA_PAY_DELAY=3` slows payments so you have time to kill the app on camera.

## 4. Do one full rehearsal

Run the whole script below once before recording. Then repeat step 3 to reset. **Each take needs a fresh reset.**

## 5. Set up the recording

- Use [Loom](https://www.loom.com), screen and microphone, at 1080p if you can.
- Chrome full screen (F11), zoom 100%, light theme, no other tabs or bookmarks showing.
- Turn off notifications. Close anything showing keys, chats or personal details.
- Arrange it so you can switch to the terminal quickly. Alt+Tab is fine.
- Have one person drive and one person speak if you can.
- A run takes about 30 seconds. Talk over it, or trim the wait in Loom. **The final video must be two minutes or less.**

## 6. The script

| Time | Do this | Say this |
| - | - | - |
| 0:00 | Show the request on **Today** | "CA firms are paid to run payables. Here is a client's request, and Chukta does the job." |
| 0:06 | Click **Run**. Invoices arrive live | "Twelve invoices, including a messy Hinglish email with a hidden instruction telling the AI to skip checks. An invoice is never evidence for itself, so each claim is checked against a record the sender doesn't control." |
| 0:26 | When it finishes, click **Review 6** | "Six are clean. Six need a person. Here are three attempts to take this client's money." |
| 0:32 | **TCI Express** opens first. Point at the red digits | "One: a polite email from the vendor's real domain asks to change bank details. The digits differ from the account on file, so Chukta blocks it and tells the reviewer to call a number already in their records. A real change takes two people." |
| 0:50 | Click **Moglix, Already on the books** | "Two: the same invoice again, with its number reformatted. It would have been paid twice." |
| 0:58 | Click **Gati, Can't verify the company** | "Three is the honest case. Gati's domain now resolves to Allcargo. Chukta says it can't verify this and asks a person, without calling anyone a fraud." |
| 1:06 | **Today**, **Review and sign**, type a name, then **press and hold** the round button | "A person signs, and the payee and amount are frozen." |
| 1:14 | **Within 5 seconds**, in the second terminal: `kill -9 "$(cat chukta.pid)"` (Windows: `taskkill /F /PID (Get-Content chukta.pid)`) | "Now I kill it in the middle of paying." |
| 1:18 | Run `python3 app.py` (**without** `--reset`). Go back to Chrome | "It restarts and carries on by itself." |
| 1:28 | The seal lands. Click **Open run sheet** | "Six invoices, six payment requests in Razorpay test mode, each issued once. This is the finished work: the run sheet, TDS by section, and what was left out and why." |
| 1:40 | **Break it**, then **Run all attacks** | "Anyone can attack it. Duplicates, changed facts, a dead source, a crash, a second client. Nine of nine stopped." |
| 1:50 | **Ledger** | "This batch cost about one Crustdata credit and a cent of model calls." |
| 1:56 | Hold on the screen | "Chukta: every invoice signed by a person and issued once." |

## 7. If something goes wrong

| What you see | What to do |
| - | - |
| `Address already in use` | Run `kill "$(cat chukta.pid)"` and start again |
| Almost every invoice is Held | Keys are missing or wrong. Check `.env`, then redo step 3 |
| "Razorpay asked us to slow down" | Normal. It retries by itself. Wait, or trim it from the video |
| You restarted with `--reset` by mistake | The run is gone. Redo the take from step 3 |
| You killed it too late and all six were issued | Redo the take. Press kill sooner after signing |
| The page says Chukta is not responding | The app is stopped. Start it again without `--reset` |
| The hold button is greyed out | Type a reviewer name first |
| A live call fails during the take | Keep going and say what happened. Holding the invoice is the correct behaviour |

Do not claim money reached a vendor. Payment Links are Razorpay **test-mode payment requests**, and real payouts would use RazorpayX.

## 8. Upload and check

1. Trim the video to two minutes or less.
2. Set sharing to **anyone with the link**. Loom, unlisted YouTube or one Google Drive file all work. Do not share a folder.
3. **Open the link in a private window** to confirm it plays.

## 9. Submit by 6:00 PM

**One person submits for the whole team.** You can submit again, and the latest one counts. The form link is in the WhatsApp group.

| Field | What to enter |
| - | - |
| Team name | The same name every time |
| One line | Chukta is a payables desk for CA firms: it checks each invoice against independent records, holds anything unusual, and issues each signed payment exactly once. |
| Theme | 6.1, The Payables Desk |
| GitHub repo | https://github.com/neofytr/chukta |
| Demo video | Your one video link |
| How does your product work? | Summarise the README: what it does, where a person is needed, approaches tried, tools used, what comes next |
| Diagram | https://github.com/neofytr/chukta/blob/main/docs/architecture.md |
| Anything written before 10:15 AM? | Blank, unless your team prepared something before then |
| Every member | Name as registered, BITS email, YC email if different, student ID, personal email, GitHub username |

Before pressing submit, confirm the repo opens in a private window, the video plays there, the diagram link opens, and every name matches the registration form.

## 10. If you reach the finals

Finalists are announced at 7:30 PM and must be at the front by 7:40 PM with a charged laptop and the demo open. You get two minutes, then one minute of questions. Keep the video ready as a backup.

| If they ask | Answer |
| - | - |
| Who pays for this today? | Small and mid-size businesses pay CA firms and outsourced accountants to run payables |
| What would you charge? | A proposed ₹40 per invoice, a price we still need to test with firms |
| What does one job cost? | A 12-invoice run costs about 1.15 Crustdata credits and a cent of model calls |
| Why not let an agent decide? | Rewording could change a decision, and a poisoned invoice could steer it. Models read and explain, code verifies, and fixed policy decides |
| What was the hardest case? | A bank-change email from the vendor's real domain. Domain checks pass, so Chukta relies on the vendor master and a callback to a known number |
| Who could it get wrong? | An honest small vendor unknown to data sources. It gets "I can't verify" and a person, never a fraud label |
| How do you know it works? | 12 of 12 labelled decisions on live sources, a real `kill -9` test, nine live attacks, and a benchmark on 2,994 real Indian companies. The 12 cases are ones we wrote |
| A hundred times the volume? | Crustdata's rate limit comes first. We batch 25 domains per call and cache by vendor. SQLite would move to Postgres with a job queue |
| A second client? | All data is keyed by client, and a live drill proves one client can't use another's vendors. The screen shows one client until real logins exist |
| What did you leave out? | Real payouts through RazorpayX, OCR for scanned PDFs, logins, and live GSTIN status |
