"""Live data sources: throttled, retried, cached, and written to the ledger."""
import http.client
import json
import pathlib
import re
import time
import urllib.error
import urllib.request

API = "https://api.crustdata.com"
IFSC_API = "https://ifsc.razorpay.com/"
API_VERSION = "2025-11-01"
# Real limits for this key, from GET /account/endpoints. Tune here if the plan changes.
RPM = {"/company/identify": 5, "ifsc": 60}
CACHE_TTL_S = 86400
MAX_WAIT_S = 60


class SourceDown(Exception):
    """A source gave no usable answer. Callers must hold, never treat this as a pass."""


def load_keys(path=pathlib.Path(__file__).parent.parent / ".env"):
    """Primary key first. Each spare is used only after the one before it returns 402."""
    env = dict(l.split("=", 1) for l in path.read_text().splitlines() if "=" in l)
    names = ("CRUSTDATA_API_KEY", "CRUSTDATA_API_KEY_FALLBACK", "CRUSTDATA_API_KEY_FALLBACK_2")
    return [env[k] for k in names if env.get(k)]


def http_call(method, url, headers, body, timeout=20):
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class Sources:
    def __init__(self, db, run_id, keys=None, credit_limit=10.0, time_limit_s=900,
                 transport=http_call, sleep=time.sleep):
        self.db, self.run_id, self.credit_limit = db, run_id, credit_limit
        self.keys = load_keys() if keys is None else list(keys)
        self.key_index = 0
        self.deadline = time.monotonic() + time_limit_s
        self.transport, self.sleep = transport, sleep
        self.last_call = {}

    def spent(self):
        row = self.db.execute("SELECT COALESCE(SUM(credits), 0) FROM ledger WHERE run_id=?",
                              (self.run_id,)).fetchone()
        return row[0]

    def _log(self, source, request, credits, outcome):
        with self.db:
            self.db.execute(
                "INSERT INTO ledger(run_id, source, request, credits, outcome, at) VALUES(?,?,?,?,?,?)",
                (self.run_id, source, request, credits, outcome,
                 time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))

    def _cached(self, key):
        row = self.db.execute("SELECT body, retrieved_at FROM source_cache WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[1] < CACHE_TTL_S:
            return json.loads(row[0])
        return None

    def _store(self, key, value):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO source_cache VALUES(?,?,?)",
                            (key, json.dumps(value), time.time()))

    def _throttle(self, label):
        gap = 60 / RPM.get(label, 10)
        wait = self.last_call.get(label, -gap) + gap - time.monotonic()
        if wait > 0:
            self.sleep(wait)
        self.last_call[label] = time.monotonic()

    def _request(self, source, label, url, payload=None, estimate=0.0, missing_ok=False):
        if time.monotonic() > self.deadline:
            raise SourceDown("run time limit reached")
        if self.spent() + estimate > self.credit_limit:
            raise SourceDown("run credit limit reached")
        if source == "crustdata" and not self.keys:
            raise SourceDown("no Crustdata key configured")
        body = json.dumps(payload).encode() if payload is not None else None
        last = "no response"
        for attempt in range(4):
            self._throttle(label)
            headers = {"user-agent": "chukta/0.1", "accept": "application/json"}
            if source == "crustdata":
                headers |= {"authorization": f"Bearer {self.keys[self.key_index]}",
                            "x-api-version": API_VERSION, "content-type": "application/json"}
            try:
                status, h, raw = self.transport("POST" if body else "GET", url, headers, body)
            except (OSError, http.client.HTTPException) as e:
                last = type(e).__name__
                self._log(source, label, 0, f"error:{last}")
                self.sleep(2 ** attempt)
                continue
            credits = _number(h.get("x-credits-used"))
            self._log(source, label, credits, str(status))
            if status == 200:
                try:
                    return json.loads(raw)
                except ValueError:
                    last = "unreadable response"
            elif status == 404 and missing_ok:
                return None
            elif status == 402 and source == "crustdata" and self.key_index + 1 < len(self.keys):
                self.key_index += 1
                last = "primary key out of credits"
                continue
            elif status == 429:
                last = "rate limited"
                self.sleep(min(_number(h.get("x-ratelimit-reset"), 2 ** attempt) + 1, MAX_WAIT_S))
                continue
            elif status < 500:
                raise SourceDown(f"{source} returned HTTP {status}")
            else:
                last = f"HTTP {status}"
            self.sleep(2 ** attempt)
        raise SourceDown(f"{source}: {last}")

    def ifsc(self, code):
        """Registry record, or {"record": None} if the registry says the code does not exist."""
        code = code.upper()
        if not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", code):
            return {"record": None, "retrieved_at": time.strftime("%Y-%m-%d")}
        key = f"ifsc:{code}"
        hit = self._cached(key)
        if hit:
            return hit
        record = self._request("ifsc", "ifsc", IFSC_API + code, missing_ok=True)
        if record is not None and not (isinstance(record, dict) and record.get("BANK")):
            raise SourceDown("IFSC registry returned an unexpected record")
        value = {"record": record and {"bank": record["BANK"], "branch": record.get("BRANCH")},
                 "retrieved_at": time.strftime("%Y-%m-%d")}
        self._store(key, value)
        return value

    def identify_many(self, domains):
        """Resolve domains to companies, up to 25 per call because identify is 5 RPM."""
        out, missing = {}, []
        for domain in dict.fromkeys(d.lower() for d in domains):
            hit = self._cached(f"identify:{domain}")
            if hit:
                out[domain] = hit
            else:
                missing.append(domain)
        for i in range(0, len(missing), 25):
            chunk = missing[i:i + 25]
            rows = self._request("crustdata", "/company/identify", API + "/company/identify",
                                 {"domains": chunk}, estimate=0.2 * len(chunk))
            try:
                by_domain = {r["matched_on"].lower(): r["matches"] for r in rows}
                for domain in chunk:
                    matches = by_domain[domain]
                    match = None
                    if matches:
                        info = matches[0]["company_data"]["basic_info"]
                        match = {"id": matches[0]["company_data"]["crustdata_company_id"],
                                 "name": info["name"], "domain": info.get("primary_domain"),
                                 "confidence": matches[0].get("confidence_score")}
                    out[domain] = {"match": match, "retrieved_at": time.strftime("%Y-%m-%d")}
                    self._store(f"identify:{domain}", out[domain])
            except (KeyError, TypeError, AttributeError, IndexError) as e:
                raise SourceDown(f"Crustdata identify returned an unexpected shape: {e}") from e
        return out

    def identify(self, domain):
        return self.identify_many([domain])[domain.lower()]
