---
name: payables-domain
description: Use when writing or reviewing Chukta logic or copy about Indian payables: GSTR-2B timing, MSME payment deadlines, TDS on vendor payments, duplicate and bank-change fraud, or what a CA firm's reviewer needs.
---

# Indian payables rules for Chukta

Checked on 22 Nov 2026. Anything marked **unconfirmed** must stay a flag for a person. Tax output is always a draft for the reviewer.

## GSTR-2B

- Generated on the **14th of the following month** for monthly filers. An October statement arrives on 14 November.
- Supplier cut-off for monthly GSTR-1 runs from the 12th of the month to the 11th of the next.
- Quarterly recipients get GSTR-2BQ on the 14th of the month after the quarter ends.
- The statement may not generate on the 14th if the recipient has not filed the previous GSTR-3B.
- It can be recomputed until the GSTR-3B is filed, so store which version was imported.

**Consequence:** absence from 2B proves something only if that invoice's period has closed. For an open period the result is "pending", never a failure.

Source: [GST FAQ on GSTR-2B](https://tutorial.gst.gov.in/userguide/returns/FAQ_gstr2b.htm), [IMS FAQ](https://tutorial.gst.gov.in/userguide/returns/FAQ_IMS_Dashboard.htm)

## MSME payment deadline

- Covers amounts owed to **micro or small** enterprises beyond the MSMED Act section 15 limit. Medium enterprises are outside the wording.
- Limit: 15 days with no written agreement, and the agreed period with one, capped at 45 days.
- Late payment moves the buyer's tax deduction to the year it is actually paid.
- The clause carries into the Income-tax Act, 2025. Its section number is **unconfirmed**, so cite "Section 43B(h) and its 2025 Act equivalent".
- Treatment of traders is **unconfirmed**. Show "needs review" for a trader.
- Vendor size comes from the Udyam details on the vendor master. If missing: "I can't verify MSME status".

Source: [Section 43B](https://wm.incometaxindia.gov.in/w/section-43b-42)

## TDS draft (Income-tax Act, 2025, section 393, from 1 April 2026)

| Payment | Table entry | Rate | No TDS if |
| - | - | - | - |
| Contractor | 6(i) | 1% individual or HUF, 2% others | single payment up to ₹30,000 and FY total up to ₹1,00,000 |
| Professional fees | 6(iii) | 10% | FY total up to ₹50,000 |
| Technical services | 6(iii) | 2% | FY total up to ₹50,000 |

- The ₹50,000 figure comes from an official FAQ. Its statute text is **unconfirmed**.
- Never guess the payment category. If the vendor master has none, hold TDS for a person.
- Use the new section references. Old numbers such as 194C can fail validation for payments after 1 April 2026.

Source: [Section 393](https://wm.incometaxindia.gov.in/w/section-393-6), [Official TDS FAQ](https://www.incometaxindia.gov.in/documents/d/guest/faqs-on-tax-deducted-source)

## Fraud controls

- Never take bank details from an invoice or email. Pay only the vendor master.
- Confirm a bank change on a known number, never one in the request.
- Keep vendor-master changes and payment release as separate approvals.
- A compromised real mailbox passes every domain check, so a bank change is a stop even from the right domain.
