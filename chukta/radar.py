"""Imposter Radar: finds lookalikes of a client's vendor domains that already exist, before a fraud email arrives.

It only asks public DNS and RDAP whether a name is registered. It never visits, contacts or scans those domains.
A lookalike is a reason to watch closely, never proof of fraud.
"""
import datetime as dt
import json
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

from .desk import imitates, now, same_company, today
from .sources import SourceDown, http_call

DOH = "https://cloudflare-dns.com/dns-query"
RDAP = "https://rdap.org/domain/"
GLYPHS = {"o": "0", "0": "o", "l": "1", "i": "1", "1": "l", "e": "3", "a": "4", "s": "5"}
OTHER_ENDINGS = ("com", "in", "co", "co.in", "net", "org", "cam", "biz", "info", "xyz")
RESERVED = ("test", "example", "invalid", "localhost")
PER_VENDOR = 26
NEW_DAYS = 365
SETTLED_DAYS = 3 * 365  # A name held this long was not registered for this week's fraud.


def lookalikes(domain, limit=PER_VENDOR):
    """The names an attacker would register, most convincing first."""
    label, _, ending = domain.partition(".")
    names = [label[:i] + GLYPHS[c] + label[i + 1:] for i, c in enumerate(label) if c in GLYPHS]
    names += [label[:i] + "rn" + label[i + 1:] for i, c in enumerate(label) if c == "m"]
    names += [label[:i] + label[i + 1] + label[i] + label[i + 2:] for i in range(1, len(label) - 1) if label[i] != label[i + 1]]
    names += [label[:i] + label[i + 1:] for i in range(1, len(label))]
    names += [label[:i] + label[i] + label[i:] for i in range(1, len(label))]
    names += [label[:i] + "-" + label[i:] for i in range(2, len(label) - 1)]
    found = [f"{n}.{ending}" for n in names if len(n) > 2 and imitates(f"{n}.{ending}", domain)]
    other = [f"{label}.{e}" for e in OTHER_ENDINGS if e != ending]
    mixed = []
    for a, b in zip(other, found):  # Another ending is the cheapest trick, so it is checked alongside typos.
        mixed += [a, b]
    mixed += found[len(other):] + other[len(found):]
    return [d for d in dict.fromkeys(mixed) if d != domain][:limit]


def _dns(name, kind, fetch):
    status, _, raw = fetch("GET", f"{DOH}?{urllib.parse.urlencode({'name': name, 'type': kind})}", {"accept": "application/dns-json", "user-agent": "chukta/0.1"}, None, 6)
    if status != 200:
        raise SourceDown(f"DNS returned {status}")
    return json.loads(raw)


def probe(name, fetch=http_call):
    """Registered, and able to receive or send mail? An error is 'unknown', never 'safe'."""
    try:
        got = _dns(name, "NS", fetch)
        if got.get("Status") == 3:
            return {"domain": name, "exists": False}
        if got.get("Status") != 0:
            return {"domain": name, "exists": None}
        mail = _dns(name, "MX", fetch)
        answers = [a["data"] for a in mail.get("Answer") or [] if a.get("type") == 15]
        usable = [a for a in answers if a.split()[-1].strip(".") != ""]  # A null MX means the domain refuses mail.
        address = _dns(name, "A", fetch)
        live = bool(got.get("Answer") or got.get("Authority") or address.get("Answer") or answers)
        servers = sorted(a["data"].lower().rstrip(".") for a in got.get("Answer") or [] if a.get("type") == 2)
        return {"domain": name, "exists": live, "mail": bool(usable), "ns": servers}
    except (SourceDown, OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return {"domain": name, "exists": None}


def registered_on(name, fetch=http_call):
    base = {"com": "https://rdap.verisign.com/com/v1/domain/", "net": "https://rdap.verisign.com/net/v1/domain/",
            "org": "https://rdap.publicinterestregistry.org/rdap/domain/"}.get(name.rsplit(".", 1)[-1], RDAP)  # Ask the registry itself where we can.
    try:
        for attempt in range(3):
            status, _, raw = fetch("GET", base + name, {"accept": "application/rdap+json", "user-agent": "chukta/0.1"}, None, 6)
            if status != 429:
                break
            time.sleep(1.2 * (attempt + 1))
        if status != 200:
            return None
        return next((e["eventDate"][:10] for e in json.loads(raw).get("events", []) if e.get("eventAction") == "registration"), None)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def grade(hit, vendor_name, company, owner=None):
    """Protects innocent businesses first. A name older than the vendor's own domain cannot have been registered to copy it."""
    if hit.get("older"):
        return "older"
    if hit.get("same_ns"):
        return "own"
    if company and (same_company(company, vendor_name) or (owner and same_company(company, owner))):
        return "own"
    if company:
        return "known"
    return "watch" if hit.get("mail") else "parked"


def sweep(db, src, client_id, on_progress=lambda text: None, fetch=http_call):
    vendors = [dict(v) for v in db.execute("SELECT name, domain FROM vendors WHERE client_id=? ORDER BY name", (client_id,)) if v["domain"].rsplit(".", 1)[-1] not in RESERVED]
    real = {v["domain"] for v in vendors}
    hits, checked, unknown = [], 0, 0
    with ThreadPoolExecutor(14) as pool:
        for vendor in vendors:
            on_progress(f"Scanning lookalikes of {vendor['domain']}")
            names = [n for n in lookalikes(vendor["domain"]) if n not in real]
            results = list(pool.map(lambda n: probe(n, fetch), names))
            checked += len(names)
            unknown += sum(r["exists"] is None for r in results)
            home = probe(vendor["domain"], fetch).get("ns") or []
            found = [r | {"vendor": vendor["name"], "real": vendor["domain"], "same_ns": bool(home) and r.get("ns") == home} for r in results if r["exists"]]  # Same name servers, same owner.
            hits += found
            with db:
                db.execute("INSERT INTO ledger(run_id, source, request, credits, outcome, at, usd) VALUES(?,?,?,?,?,?,?)",
                           (src.run_id, "dns", f"Lookalikes of {vendor['domain']} ({len(names)} names)", 0, f"{len(found)} registered", now(), 0))
        on_progress("Reading registration dates")
    with ThreadPoolExecutor(3) as slow:  # The registry service throttles bursts.
        real_born = dict(zip(real, slow.map(lambda d: registered_on(d, fetch), real)))
        settled = (dt.date.fromisoformat(today()) - dt.timedelta(days=SETTLED_DAYS)).isoformat()
        for hit, born in zip(hits, slow.map(lambda h: registered_on(h["domain"], fetch), hits)):
            hit["created"] = born
            hit["older"] = bool(born and (born < settled or (real_born.get(hit["real"]) and born < real_born[hit["real"]])))
    on_progress("Checking for honest businesses")
    companies, owners, verified = {}, {}, True
    suspects = [h["domain"] for h in hits if h.get("mail") and not h["older"] and not h["same_ns"]]  # Only these could become threats, so only these cost credits.
    try:
        for domain, got in src.identify_many(sorted(real)).items():
            owners[domain] = (got["match"] or {}).get("name")
        for i in range(0, len(suspects), 25):
            for domain, got in src.identify_many(suspects[i:i + 25]).items():
                companies[domain] = (got["match"] or {}).get("name")
    except SourceDown:
        verified = False  # Without the company record nothing may be called a threat, so it stays a plain watch item.
    stamp = now()
    cleared = {r[0] for r in db.execute("SELECT domain FROM radar_hits WHERE client_id=? AND level='cleared'", (client_id,))}  # A person's decision survives the next sweep.
    with db:
        db.execute("DELETE FROM radar_hits WHERE client_id=?", (client_id,))
        for h in hits:
            company = companies.get(h["domain"])
            level = grade(h, h["vendor"], company, owners.get(h["real"])) if verified else ("older" if h["older"] else "parked")
            level = "cleared" if h["domain"] in cleared else level
            db.execute("INSERT OR REPLACE INTO radar_hits VALUES(?,?,?,?,?,?,?,?,?)", (client_id, h["domain"], h["vendor"], h["real"], level, int(bool(h.get("mail"))), h.get("created"), company, stamp))
        db.execute("INSERT OR REPLACE INTO meta VALUES('radar', ?)", (json.dumps({"checked": checked, "unknown": unknown, "vendors": len(vendors), "at": stamp, "verified": verified}),))
    return radar_payload(db, client_id)


def radar_payload(db, client_id, as_of=None):
    as_of = dt.date.fromisoformat(as_of or today())
    meta = db.execute("SELECT value FROM meta WHERE key='radar'").fetchone()
    rows = [dict(r) for r in db.execute("SELECT domain, vendor, real, level, mail, created, company, checked_at FROM radar_hits WHERE client_id=?", (client_id,))]
    order = {"watch": 0, "parked": 1, "known": 2, "older": 3, "own": 4, "cleared": 5}
    for r in rows:
        r["mail"] = bool(r["mail"])
        r["age_days"] = (as_of - dt.date.fromisoformat(r["created"])).days if r["created"] else None
        r["fresh"] = r["age_days"] is not None and r["age_days"] <= NEW_DAYS
    rows.sort(key=lambda r: (order[r["level"]], not r["fresh"], r["age_days"] if r["age_days"] is not None else 99999, r["domain"]))
    count = lambda level: sum(r["level"] == level for r in rows)
    return {"swept": json.loads(meta[0]) if meta else None, "hits": rows, "watch": count("watch"), "parked": count("parked"), "known": count("known") + count("older"), "own": count("own") + count("cleared")}


def clear_domain(db, client_id, domain, by):
    """A person says this lookalike is legitimate, so its invoices are no longer blocked by the radar."""
    if not by.strip():
        raise ValueError("Enter the reviewer's name first")
    with db:
        if not db.execute("UPDATE radar_hits SET level='cleared', company=? WHERE client_id=? AND domain=?", (f"Cleared by {by.strip()}", client_id, domain)).rowcount:
            raise ValueError("That domain is not on the radar")


def _demo():
    assert "m0glix.com" in lookalikes("moglix.com", 60) and "moglix.cam" in lookalikes("moglix.com", 60) and "moglix.com" not in lookalikes("moglix.com", 60)
    assert grade({"mail": True}, "Moglix", None) == "watch" and grade({"mail": False}, "Moglix", None) == "parked"
    assert grade({"mail": True}, "Moglix", "Moglix") == "own" and grade({"mail": True}, "Moglix", "Mogul Foods") == "known", "an honest business is never an imposter"
    assert grade({"mail": True, "older": True}, "Moglix", None) == "older", "a domain older than the vendor cannot be copying it"
    assert grade({"mail": True}, "Gati", "Allcargo Logistics", "Allcargo Logistics") == "own"
    down = lambda *a: (_ for _ in ()).throw(TimeoutError())
    assert probe("x.com", down)["exists"] is None, "a failed lookup is unknown, never safe"


if __name__ == "__main__":
    _demo()
    print("radar ok", time.strftime("%T"))
