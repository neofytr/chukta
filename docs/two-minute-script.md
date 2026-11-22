# The two-minute video script

Two people: **Asha** sits at the laptop and clicks. **Ravi** plays the CA who has to trust this thing. Swap in your own names. One person can read both parts.

Say it like you're showing a friend. Don't rush. Lines in **[brackets]** are what to do, not what to say.

## Before you press record

1. Start clean: `CHUKTA_PAY_DELAY=3 python3 app.py --reset`
2. Open http://127.0.0.1:8765 in Chrome, full screen, light theme.
3. Click **Vendors**, then **Imposter Radar**, then **Start the sweep**. Wait about a minute until it finishes. Note the number in the headline.
4. Click **Today**. You should see the request box.
5. Keep a second terminal open in the repo folder, with this already typed and not yet entered: `kill -9 "$(cat chukta.pid)"`

## The script

### 0:00 The problem

**[On the Today screen.]**

**Ravi:** Small businesses pay CA firms to do one scary job. Pay the vendors, and pay the right account.

**Asha:** One fake email can cost them lakhs. So we built Chukta. Here's the kind of request a client sends.

**[Click Run.]**

### 0:10 It does the work

**[Invoices appear one by one. Trim this wait in Loom if it feels long.]**

**Ravi:** What's it doing?

**Asha:** Twelve invoices, and one's a messy Hinglish email telling the AI to skip the checks. Chukta believes none of them. Every claim gets checked against records the sender can't touch.

### 0:28 The fraud

**[When it finishes, click Review 6. TCI Express opens. Point at the red digits.]**

**Ravi:** Why is this one blocked?

**Asha:** Polite email, real domain, new bank account. But these digits don't match our records, so it stops and says call a number we already have.

### 0:44 The duplicate

**[Click Moglix, "Already on the books".]**

**Ravi:** And this one?

**Asha:** Same invoice again, with the number written differently. We'd have paid it twice.

### 0:52 Sign, then crash it

**[Click Today. Click Review and sign. Type a name. Press and hold the round button until it turns green.]**

**Asha:** The clean ones need a human. I sign, and the payee and amount are frozen.

**Ravi:** Okay. Now kill it.

**[Within 5 seconds, go to the terminal and press Enter on the kill command. Then run `python3 app.py`, without --reset. Go back to Chrome.]**

**Asha:** Dead, mid-payment. And it picks up right where it stopped.

### 1:10 Proof

**[When the green seal lands, click Audit, then Receipts. Click Try a real code. Then click Try a forged code.]**

**Ravi:** Did anyone get paid twice?

**Asha:** No. Six invoices, six payment requests in Razorpay test mode. Each gets a receipt with a proof code. A real code passes. A forged one fails.

### 1:22 The thing nobody else built

**[Click Vendors, then Imposter Radar.]**

**Ravi:** But all of this happens after the fake invoice shows up.

**Asha:** So we go first. A fraudster has to register the fake domain, so Chukta hunts for lookalikes of our vendors on the live internet. Right now, **[read the number in the headline]** can send email. That's not proof of fraud, but if one bills us, it's blocked on its first invoice.

### 1:40 Can an auditor trust it?

**[Click Audit, then Replay. Click Change one rupee.]**

**Ravi:** Would an auditor trust these books?

**Asha:** I just changed one rupee in a copy. Watch. Caught, on the exact line.

### 1:52 Close

**[Stay on the screen.]**

**Ravi:** So what's Chukta?

**Asha:** A payables desk for CA firms. Every invoice checked, signed by a person, and issued exactly once.

**[Stop recording.]**

## If something goes wrong

- **Fumbled a line:** keep going, and trim it in Loom.
- **A take went wrong:** stop the app, wait a minute, and start again from step 1.
- **Over two minutes:** trim the invoice-reading wait and the wait after restart first.
- **Never say** that real money moved, that a vendor really received an email, or that a domain on the radar *is* a fraudster.
