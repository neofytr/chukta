"""Measures Chukta's matching rules on real Indian companies from Crustdata.

Only aggregates are written to docs/benchmark.json. The raw corpus stays in data/, which is gitignored.
Run: python3 scripts/benchmark.py [companies_per_size_band]
"""
import json
import pathlib
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from chukta.desk import _brand_suffix, imitates, same_company  # noqa: E402
from chukta.sources import API, API_VERSION, http_call, load_keys  # noqa: E402

BANDS = ("2-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000")
FIELDS = ["basic_info.name", "basic_info.primary_domain", "basic_info.all_domains", "basic_info.employee_count_range", "basic_info.status",
          "basic_info.year_founded", "basic_info.company_type", "metadata.updated_at"]
GAP_S = 12.5  # This key allows 5 requests a minute per endpoint.
DATA = ROOT / "data" / "benchmark"
spent = 0.0


def call(path, body):
    global spent
    headers = {"authorization": f"Bearer {load_keys()[0]}", "x-api-version": API_VERSION, "content-type": "application/json", "user-agent": "chukta-benchmark"}
    for attempt in range(6):
        time.sleep(GAP_S)
        try:
            status, h, raw = http_call("POST", API + path, headers, json.dumps(body).encode(), timeout=45)
        except OSError as e:
            print("network", type(e).__name__, flush=True)
            continue
        if status == 200:
            spent += float(h.get("x-credits-used") or 0)
            return json.loads(raw)
        print("HTTP", status, raw[:160], flush=True)
        if status == 429:
            time.sleep(float(h.get("x-ratelimit-reset") or 15))
        elif status < 500:
            raise SystemExit(f"stopping on HTTP {status}")
    raise SystemExit("source stayed down")


def corpus(per_band):
    file = DATA / f"corpus_{per_band}.json"
    if file.exists():
        return json.loads(file.read_text())
    rows = []
    for band in BANDS:
        cursor, got = None, 0
        while got < per_band:
            body = {"filters": {"op": "and", "conditions": [{"field": "locations.country", "type": "=", "value": "India"},
                                                            {"field": "basic_info.employee_count_range", "type": "=", "value": band},
                                                            {"field": "basic_info.primary_domain", "type": "is_not_null"}]},
                    "limit": min(100, per_band - got), "fields": FIELDS}
            if cursor:
                body["cursor"] = cursor
            page = call("/company/search", body)
            items = page.get("companies") or []
            for c in items:
                b = c.get("basic_info") or {}
                if b.get("primary_domain") and b.get("name"):
                    rows.append({"id": c["crustdata_company_id"], "name": b["name"], "domain": b["primary_domain"].lower(), "all": [d.lower() for d in b.get("all_domains") or []],
                                 "band": band, "status": b.get("status"), "founded": b.get("year_founded"), "updated": (c.get("metadata") or {}).get("updated_at")})
            got += len(items)
            cursor = page.get("next_cursor")
            print(f"{band}: {got}", flush=True)
            if not cursor or not items:
                break
    DATA.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(rows))
    return rows


def attacks(domain, rng):
    brand, suffix = _brand_suffix(domain)
    out = {}
    swaps = {"o": "0", "l": "1", "i": "1", "e": "3", "s": "5"}
    if hit := next((c for c in brand if c in swaps), None):
        out["look-alike character"] = f"{brand.replace(hit, swaps[hit], 1)}.{suffix}"
    if len(brand) >= 5:
        i = rng.randrange(1, len(brand) - 1)
        out["missing letter"] = f"{brand[:i]}{brand[i + 1:]}.{suffix}"
        out["doubled letter"] = f"{brand[:i]}{brand[i]}{brand[i:]}.{suffix}"
        if brand[i] != brand[i + 1]:
            out["swapped letters"] = f"{brand[:i]}{brand[i + 1]}{brand[i]}{brand[i + 2:]}.{suffix}"
        out["inserted hyphen"] = f"{brand[:i]}-{brand[i:]}.{suffix}"
        out["wrong letter"] = f"{brand[:i]}{rng.choice([c for c in 'abcdefghijklmnopqrstuvwxyz' if c != brand[i]])}{brand[i + 1:]}.{suffix}"
    if "m" in brand:
        out["rn for m"] = f"{brand.replace('m', 'rn', 1)}.{suffix}"
    if suffix == "com":
        out["one-letter TLD change"] = f"{brand}.cam"
    if suffix == "in":
        out["one-letter TLD change"] = f"{brand}.io"
    out["other TLD"] = f"{brand}.{'net' if suffix != 'net' else 'org'}"
    return {k: v for k, v in out.items() if v != domain}


def main():
    per_band = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    rng = random.Random(22112026)
    rows = corpus(per_band)
    unique = list({r["domain"]: r for r in rows}.values())
    print("companies", len(rows), "unique domains", len(unique), flush=True)

    caught, total = Counter(), Counter()
    for r in unique:
        for kind, fake in attacks(r["domain"], rng).items():
            total[kind] += 1
            caught[kind] += imitates(fake, r["domain"])

    pairs, false_blocks, examples = 300_000, 0, []
    for _ in range(pairs):
        a, b = rng.sample(unique, 2)
        if a["id"] == b["id"] or a["domain"] in b["all"] or b["domain"] in a["all"]:
            continue
        if imitates(a["domain"], b["domain"]):
            false_blocks += 1
            if len(examples) < 12:
                examples.append([a["domain"], b["domain"]])

    variants, variant_ok, wrong_pairs, wrong_ok = 0, 0, 0, 0
    for r in unique:
        for suffix in (" Private Limited", " Pvt. Ltd.", " LIMITED", " (India) Pvt Ltd"):
            variants += 1
            variant_ok += same_company(r["name"] + suffix, r["name"])
    for _ in range(100_000):
        a, b = rng.sample(unique, 2)
        wrong_pairs += 1
        wrong_ok += same_company(a["name"], b["name"]) and a["id"] != b["id"]

    sample = rng.sample(unique, min(500, len(unique)))
    ambiguous, checked, by_band = 0, 0, {b: [0, 0] for b in BANDS}
    for i in range(0, len(sample), 25):
        chunk = sample[i:i + 25]
        names = list(dict.fromkeys(r["name"] for r in chunk))
        for row in call("/company/identify", {"names": names}):
            r = next((x for x in chunk if x["name"].lower() == str(row.get("matched_on", "")).lower()), None)
            if not r:
                continue
            same = {m["company_data"].get("crustdata_company_id") for m in row.get("matches") or []
                    if same_company(r["name"], m["company_data"]["basic_info"].get("name") or "")}
            checked += 1
            by_band[r["band"]][1] += 1
            if len(same) > 1:
                ambiguous += 1
                by_band[r["band"]][0] += 1
        print("names", min(i + 25, len(sample)), flush=True)

    now = datetime.now(timezone.utc)
    ages = sorted((now - datetime.fromisoformat(r["updated"].replace("Z", "+00:00"))).days for r in unique if r.get("updated"))
    result = {
        "measured_on": now.strftime("%Y-%m-%d"), "source": "Crustdata company search, Indian companies with a website, six size bands",
        "companies": len(unique), "credits_spent": round(spent, 2),
        "lookalike_attacks": {k: {"tested": total[k], "caught_pct": round(100 * caught[k] / total[k], 1)} for k in sorted(total)},
        "lookalike_attacks_overall_pct": round(100 * sum(caught.values()) / max(1, sum(total.values())), 2),
        "honest_domain_pairs_tested": pairs, "honest_pairs_wrongly_blocked": false_blocks, "honest_block_rate_pct": round(100 * false_blocks / pairs, 4), "wrong_block_examples": examples,
        "legal_suffix_variants_tested": variants, "legal_suffix_match_pct": round(100 * variant_ok / max(1, variants), 2),
        "different_company_pairs_tested": wrong_pairs, "different_companies_matched_by_name": wrong_ok,
        "names_checked": checked, "names_shared_by_2plus_companies_pct": round(100 * ambiguous / max(1, checked), 1),
        "shared_name_pct_by_size": {b: round(100 * v[0] / v[1], 1) if v[1] else None for b, v in by_band.items()},
        "status": dict(Counter(str(r.get("status")) for r in unique)),
        "record_age_days": {"median": ages[len(ages) // 2], "p90": ages[int(len(ages) * .9)], "max": ages[-1]} if ages else None,
    }
    (ROOT / "docs" / "benchmark.json").write_text(json.dumps(result, indent=1))
    print(json.dumps({k: v for k, v in result.items() if k != "wrong_block_examples"}, indent=1), flush=True)


if __name__ == "__main__":
    main()
