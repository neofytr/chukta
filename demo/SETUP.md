# Set up Chukta

This takes about five minutes. Once it runs, read the [full guide](GUIDE.md).

## 1. What you need

- **Python 3.11 or newer.** Check with `python3 --version`.
- **Git and Chrome.**
- Nothing else. Chukta has no packages to install.

## 2. Get the code

```bash
git clone https://github.com/neofytr/chukta
cd chukta
```

If the repo is private, accept your GitHub invitation first.

**Windows (PowerShell):** use the same commands, and write `python` instead of `python3`. Windows support has not been tested on a real Windows machine. If it fails, use WSL or a teammate's laptop.

## 3. Check that it works

These two commands need no keys, network or credits.

```bash
python3 test_chukta.py
python3 eval.py
```

You should see:

```text
all checks passed
Decisions correct: 12/12
Bank lines correct: 4/4
```

## 4. Choose how to run it

| Mode | Keys needed | What you get |
| - | - | - |
| **Try the app** | None | The app runs on a local payment sandbox, but holds most invoices because it can't verify them |
| **Full demo** | Crustdata and model | The real story: 6 clean invoices, 6 exceptions |
| **Full demo with Razorpay** | Crustdata, model and Razorpay test keys | The same, with real test-mode payment requests |
| **With email receipts** | The above, plus mail settings | Receipts arrive in your own test inbox |

To skip keys, go to step 6.

## 5. Add your keys

```bash
cp .env.example .env
```

On Windows, use `copy .env.example .env`. Then open `.env` and fill in what you need.

| Line in `.env` | Where to get it | Needed? |
| - | - | - |
| `CRUSTDATA_API_KEY` | Your Crustdata dashboard. Each team member has their own 15,000 credits | For the full demo |
| `LLM_BASE_URL` | `https://api.goedelmachines.com/v1` | For the full demo |
| `LLM_API_KEY` | The Keys page on that site | For the full demo |
| `RAZORPAY_KEY_ID` | Razorpay dashboard, in **Test mode**, under API Keys. It must start with `rzp_test_` | Optional |
| `RAZORPAY_KEY_SECRET` | The same page | Optional |
| `SMTP_HOST`, `SMTP_PORT` | For Gmail: `smtp.gmail.com` and `587` | Optional |
| `SMTP_USER` | Your Gmail address | Optional |
| `SMTP_PASSWORD` | A Gmail [App Password](https://myaccount.google.com/apppasswords), not your normal password | Optional |
| `RECEIPT_TEST_INBOX` | The inbox that should receive the receipts | Optional |

**Keep keys safe.** `.env` is ignored by Git. Never commit it, show it on screen or paste it in a group chat.

**Without the model key**, the messy Hinglish email is held, so you see 5 clean invoices instead of 6. **Without Razorpay**, the app uses its local sandbox. Chukta refuses live Razorpay keys.

**Email has not been tested against a real mail server.** Send yourself one run before relying on it. Chukta only ever sends to `RECEIPT_TEST_INBOX`, never to a real vendor.

## 6. Start the app

```bash
python3 app.py --reset
```

Open **http://127.0.0.1:8765** in Chrome.

`--reset` deletes the local demo books and starts clean. To keep your current books, run `python3 app.py` without it.

## 7. Confirm it is live

On the **Today** screen, look at the pill in the top right:

- **Razorpay test mode** means your Razorpay keys work.
- **Local sandbox** means no Razorpay keys were found.

Click **Run**. A full run takes about 30 seconds and should end with **Ready to sign, ₹42,100.00**, with **6 Cleared, 4 Held, 2 Blocked**.

## Stop, restart and reset

| To do this | Run |
| - | - |
| Stop the app | Press `Ctrl+C` in its terminal |
| Stop it from another terminal | `kill "$(cat chukta.pid)"` |
| Restart and keep the books | `python3 app.py` |
| Restart clean | `python3 app.py --reset` |
| Slow payments for a crash demo | `CHUKTA_PAY_DELAY=3 python3 app.py --reset` |
| Crash it on purpose | `kill -9 "$(cat chukta.pid)"` |
| Use another port | `CHUKTA_PORT=8800 python3 app.py` |

On Windows PowerShell, set variables first, such as `$env:PYTHONUTF8=1; $env:CHUKTA_PAY_DELAY=3; python app.py --reset`. To crash it, run `taskkill /F /PID (Get-Content chukta.pid)`.

## If something goes wrong

| What you see | What to do |
| - | - |
| `Address already in use` | Another copy is running. Run `kill "$(cat chukta.pid)"` and start again |
| Almost every invoice is Held | The Crustdata key is missing or wrong. Check `.env` and restart |
| 5 clean invoices instead of 6 | The model key is missing or wrong |
| The pill says Local sandbox | Razorpay keys are missing, or are not test keys |
| "Razorpay asked us to slow down" | Normal. It retries by itself. Wait a minute between full runs |
| The hold button is grey | Type a reviewer name first |
| The page says Chukta is not responding | The app has stopped. Start it again without `--reset` |
| The old design still shows | Press `Ctrl+Shift+R` |
| Receipts say "In the outbox" | Mail settings are missing. Proof codes still work |
| A Python syntax error | Your Python is too old. Install 3.11 or newer |
