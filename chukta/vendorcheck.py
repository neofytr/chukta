"""Answers "is this new vendor real and trading?" from live company records, before anyone is paid."""
import csv
import io
import re
import time

from .books import import_vendors
from .desk import imitates, same_company, today
from .sources import SourceDown

DOMAIN = re.compile(r"[a-z0-9-]+(\.[a-z0-9-]+)+")
HEADLINES = {"REAL": "Real and trading", "LOOK": "A person should confirm this", "STOP": "Do not onboard yet"}


def clean_domain(text):
    text = re.sub(r"^[a-z]+://", "", str(text or "").strip().lower()).split("/")[0].split("?")[0]
    text = text[4:] if text.startswith("www.") else text
    if not DOMAIN.fullmatch(text):
        raise ValueError("Enter the vendor's website, like acmetools.in")
    return text


def check_vendor(db, src, client_id, name, domain):
    name, domain = str(name or "").strip()[:120], clean_domain(domain)
    if not name:
        raise ValueError("Enter the vendor's name")
    findings = []
    add = lambda check, status, detail, source: findings.append({"check": check, "status": status, "detail": detail, "source": source, "retrieved": today()})
    vendors = db.execute("SELECT name, domain FROM vendors WHERE client_id=?", (client_id,)).fetchall()
    twin = next((v for v in vendors if v["domain"] == domain), None)
    copied = next((v for v in vendors if v["domain"] != domain and imitates(domain, v["domain"])), None)
    if twin:
        add("master", "info", f"Already on the vendor master as {twin['name']}.", "vendors.domain")
    if copied:
        add("lookalike", "fail", f"{domain} imitates {copied['domain']}, the real domain of {copied['name']}.", "vendors.domain")
    else:
        add("lookalike", "pass", "It does not imitate any vendor on the master.", "vendors.domain")

    facts = None
    try:
        got = src.enrich(domain)
    except SourceDown as e:
        add("company", "unverified", f"I can't verify this company: {e}.", "crustdata:/company/enrich")
        got = {"match": None, "retrieved_at": today()}
    else:
        if not got["match"]:
            add("company", "unverified", f"I can't verify this company: no record exists for {domain}. Small honest businesses often have none, so ask for its GST certificate.", "crustdata:/company/enrich")
    if m := got["match"]:
        facts = m
        source = lambda field: f"crustdata:/company/enrich {field}"
        known = {domain, (m.get("domain") or "").lower(), *[d.lower() for d in m.get("all_domains") or []]}
        if same_company(name, m["name"]):
            add("name", "pass", f"The record for {domain} is named {m['name']}.", source("basic_info.name"))
        else:
            add("name", "unverified", f"You entered {name}, but the record for {domain} is named {m['name']}.", source("basic_info.name"))
        if domain not in known:
            add("domain", "unverified", f"The record's main domain is {m.get('domain')}, not {domain}.", source("basic_info.primary_domain"))
        status = (m.get("status") or "").lower()
        if status == "active":
            add("status", "pass", "The company record is active.", source("basic_info.status"))
        elif status:
            add("status", "fail", f"The company record says {status}.", source("basic_info.status"))
        else:
            add("status", "unverified", "I can't verify whether it is trading: the record has no status.", source("basic_info.status"))
        year = m.get("year_founded")
        if isinstance(year, int) and year >= int(time.strftime("%Y")) - 1:
            add("age", "unverified", f"Founded in {year}, so it has a short track record.", source("basic_info.year_founded"))
        elif isinstance(year, int):
            add("age", "pass", f"Founded in {year}.", source("basic_info.year_founded"))
        trend = m.get("trend") or []
        if m.get("employees") is None:
            add("people", "unverified", "I can't verify its size: the record has no headcount.", source("headcount.total"))
        elif len(trend) >= 13 and trend[-13] and trend[-1] <= trend[-13] * .6:
            add("people", "unverified", f"Headcount fell from {trend[-13]} to {trend[-1]} in about a year.", source("headcount.timeseries"))
        else:
            add("people", "pass", f"{m['employees']:,} people on record.", source("headcount.total"))
    verdict = "STOP" if any(f["status"] == "fail" for f in findings) else "LOOK" if any(f["status"] == "unverified" for f in findings) else "REAL"
    return {"name": name, "domain": domain, "verdict": verdict, "headline": HEADLINES[verdict], "facts": facts, "findings": findings,
            "on_master": bool(twin), "retrieved": got["retrieved_at"]}


def add_checked_vendor(db, client_id, name, domain, gstin, account, ifsc, tds_class):
    """Uses the import rules, so a new vendor cannot skip validation or change an existing vendor's bank details."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(("gstin", "name", "domain", "account", "ifsc", "tds_class"))
    writer.writerow((gstin, name, clean_domain(domain), account, ifsc, tds_class))
    return import_vendors(db, client_id, out.getvalue())
