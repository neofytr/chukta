"""A plain update the CA can forward to the business owner, in English or Hindi. Every number comes from the books."""
from .desk import _rupees

WORDS = {
    "en": {"title": "This week's payables update", "issued": "{n} payments issued, {net} in total.", "none": "No payments have been issued yet.", "ready": "{n} are checked and waiting for sign-off, {net} in total.",
           "tds": "TDS of {tds} was drafted on these payments.", "stopped": "We stopped {amount} from going out: {dup} in duplicates and {bank} to accounts we could not match.",
           "open": "Waiting on a decision", "ask": "What we need from you", "clear": "Nothing is waiting on you.", "note": "These are test-mode payment requests. No money has moved."},
    "hi": {"title": "इस हफ़्ते के भुगतान की जानकारी", "issued": "{n} भुगतान जारी हुए, कुल {net}।", "none": "अभी तक कोई भुगतान जारी नहीं हुआ है।", "ready": "{n} बिल जाँच चुके हैं और मंज़ूरी का इंतज़ार कर रहे हैं, कुल {net}।",
           "tds": "इन भुगतानों पर {tds} का TDS ड्राफ़्ट किया गया है।", "stopped": "हमने {amount} गलत भुगतान होने से रोके: {dup} दोहराए गए बिल और {bank} ऐसे खातों में जो हमारे रिकॉर्ड से मेल नहीं खाते।",
           "open": "इन पर फ़ैसला बाकी है", "ask": "आपसे क्या चाहिए", "clear": "अभी आपकी ओर से कुछ बाकी नहीं है।", "note": "ये टेस्ट-मोड भुगतान अनुरोध हैं। असली पैसा नहीं गया है।"},
}
ISSUES = {
    "bank": ("names a different bank account", "का बैंक खाता रिकॉर्ड से अलग है", "Confirm its bank details by phone, on a number you already have.", "अपने पास मौजूद नंबर पर फ़ोन करके बैंक विवरण पक्का करें।"),
    "sender": ("came from a lookalike email domain", "नकली जैसे ईमेल डोमेन से आया है", "Do not reply to that email. Call the vendor on a known number.", "उस ईमेल का जवाब न दें। जाने-पहचाने नंबर पर वेंडर को फ़ोन करें।"),
    "bank_request": ("asks to change bank details", "बैंक विवरण बदलने को कह रहा है", "Confirm the change by phone, on a number you already have.", "अपने पास मौजूद नंबर पर फ़ोन करके बदलाव पक्का करें।"),
    "duplicate": ("looks like a repeat of an earlier invoice", "पहले वाले बिल की दोबारा कॉपी लगता है", "Tell us if this is really a second bill.", "बताएँ कि क्या यह सच में दूसरा बिल है।"),
    "po": ("is above its purchase order balance", "PO की बची राशि से ज़्यादा है", "Approve a bigger PO, or tell us to reject the extra.", "बड़ा PO मंज़ूर करें या अतिरिक्त राशि अस्वीकार करने को कहें।"),
    "gst": ("is not in GSTR-2B yet", "अभी GSTR-2B में नहीं है", "Ask the supplier to file it, so the GST credit is safe.", "सप्लायर से इसे फ़ाइल करवाएँ, ताकि GST क्रेडिट सुरक्षित रहे।"),
    "company": ("has a company name we could not confirm", "का कंपनी नाम पक्का नहीं हो पाया", "Confirm this is the same company you deal with.", "पक्का करें कि यह वही कंपनी है जिससे आप काम करते हैं।"),
}
OTHER = ("needs a check", "की जाँच बाकी है", "Tell us how to treat this invoice.", "बताएँ कि इस बिल का क्या करना है।")


def client_brief(db, client_id, lang="en"):
    lang = "hi" if lang == "hi" else "en"
    w, at = WORDS[lang], 0 if lang == "en" else 1
    client = db.execute("SELECT name FROM clients WHERE id=?", (client_id,)).fetchone()[0]
    paid = db.execute("SELECT COUNT(*), COALESCE(SUM(o.net_paise),0), COALESCE(SUM(o.tds_paise),0) FROM payment_orders o JOIN invoices i ON i.id=o.invoice_id WHERE o.client_id=? AND i.state='PAID'", (client_id,)).fetchone()
    ready = db.execute("SELECT COUNT(*), COALESCE(SUM(amount_paise),0) FROM invoices WHERE client_id=? AND state IN ('READY','APPROVED')", (client_id,)).fetchone()
    lines = [w["issued"].format(n=paid[0], net=_rupees(paid[1])) if paid[0] else w["none"]]
    if ready[0]:
        lines.append(w["ready"].format(n=ready[0], net=_rupees(ready[1])))
    if paid[2]:
        lines.append(w["tds"].format(tds=_rupees(paid[2])))
    dup = bank = 0
    items, asks = [], []
    for inv in db.execute("SELECT i.id, i.amount_paise, v.name vendor FROM invoices i LEFT JOIN vendors v ON v.client_id=i.client_id AND v.gstin=i.gstin WHERE i.client_id=? AND i.state IN ('HELD','BLOCKED') ORDER BY i.state='BLOCKED' DESC, i.id", (client_id,)).fetchall():
        failing = [r[0] for r in db.execute("SELECT check_name FROM findings WHERE invoice_id=? AND status NOT IN ('pass','info') ORDER BY severity='block' DESC", (inv["id"],))]
        key = next((c for c in failing if c in ISSUES), None)
        if "duplicate" in failing:
            key, dup = "duplicate", dup + (inv["amount_paise"] or 0)
        elif any(c in failing for c in ("bank", "sender")):
            bank += inv["amount_paise"] or 0
        issue = ISSUES.get(key, OTHER)
        items.append({"vendor": inv["vendor"] or "Unknown vendor", "amount": _rupees(inv["amount_paise"]) if inv["amount_paise"] else "", "issue": issue[at], "ask": issue[2 + at]})
        if issue[2 + at] not in asks:
            asks.append(issue[2 + at])
    if dup or bank:
        lines.append(w["stopped"].format(amount=_rupees(dup + bank), dup=_rupees(dup), bank=_rupees(bank)))
    text = [w["title"], client, ""] + lines
    if items:
        text += ["", w["open"]] + [f"- {i['vendor']} {i['amount']}: {i['issue']}" for i in items] + ["", w["ask"]] + [f"- {a}" for a in asks]
    else:
        text += ["", w["clear"]]
    text += ["", w["note"]]
    return {"lang": lang, "title": w["title"], "client": client, "lines": lines, "open_title": w["open"], "items": items, "ask_title": w["ask"], "asks": asks, "clear": w["clear"], "note": w["note"], "text": "\n".join(text)}
