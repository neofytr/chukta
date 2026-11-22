"use strict";
/* Chukta reviewer app. Plain DOM, one polling loop, and every value rendered as text. */

const SYM = {"home":59530,"inbox":57686,"account_balance":59471,"menu_book":59929,"verified_user":59624,"receipt_long":61294,"add":57669,"palette":58295,"dark_mode":58652,"light_mode":58648,"check":58826,"close":57676,"chevron_right":58377,"arrow_back":58820,"arrow_forward":58824,"warning":57346,"info":59534,"schedule":57746,"call":57520,"description":59507,"link":57687,"download":57713,"sync":58919,"play_arrow":57399,"lock":59533,"person":59389,"apartment":59968,"percent":60248,"mail":57534,"content_copy":57677,"shopping_cart":58695,"tag":59887,"currency_rupee":60151,"content_paste":57679,"history":57998,"edit_note":59205,"keyboard":58130,"wifi_off":58952,"gpp_bad":61458,"gpp_maybe":61460,"verified":57393,"print":58709,"upload_file":59900,"task_alt":58086,"payments":61283,"draw":59206,"expand_more":58831,"search":59574,"attach_file":57894,"assignment_turned_in":59490,"cancel":58825,"error":57344,"fact_check":61637};
const ICONS = { today: "home", inbox: "inbox", bank: "account_balance", receipt: "receipt_long", shield: "verified_user", shieldx: "gpp_bad", plus: "add", palette: "palette", moon: "dark_mode", sun: "light_mode",
  check: "check", x: "close", chevron: "chevron_right", back: "arrow_back", arrow: "arrow_forward", warn: "warning", info: "info", clock: "schedule", phone: "call", doc: "description", link: "link", download: "download",
  refresh: "sync", play: "play_arrow", lock: "lock", user: "person", building: "apartment", percent: "percent", mail: "mail", copy: "content_copy", cart: "shopping_cart", hash: "tag", agent: "search", rupee: "currency_rupee",
  paste: "content_paste", history: "history", books: "menu_book", note: "edit_note", keys: "keyboard", off: "wifi_off", maybe: "gpp_maybe", verified: "verified", print: "print", upload: "upload_file", done: "task_alt",
  pay: "payments", draw: "draw", more: "expand_more", attach: "attach_file", signed: "assignment_turned_in", fact: "fact_check" };
const CHECKS = {
  required: ["Invoice fields", "doc"], document: ["Document", "doc"], invoice_date: ["Invoice date", "clock"], buyer: ["Billed to", "building"], gstin: ["GSTIN", "hash"], vendor: ["Vendor master", "building"],
  duplicate: ["Duplicate", "copy"], near_duplicate: ["Possible duplicate", "copy"], po: ["Purchase order", "cart"], bank: ["Bank details", "bank"], bank_request: ["Bank change request", "warn"],
  ifsc: ["IFSC registry", "bank"], gst: ["GSTR-2B", "receipt"], credit: ["GST credit clock", "clock"], einvoice: ["E-invoice", "doc"], sender: ["Sender", "mail"], company: ["Company record", "building"],
  msme: ["MSME deadline", "clock"], tds: ["TDS draft", "percent"], instruction: ["Your instruction", "note"], internal: ["System", "info"], payment_conflict: ["Payment", "rupee"], payment: ["Payment provider", "rupee"], master_changed: ["Changed fact", "warn"],
};
const PROBLEMS = {
  bank: "Bank account doesn't match", sender: "Sent from a lookalike domain", bank_request: "Asks to change bank details", duplicate: "Already on the books", near_duplicate: "Looks like a duplicate",
  po: "Over the PO balance", gst: "Missing from GSTR-2B", company: "Can't verify the company", tds: "TDS needs a person", ifsc: "Bank branch not confirmed", gstin: "GSTIN isn't valid", vendor: "Not on the vendor master",
  required: "Details are missing", document: "Doesn't read as an invoice", invoice_date: "Check the invoice date", buyer: "Billed to someone else", instruction: "Held on your instruction", einvoice: "E-invoice number missing",
  master_changed: "Facts changed after sign-off", payment_conflict: "Check this payment first", payment: "Provider refused it", internal: "Couldn't finish checking", msme: "MSME deadline", credit: "GST credit deadline",
};
const problem = check => PROBLEMS[check] || (CHECKS[check] || ["Needs a look"])[0];
const STATES = { BLOCKED: ["Blocked", "shieldx"], HELD: ["Held", "warn"], READY: ["Ready", "check"], APPROVED: ["Signed", "lock"], PAID: ["Issued", "check"], REJECTED: ["Rejected", "x"], NEW: ["Checking", "clock"] };
const STATUS = { pass: ["Verified", "check"], fail: ["Failed", "x"], unverified: ["Can't verify", "info"], info: ["Note", "info"], POSTED: ["Posted", "check"], HELD: ["Held", "warn"], REJECTED: ["Dismissed", "x"] };
const SHAPE_OF = { READY: "circle", HELD: "soft", BLOCKED: "burst", APPROVED: "clover", PAID: "cookie", REJECTED: "circle", NEW: "soft" };
const SEEDS = { bay: ["#0061a3", "#d4e3ff", "#b7c7e4"], forest: ["#196b47", "#beedd2", "#adcebb"], peony: ["#993f65", "#ffd8e5", "#e3bcc9"], marigold: ["#7c5816", "#ffddb2", "#d8c3a9"] };
const NAV = [["today", "Today", "today"], ["review", "Review", "inbox"], ["bank", "Bank", "bank"], ["books", "Books", "books"], ["audit", "Audit", "shield"]];
const FILTERS = { needs: ["Needs you", ["BLOCKED", "HELD"]], ready: ["Ready", ["READY", "APPROVED"]], issued: ["Issued", ["PAID"]], all: ["All", Object.keys(STATES)] };
const GROUPS = [["Needs your decision", ["BLOCKED", "HELD"]], ["Ready to sign", ["READY"]], ["Signed, waiting to issue", ["APPROVED"]], ["Payment requests issued", ["PAID"]], ["Rejected", ["REJECTED"]], ["Checking", ["NEW"]]];

let S = null, route = ["today"], filter = "needs", sigs = {}, composerOpen = false, useSample = true, draft = null, pollTimer = null, online = true;
let mounted = "", busyMorph = null, railRefs = null, current = null, drawerKind = null, pending = null, bankDraft = "", booksKind = "vendors", startedExceptions = 0, planOpen = false, drillResult = null, drillBusy = false, listAnim = false, stepRun = "", celebrated = "", lastMessage = "";
const rollMemory = {}, doneSteps = new Set(), seenLive = new Set();
const hiddenIds = new Set();
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
const wide = matchMedia("(min-width: 840px)");

/* Helpers */
function h(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "style") Object.assign(e.style, v);
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (k === "value") e.value = v;
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(4)) if (kid !== null && kid !== undefined && kid !== false) e.append(kid);
  return e;
}
function icon(name, size = 24, fill = false) {
  return h("span", { class: "ms" + (fill ? " fill" : ""), style: { fontSize: size + "px" }, "aria-hidden": "true" }, String.fromCodePoint(SYM[ICONS[name]] || SYM.info));
}
function shape(kind) {
  const pts = [], n = 120;
  const radius = { circle: () => 1, soft: a => .93 + .07 * Math.cos(5 * a), cookie: a => .9 + .1 * Math.cos(9 * a), clover: a => .8 + .2 * Math.cos(4 * a), burst: a => .84 + .16 * Math.cos(12 * a), pebble: a => .9 + .07 * Math.cos(3 * a + 1) + .03 * Math.cos(5 * a) }[kind];
  for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2, r = radius(a) * 50; pts.push(`${(50 + r * Math.cos(a)).toFixed(2)}% ${(50 + r * Math.sin(a)).toFixed(2)}%`); }
  return `polygon(${pts.join(",")})`;
}
const shaped = (cls, kind, ...kids) => h("span", { class: cls, style: { clipPath: shape(kind) } }, ...kids);
const tag = (key, map = STATES) => h("span", { class: "tag " + key }, icon((map[key] || [key, "info"])[1], 15), (map[key] || [key])[0]);
const avatar = (name, state) => h("span", { class: "avw" }, h("span", { class: "av" }, name[0].toUpperCase()), h("span", { class: "pip " + state, title: (STATES[state] || [state])[0] }, icon((STATES[state] || [])[1] || "info", 12, true)));
function money(text, key) {
  const m = /^(.*)(\.\d\d)$/.exec(text || "");
  if (!m) return h("span", { class: "amount missing" }, "Amount missing");
  if (!key || reduced.matches) return h("span", { class: "amount num" }, m[1], h("small", {}, m[2]));
  const before = rollMemory[key] || m[1].replace(/\d/g, "0"), chars = [...m[1]], old = [...before], shift = old.length - chars.length;
  rollMemory[key] = m[1];
  const columns = chars.map((c, i) => {
    if (!/\d/.test(c)) return h("span", { "aria-hidden": "true" }, c);
    const from = /\d/.test(old[i + shift] || "") ? old[i + shift] : "0";
    const strip = h("span", { class: "strip", style: { "--d": from, "--i": chars.length - i } }, [..."0123456789"].map(n => h("span", {}, n)));
    strip.style.setProperty("--d", from); strip.style.setProperty("--i", chars.length - i);
    requestAnimationFrame(() => requestAnimationFrame(() => strip.style.setProperty("--d", c)));
    return h("span", { class: "col", "aria-hidden": "true" }, strip);
  });
  return h("span", { class: "amount num roll", role: "text", "aria-label": text }, columns, h("small", { "aria-hidden": "true" }, m[2]));
}
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function day(iso) {
  if (!iso) return "No date";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
}
const human = t => String(t ?? "").replace(/\b(20\d\d)-(0[1-9]|1[0-2])-(\d\d)\b/g, m => day(m)).replace(/\b(20\d\d)-(0[1-9]|1[0-2])\b/g, (_, y, m) => `${MONTHS[+m - 1]} ${y}`);
function sourceLabel(s) {
  s = String(s || "");
  if (s.startsWith("https://ifsc") || s.startsWith("ifsc")) return "IFSC registry";
  if (s.startsWith("crustdata:")) return "Crustdata company record";
  if (s.startsWith("vendor_changes")) return "Approved bank change";
  if (s.startsWith("vendors.")) return "Vendor master";
  if (s.startsWith("pos.")) return s.includes("=") ? `Purchase order ${s.split("=")[1]}` : "Purchase orders";
  if (s.startsWith("invoices.")) return s.includes("=") ? `Invoice #${s.split("=")[1]}` : "Invoice history";
  if (s.startsWith("gstr2b")) return "GSTR-2B statement";
  if (s.startsWith("bank_lines")) return "Earlier statement line";
  if (s.startsWith("payment:")) return "Payment issued by Chukta";
  if (s.startsWith("payee_rules")) return "Firm's payee rule";
  return s ? s[0].toUpperCase() + s.slice(1) : "";
}
const stamp = iso => iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { /* Optional. */ } } };
const reviewer = () => store.get("chukta-reviewer") || "";
let snackTimer;
function snack(text, action) {
  const el = document.getElementById("snack");
  el.replaceChildren(h("span", {}, text), action ? h("button", { onclick: action.run }, action.label) : "");
  el.className = "on";
  clearTimeout(snackTimer); snackTimer = setTimeout(() => { el.className = ""; }, action ? 5000 : 4200);
}
const hideSnack = () => { clearTimeout(snackTimer); document.getElementById("snack").className = ""; };
async function get(path) { const r = await fetch(path); if (!r.ok) throw new Error("Not available"); return r.json(); }
async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json", "x-chukta": "1" }, body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "That did not work");
  return data;
}
function askReviewer() {
  return new Promise(resolve => {
    if (reviewer()) return resolve(reviewer());
    const box = document.getElementById("who"), input = h("input", { class: "input", id: "whoName", autocomplete: "name", placeholder: "Your name" });
    const done = value => { box.hidden = true; document.removeEventListener("keydown", onKey); resolve(value); };
    const save = () => { const v = input.value.trim(); if (!v) return input.focus(); store.set("chukta-reviewer", v); renderRail(); done(v); };
    const onKey = e => { if (e.key === "Escape") done(""); if (e.key === "Enter") { e.preventDefault(); save(); } };
    box.replaceChildren(h("h2", { class: "title", id: "who-title" }, "Who is reviewing?"), h("p", { class: "body-s", style: { margin: "4px 0 14px" } }, "Your name goes on every decision in the audit trail."),
      h("label", { class: "field" }, h("span", {}, "Reviewer"), input), h("div", { class: "actions", style: { justifyContent: "flex-end" } }, h("button", { class: "btn text", onclick: () => done("") }, "Cancel"), h("button", { class: "btn filled", onclick: save }, "Continue")));
    box.hidden = false; document.addEventListener("keydown", onKey); input.focus();
  });
}
async function act(path, body, done) {
  const by = await askReviewer();
  if (!by) return false;
  try {
    await flushPending();
    await post(path, { by, ...body });
    if (done) snack(done);
    sigs.view = sigs.list = sigs.detail = ""; await tick();
    return true;
  } catch (e) { snack(e.message); return false; }
}
function trap(el, onClose) {
  const onKey = e => {
    if (e.key === "Escape") { e.stopPropagation(); return onClose(); }
    if (e.key !== "Tab") return;
    const items = [...el.querySelectorAll("a[href],button:not(:disabled),input,textarea")];
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  document.addEventListener("keydown", onKey);
  return () => document.removeEventListener("keydown", onKey);
}
document.addEventListener("pointerdown", e => {
  const host = e.target.closest?.(".btn,.chip,.fab,.icon-btn,.row,.li");
  if (!host || host.disabled || reduced.matches) return;
  const box = host.getBoundingClientRect(), size = Math.max(box.width, box.height) * 2.2;
  const dot = h("span", { class: "ripple", style: { width: size + "px", height: size + "px", left: e.clientX - box.left - size / 2 + "px", top: e.clientY - box.top - size / 2 + "px" } });
  host.append(dot); setTimeout(() => dot.remove(), 560);
});

/* Navigation: updated in place so its transitions actually run */
function renderRail() {
  const need = visibleNeeds().length;
  if (!railRefs) {
    railRefs = { dests: {}, badge: h("span", { class: "badge" }), me: shaped("me", "cookie") };
    document.getElementById("rail").replaceChildren(
      h("div", { class: "brand", style: { clipPath: shape("cookie") }, "aria-hidden": "true" }, icon("check", 24)),
      h("button", { class: "fab", "aria-label": "New run", title: "New run", onclick: e => morphTo(e.currentTarget, () => { composerOpen = true; if (route[0] !== "today") { history.replaceState(null, "", "#/today"); route = ["today"]; } sigs.view = ""; renderRail(); renderView(); renderDock(); }, () => document.querySelector(".ask-card")) }, icon("plus", 28)),
      ...NAV.map(([id, label, ic]) => { const a = h("a", { class: "dest", href: "#/" + id }, h("span", { class: "pill" }, icon(ic)), id === "review" ? railRefs.badge : null, label); railRefs.dests[id] = a; return a; }),
      h("div", { class: "rail-end" }, h("button", { class: "icon-btn", "aria-label": "Keyboard shortcuts", title: "Keyboard shortcuts (?)", onclick: showKeys }, icon("keys")),
        h("button", { class: "icon-btn", "aria-label": "Reviewer and theme", title: "Reviewer and theme", "aria-haspopup": "true", onclick: toggleMenu }, railRefs.me)));
  }
  for (const [id, a] of Object.entries(railRefs.dests)) { if (route[0] === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); }
  if (railRefs.badge.textContent !== String(need) && need && !reduced.matches) railRefs.badge.animate([{ transform: "scale(1.6)" }, { transform: "scale(1)" }], { duration: 420, easing: "cubic-bezier(.34,1.56,.64,1)" });
  railRefs.badge.textContent = String(need); railRefs.badge.hidden = !need; railRefs.badge.setAttribute("aria-label", plural(need, "exception"));
  const who = reviewer(); railRefs.me.replaceChildren(who ? who[0].toUpperCase() : icon("user", 20));
}
function toggleMenu(e) {
  e?.stopPropagation();
  const menu = document.getElementById("menu");
  if (!menu.hidden) { menu.hidden = true; return; }
  const root = document.documentElement;
  const paint = () => menu.replaceChildren(
    h("label", { class: "field", style: { marginBottom: "14px" } }, h("span", {}, "Reviewer"), h("input", { class: "input", value: reviewer(), placeholder: "Your name", oninput: x => { store.set("chukta-reviewer", x.target.value.trim()); renderRail(); } })),
    h("div", { class: "title-s" }, "Your palette"),
    h("div", { class: "swatches" }, Object.entries(SEEDS).map(([name, [a, b, c]]) => h("button", { class: "swatch", "aria-label": name, "aria-pressed": String(root.dataset.seed === name), onclick: x => { x.stopPropagation(); root.dataset.seed = name; store.set("chukta-seed", name); paint(); } },
      h("i", { style: { background: a } }), h("i", { style: { background: b } }), h("i", { style: { background: c } })))),
    h("div", { class: "seg", role: "group", "aria-label": "Brightness" }, [["light", "Light", "sun"], ["dark", "Dark", "moon"]].map(([m, label, ic]) => h("button", { "aria-pressed": String(root.dataset.mode === m), onclick: x => { x.stopPropagation(); root.dataset.mode = m; store.set("chukta-mode", m); paint(); } }, icon(ic, 18), label))));
  paint(); menu.hidden = false;
}
document.addEventListener("click", e => { const m = document.getElementById("menu"); if (!m.hidden && !m.contains(e.target)) m.hidden = true; });
function go(...parts) { const hash = "#/" + parts.join("/"); if (location.hash !== hash) location.hash = hash; else onRoute(); }
function onRoute() {
  const before = route;
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  route = parts.length ? parts : ["today"];
  if (route[0] === "ledger") route = ["audit", "ledger"];
  if (!NAV.some(n => n[0] === route[0])) route = ["today"];
  drawerKind = null;
  sigs.detail = "";
  if (before[0] !== route[0] || route[0] === "audit") { sigs.view = ""; sigs.list = ""; }
  if (!S) return;
  renderRail();
  const apply = () => { const done = renderView(); renderDock(); return done; };
  if (document.startViewTransition && !reduced.matches && before[0] !== route[0]) document.startViewTransition(apply); else apply();
}
addEventListener("hashchange", onRoute);
function mount(type, node) {
  if (mounted !== type) stagger(node);
  mounted = type;
  document.getElementById("view").replaceChildren(node);
}

/* Today */
const shortClient = () => S.client.replace(/ Private Limited.*$/, "");
const longDate = () => new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
const appbar = (title, extra, glance) => h("header", { class: "bar" }, h("div", {}, h("p", { class: "glance" }, glance ?? longDate()), h("h1", { class: "display" }, title)), extra ? h("div", { class: "bar-end" }, extra) : null);
const providerPill = () => h("span", { class: "note-pill" }, h("span", { class: "dot" }), S.provider);
function stepsFor() {
  const r = S.run, c = S.counts, stage = r.stage, ex = c.BLOCKED + c.HELD;
  const early = ["reading", "checking", "investigating"], at = early.indexOf(stage), past = at === -1;
  const pos = i => past || at > i ? "done" : at === i ? "active" : "todo";
  const signed = c.APPROVED + c.PAID;
  const signSt = !past ? "todo" : c.READY || ex ? "need" : signed ? "done" : "todo";
  const signNote = !past ? "Waits for a person" : `${signed} signed${c.READY ? `, ${c.READY} ready` : ""}${ex ? `, ${ex} open` : ""}`;
  return [
    { title: "Understand the request", note: r.understood.job, st: "done" },
    { title: "Read every invoice", note: `${r.inputs_done} of ${r.inputs_total}`, st: pos(0), pct: r.inputs_total ? r.inputs_done / r.inputs_total : 0 },
    { title: "Check independent records", note: "GST, PO, vendor, bank, IFSC, company", st: pos(1) },
    { title: "Look into exceptions", note: past ? (ex ? plural(ex, "exception") + " explained" : "None open") : "Read-only, every citation checked", st: pos(2) },
    { title: "Your sign-off", note: signNote, st: signSt },
    { title: "Issue each payment once", note: c.PAID ? `${c.PAID} issued in ${S.provider}` : S.provider, st: stage === "paying" ? "active" : c.PAID && !c.APPROVED ? "done" : c.APPROVED ? "need" : "todo" },
    { title: "Prove the books", note: S.audit_problems.length ? S.audit_problems[0] : c.PAID ? "Audit replay is clean" : "After payment", st: c.PAID && !S.audit_problems.length && stage !== "paying" && !c.APPROVED ? "done" : "todo" },
  ];
}
function wave() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"), path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  let d = "M0 5"; for (let x = 0; x < 2400; x += 16) d += ` q8 ${x % 32 ? 7 : -7} 16 0`;
  path.setAttribute("d", d); svg.setAttribute("viewBox", "0 0 2400 10"); svg.setAttribute("preserveAspectRatio", "xMinYMid slice"); svg.append(path);
  return svg;
}
function morphing(el) {
  if (reduced.matches) return el;
  el.animate(["soft", "cookie", "clover", "burst", "pebble", "soft"].map(k => ({ clipPath: shape(k) })), { duration: 5200, iterations: Infinity, easing: "cubic-bezier(.4,0,.2,1)" });
  el.animate([{ transform: "rotate(0)" }, { transform: "rotate(360deg)" }], { duration: 6400, iterations: Infinity });
  return el;
}
const tile = (ic, title, text, end) => h("div", { class: "tile" }, h("span", { class: "sh" }, icon(ic, 22)), h("div", {}, h("b", {}, title), h("div", { class: "body-s" }, text)), end || "");
function composer() {
  if (draft === null) draft = S.sample_request;
  const pasted = h("textarea", { class: "input mono", id: "pasteText", rows: 6, "aria-label": "Invoice text", placeholder: "Paste invoices or emails. Put a line with only --- between them. Fictional data only." });
  const box = h("div", { hidden: useSample }, pasted);
  const sampleChip = h("button", { class: "chip", "aria-pressed": String(useSample), onclick: () => choose(true) }, icon("receipt", 18), `This week's ${S.sample_count} invoices`);
  const pasteChip = h("button", { class: "chip", "aria-pressed": String(!useSample), onclick: () => choose(false) }, icon("paste", 18), "Paste");
  function choose(sample) { useSample = sample; sampleChip.setAttribute("aria-pressed", String(sample)); pasteChip.setAttribute("aria-pressed", String(!sample)); box.hidden = sample; if (!sample) pasted.focus(); }
  async function addFiles(files) {
    const texts = [];
    for (const f of files) {
      if (f.size > 30000 || !(/\.(txt|eml)$/i.test(f.name) || f.type.startsWith("text/"))) { snack(`${f.name} isn't a small text or email file. Paste its text instead.`); continue; }
      texts.push((await f.text()).trim());
    }
    if (!texts.length) return;
    pasted.value = [pasted.value.trim(), ...texts].filter(Boolean).join("\n---\n");
    choose(false); snack(`${plural(texts.length, "file")} added`);
  }
  const file = h("input", { type: "file", class: "sr", multiple: true, accept: ".txt,.eml,text/plain", "aria-label": "Add invoice files", onchange: e => { addFiles(e.target.files); e.target.value = ""; } });
  const attach = h("label", { class: "chip", style: { cursor: "pointer" } }, icon("attach", 18), "Add files", file);
  const ask = h("textarea", { class: "ask", "aria-label": "What should Chukta do?", rows: 4, placeholder: "What do you need done?", oninput: e => { draft = e.target.value; } });
  ask.value = draft;
  const start = h("button", { class: "btn filled lg run-btn", onclick: async () => {
    try {
      await post("/api/run", { request: ask.value, ...(useSample ? { sample: true } : { text: pasted.value }) });
      composerOpen = false; sigs.view = ""; await tick();
    } catch (e) { snack(e.message); }
  } }, icon("play", 26), "Run");
  const card = h("section", { class: "ask-card", "aria-label": "New request" }, ask, box, h("div", { class: "ask-foot" }, h("div", { class: "chips" }, sampleChip, pasteChip, attach), start));
  card.addEventListener("dragover", e => { e.preventDefault(); card.classList.add("drop"); });
  card.addEventListener("dragleave", () => card.classList.remove("drop"));
  card.addEventListener("drop", e => { e.preventDefault(); card.classList.remove("drop"); addFiles(e.dataTransfer.files); });
  const records = h("div", { class: "group" }, tile("books", "Vendor master", "Loading"));
  get("/api/books").then(b => records.replaceChildren(
    tile("books", "Vendor master", plural(b.vendors.length, "vendor")),
    tile("cart", "Purchase orders", `${b.pos} open`),
    tile("receipt", "GSTR-2B", b.periods.map(human).join(", ") || "None imported"),
    tile("pay", "Payments", S.provider))).catch(() => {});
  return h("div", { class: "page" }, appbar(shortClient(), [h("span", { class: "note-pill" }, "Fictional client"), providerPill()]),
    h("div", { class: "today-grid" }, card, h("aside", {}, h("div", { class: "sec" }, "Checks against"), records)));
}
function invoiceRow(i) {
  const open = ["BLOCKED", "HELD"].includes(i.state);
  const sub = open && i.check ? problem(i.check) : i.due ? `MSME: pay by ${day(i.due)}` : `${i.number} · ${day(i.date)}`;
  return h("a", { class: "row", href: `#/review/${i.id}`, "data-id": String(i.id), "aria-current": String(route[1] === String(i.id)) },
    avatar(i.vendor, i.state), h("span", { style: { minWidth: 0 } }, h("span", { class: "who" }, i.vendor), h("span", { class: "sub " + (open ? i.state : "") }, sub)),
    h("span", { class: "amt" }, i.net || i.gross, h("small", {}, i.number)));
}
function heroCard(busy) {
  const c = S.counts, ex = c.BLOCKED + c.HELD, count = c.READY + c.APPROVED;
  if (busy) {
    busyMorph ||= morphing(shaped("morph", "soft", icon("agent", 32)));
    const changed = lastMessage !== S.job.message; lastMessage = S.job.message;
    return h("section", { class: "live", "aria-live": "polite" }, busyMorph, h("div", { class: changed ? "msg-in" : "" }, h("h2", { class: "headline" }, S.job.message), h("p", { class: "body-s" }, S.job.name)));
  }
  busyMorph = null;
  const parts = [["s", count + c.PAID, "Cleared"], ["w", c.HELD, "Held"], ["e", c.BLOCKED, "Blocked"], ["n", c.REJECTED, "Rejected"]].filter(p => p[1]);
  const bar = S.invoices.length ? [h("div", { class: "segbar", role: "img", "aria-label": parts.map(p => `${p[1]} ${p[2]}`).join(", ") }, parts.map(p => h("i", { class: p[0], style: { flexGrow: p[1] } }))),
    h("div", { class: "legend" }, parts.map(p => h("span", {}, h("i", { class: "segbar-dot", style: { background: { s: "var(--md-primary)", w: "var(--md-warning)", e: "var(--md-error)", n: "var(--md-outline)" }[p[0]] } }), h("b", {}, String(p[1])), p[2])))] : null;
  const review = ex ? h("a", { class: "btn tonal", href: "#/review", onclick: () => { filter = "needs"; } }, `Review ${ex}`) : null;
  if (c.PAID && !count) return h("section", { class: "hero " + (ex ? "" : "good") }, shaped("stamp", "cookie", icon("check", 34)),
    h("div", { class: "kicker" }, "Payment requests issued"), money(S.issued, "hero"), h("div", { class: "sub" }, `${plural(c.PAID, "invoice")}, each issued once in ${S.provider}`), bar,
    h("div", { class: "actions" }, h("a", { class: "btn filled", href: "#/audit" }, icon("receipt", 20), "Open run sheet"), review));
  if (count) return h("section", { class: "hero" }, h("div", { class: "kicker" }, c.READY ? "Ready to sign" : "Signed, ready to issue"), money(S.payment_run.net, "hero"),
    h("div", { class: "sub" }, `${plural(count, "invoice")}, net of TDS`), bar, h("div", { class: "actions" }, h("button", { class: "btn filled", onclick: openSign }, icon("draw", 20), c.READY ? "Review and sign" : "Issue payments"), review));
  return h("section", { class: "hero quiet" }, h("div", { class: "kicker" }, ex ? `${plural(ex, "invoice")} need you` : "Nothing is waiting"), h("div", { class: "sub" }, ex ? "Nothing can be signed until you decide." : "Start a new run when you're ready."), bar, h("div", { class: "actions" }, review));
}
function renderToday() {
  if (composerOpen || !S.run) {
    if (sigs.view !== "composer") { sigs.view = "composer"; mount("composer", composer()); }
    return;
  }
  const key = "run" + JSON.stringify([S.run, S.counts, S.job, S.audit_problems, S.issued, S.payment_run.net, S.invoices.map(i => [i.id, i.state, i.check]), [...hiddenIds]]);
  if (sigs.view === key) return; sigs.view = key;
  const r = S.run, busy = S.job.running, steps = stepsFor(), needs = visibleNeeds();
  if (stepRun !== r.id) { stepRun = r.id; doneSteps.clear(); seenLive.clear(); }
  const plan = h("details", { class: "fold", open: busy || planOpen, ontoggle: e => { if (!busy) planOpen = e.target.open; } },
    h("summary", {}, "Plan", h("small", {}, `${steps.filter(s => s.st === "done").length} of ${steps.length} done`), icon("more", 22)),
    h("div", {}, h("ol", { class: "steps" }, steps.map((s, i) => h("li", { class: "step " + s.st + (s.st === "done" && !doneSteps.has(i) && (doneSteps.add(i), true) ? " pop" : ""), "aria-current": s.st === "active" ? "step" : null },
      h("span", { class: "st" }, s.st === "done" ? icon("check", 16) : s.st === "need" ? icon("user", 16) : String(i + 1)),
      h("div", {}, h("div", { class: "title-s" }, s.title), h("div", { class: "body-s" }, s.note),
        s.st === "active" ? h("div", { class: "wave", style: s.pct !== undefined ? { width: Math.max(8, s.pct * 100) + "%" } : null }, wave()) : null))))));
  const ceiling = h("details", { class: "fold" }, h("summary", {}, "Run ceiling", h("small", {}, `${r.credits} of ${r.credit_limit} credits`), icon("more", 22)),
    h("div", {}, meter("Crustdata credits", r.credits, r.credit_limit, `${r.credits} of ${r.credit_limit}`), meter("Model spend", r.usd, r.model_usd_limit, `$${r.usd.toFixed(4)} of $${r.model_usd_limit.toFixed(2)}`),
      h("p", { class: "body-s" }, `Time limit ${Math.round(r.time_limit_s / 60)} minutes. ${plural(r.calls, "call")} in the ledger.`)));
  const asked = h("details", { class: "fold" }, h("summary", {}, "Your request", icon("more", 22)),
    h("div", {}, h("p", { class: "quote" }, r.request), r.understood.notes.map(n => h("p", { class: "body-s", style: { marginTop: "8px" } }, n)),
      h("button", { class: "btn text", style: { marginLeft: "-14px", marginTop: "4px" }, onclick: () => { composerOpen = true; draft = r.request; sigs.view = ""; renderView(); } }, icon("plus", 20), "New run")));
  mount("today", h("div", { class: "page" }, appbar(shortClient(), [h("span", { class: "note-pill" }, "Fictional client"), providerPill()]),
    h("div", { class: "today-grid" },
      h("div", {}, heroCard(busy), busy && S.invoices.length ? liveRows() : null, !busy && needs.length ? [h("div", { class: "sec", style: { paddingTop: "24px" } }, "Needs you", h("span", {}, String(needs.length))), h("div", { class: "group" }, needs.map(invoiceRow))] : null),
      h("aside", {}, plan, ceiling, asked))));
  const seal = document.querySelector(".hero .stamp");
  if (seal && !busy && celebrated !== r.id + S.issued) { celebrated = r.id + S.issued; requestAnimationFrame(() => celebrate(seal)); }
}
function liveRows() {
  const rows = [...S.invoices].sort((a, b) => a.id - b.id).map(i => { const row = invoiceRow(i); if (!seenLive.has(i.id)) { seenLive.add(i.id); row.classList.add("arrive"); } return row; });
  return [h("div", { class: "sec", style: { paddingTop: "24px" } }, "Working through", h("span", {}, String(rows.length))), h("div", { class: "group" }, rows)];
}
const meter = (name, used, limit, text) => h("div", { class: "meter" }, h("div", { class: "meter-h" }, h("span", {}, name), h("b", {}, text)),
  h("div", { class: "track", role: "img", "aria-label": `${name}: ${text}` }, used > 0 ? h("i", { style: { width: Math.max(1, Math.min(100, limit ? used / limit * 100 : 0)) + "%" } }) : null));

/* Review */
const visibleNeeds = () => (S?.invoices || []).filter(i => ["BLOCKED", "HELD"].includes(i.state) && !hiddenIds.has(i.id));
const shownInvoices = () => S.invoices.filter(i => FILTERS[filter][1].includes(i.state) && !hiddenIds.has(i.id));
function renderReview() {
  const v = document.getElementById("view");
  if (!v.querySelector(".ld")) {
    sigs.list = ""; sigs.detail = ""; mounted = "review"; listAnim = true;
    v.replaceChildren(h("div", { class: "ld" }, h("section", { class: "list-pane", id: "listPane", "aria-label": "Invoices" }), h("section", { class: "detail-pane", id: "detailPane", "aria-label": "Invoice detail" })));
  }
  if (!route[1] && filter === "needs" && wide.matches && visibleNeeds().length) { location.replace(`#/review/${visibleNeeds()[0].id}`); return; }
  v.querySelector(".ld").classList.toggle("open", Boolean(route[1]));
  const key = JSON.stringify([S.invoices, filter, [...hiddenIds]]);
  if (sigs.list !== key) { sigs.list = key; renderList(); }
  document.querySelectorAll("#listPane .row").forEach(r => r.setAttribute("aria-current", String(r.dataset.id === route[1])));
  return renderDetail();
}
function renderList() {
  const pane = document.getElementById("listPane"), keep = pane.scrollTop;
  const count = id => S.invoices.filter(i => FILTERS[id][1].includes(i.state) && !hiddenIds.has(i.id)).length;
  const shown = shownInvoices(), items = [];
  for (const [name, states] of GROUPS) {
    const rows = shown.filter(i => states.includes(i.state));
    if (!rows.length) continue;
    items.push(h("div", { class: "list-group" }, name), h("div", { class: "group" }, rows.map(invoiceRow)));
  }
  pane.replaceChildren(h("header", {}, h("h1", { class: "display" }, "Review"),
    h("div", { class: "chips", role: "group", "aria-label": "Filter" }, Object.entries(FILTERS).map(([id, [label]]) => h("button", { class: "chip", "aria-pressed": String(filter === id), onclick: () => { filter = id; sigs.list = ""; listAnim = true; renderReview(); } }, filter === id ? icon("check", 16) : null, label, h("span", { class: "n" }, String(count(id))))))),
  ...(items.length ? items : [h("div", { class: "empty", style: { height: "auto" } }, shaped("sh", "cookie", icon("check", 44)), h("div", { class: "title" }, filter === "needs" ? "Nothing needs you" : "Nothing here yet"), h("p", { class: "body-s" }, S.invoices.length ? "Choose another filter." : "Start a job from Today."))]));
  pane.scrollTop = keep;
  if (listAnim) { stagger(pane); listAnim = false; }
}
async function renderDetail() {
  const pane = document.getElementById("detailPane");
  if (!pane) return;
  if (!route[1]) {
    const zero = S.invoices.length && !visibleNeeds().length && startedExceptions > 0;
    const k = zero ? "zero" : "none";
    if (sigs.detail !== k) {
      sigs.detail = k; current = null;
      if (zero) setTimeout(() => celebrate(pane.querySelector(".empty.zero .sh")), 180);
      pane.replaceChildren(zero
        ? h("div", { class: "empty zero" }, shaped("sh", "cookie", icon("check", 42)), h("div", { class: "headline" }, `All ${startedExceptions} exceptions cleared`), S.counts.READY + S.counts.APPROVED ? h("button", { class: "btn filled", onclick: openSign }, icon("draw", 20), "Review and sign") : h("p", { class: "body-s" }, "Nothing is waiting on you."))
        : h("div", { class: "empty" }, shaped("sh", "clover", icon("inbox", 44)), h("div", { class: "title" }, "Pick an invoice"), h("p", { class: "body-s" }, "Press ? for shortcuts.")));
    }
    return;
  }
  const id = route[1];
  let d;
  try { d = await get(`/api/invoice/${id}`); } catch {
    if (route[1] === id && sigs.detail !== "missing") { sigs.detail = "missing"; current = null; pane.replaceChildren(h("div", { class: "empty" }, shaped("sh", "soft", icon("doc", 36)), h("div", { class: "title" }, "No such invoice"), h("a", { class: "btn tonal", href: "#/review" }, "Back to the queue"))); }
    return;
  }
  if (route[1] !== id) return;
  const key = id + "[" + JSON.stringify([d.state, d.findings, d.investigation?.at, d.order, d.payment_ref, d.can_approve, d.bank_change, d.can_propose_bank, S.counts]);
  if (sigs.detail === key || drawerKind || ["noteText", "tdsIn"].includes(document.activeElement?.id)) return;
  const fresh = !(sigs.detail || "").startsWith(id + "[");
  sigs.detail = key; current = d;
  const node = detailView(d);
  if (fresh) node.classList.add("fresh"); else node.style.animation = "none";
  pane.replaceChildren(node);
  if (fresh) pane.scrollTop = 0;
}
const fact = (a, b) => h("div", {}, h("span", {}, a), h("b", {}, b || "Not recorded"));
const more = (title, body) => h("details", { class: "fold" }, h("summary", {}, title, icon("more", 22)), h("div", {}, body));
function evidenceRow(d, f) {
  const [label, ic] = CHECKS[f.check_name] || [f.check_name, "info"];
  return h("button", { class: "li", onclick: () => openRecord(d.id, f.check_name), "aria-haspopup": "dialog" },
    h("span", { class: "sh " + f.status }, icon(ic, 20)),
    h("span", {}, h("strong", {}, label), h("span", { class: "what" }, human(f.detail)), h("span", { class: "src" }, `${(STATUS[f.status] || [f.status])[0]} · ${sourceLabel(f.source)} · ${day(f.retrieved_at)}`), h("span", { class: "sr" }, "Open record")),
    icon("chevron", 20));
}
function compareView(rows) {
  return rows.map((c, n) => h("div", { class: "cmp" }, h("div", { class: "label" }, c.label),
    h("div", { class: "cmp-row" }, h("span", { class: "body-s" }, "Invoice"), digitRow(c.invoice, c.master, n * 8)),
    h("div", { class: "cmp-row" }, h("span", { class: "body-s" }, "On file"), digitRow(c.master, c.invoice, n * 8 + 4))));
}
function detailView(d) {
  const n = d.investigation, open = ["HELD", "BLOCKED"].includes(d.state);
  const titles = { READY: "Clean. In the next sign-off.", APPROVED: "Signed. Waiting to be issued.", PAID: "Issued once.", REJECTED: "Rejected." };
  const bodies = { READY: "Every record agrees with this invoice.", APPROVED: d.order ? `Signed by ${d.order.by}. The payee and amount are frozen.` : "", PAID: `Reference ${d.payment_ref || ""}, in ${S.provider}.`, REJECTED: "This invoice will not be paid." };
  const queue = visibleNeeds(), at = queue.findIndex(i => String(i.id) === String(d.id));
  const problems = d.findings.filter(f => !["pass", "info"].includes(f.status)), rest = d.findings.filter(f => ["pass", "info"].includes(f.status));
  const top = open ? problems[0] : null;
  const slot = h("div", { class: "inline-compare" });
  if (top?.check_name === "bank") get(`/api/record?invoice=${d.id}&check=bank`).then(r => { if (r.compare) slot.replaceChildren(...compareView(r.compare.filter(c => c.invoice !== c.master))); }).catch(() => {});
  const passed = h("div", { class: "group", hidden: problems.length > 0, style: { marginTop: "2px" } }, rest.map(f => evidenceRow(d, f)));
  const toggle = problems.length && rest.length ? h("button", { class: "ev-more", id: "evToggle", "aria-expanded": "false", onclick: e => { passed.hidden = !passed.hidden; e.currentTarget.setAttribute("aria-expanded", String(!passed.hidden)); e.currentTarget.textContent = passed.hidden ? `Show ${rest.length} checks that passed` : "Hide passed checks"; } }, `Show ${rest.length} checks that passed`) : null;
  return h("article", { class: "detail" },
    h("a", { class: "icon-btn back", href: "#/review", "aria-label": "Back to list" }, icon("back")),
    h("header", { class: "d-head" }, avatar(d.vendor, d.state),
      h("div", {}, at >= 0 ? h("div", { class: "position" }, `${at + 1} of ${queue.length}`) : null, h("h2", { class: "title", id: "detailTitle", tabindex: "-1" }, d.vendor), h("p", { class: "body-s" }, `${d.number || "No number"} · ${day(d.date)} · ${d.po || "No PO"}`)), tag(d.state)),
    h("div", { class: "money-row" }, h("div", {}, h("div", { class: "label" }, d.order ? "Net amount" : "Net payable"), money(d.order ? d.order.net_paise : d.net, "detail")),
      h("div", { class: "breakdown" }, fact("Gross", d.order?.gross_paise || d.gross), fact("GST", d.tax), fact(d.order ? "TDS" : "TDS draft", d.order?.tds_paise || d.tds), d.due ? fact("MSME pay by", day(d.due)) : null)),
    h("section", { class: "verdict " + d.state, "aria-label": "Decision" },
      h("h3", { class: "title" }, top ? problem(top.check_name) : titles[d.state] || d.state),
      h("p", {}, top?.check_name === "bank" ? "This invoice names a different account from the one on file." : top ? human(top.detail) : bodies[d.state]), slot,
      n?.callback && open ? h("div", { class: "next" }, icon("phone", 22), h("span", {}, n.callback)) : n && open ? h("div", { class: "next" }, icon("arrow", 22), h("span", {}, n.action_text)) : null,
      d.bank_change ? h("div", { class: "next" }, icon("user", 22), h("span", {}, `${d.bank_change.by} logged a call and proposed ${d.bank_change.account}: "${d.bank_change.note}" A second person must approve it.`)) : null,
      n && open ? h("details", { class: "why" }, h("summary", {}, "Why this was flagged", icon("more", 20)), h("p", {}, human(n.explanation)),
        h("small", {}, n.author === "agent" ? `Written by Chukta's agent. Code confirmed its ${plural(n.citations.length, "source")} and every number.` : "Written from the failed checks.")) : null),
    h("div", { class: "sec", style: { padding: "20px 20px 10px" } }, "Evidence", h("span", {}, "Open a line to see its record")),
    h("div", { class: "evidence" }, problems.length ? h("div", { class: "group" }, problems.map(f => evidenceRow(d, f)), toggle) : null, passed),
    d.reader_notes.length ? more("How it was read", h("ul", { class: "trail" }, d.reader_notes.map(x => h("li", {}, x)))) : null,
    more("Audit trail", h("ul", { class: "trail" }, d.events.map(e => h("li", {}, h("b", {}, e.event.replaceAll("_", " ")), ` by ${e.actor}. ${human(e.detail)}`, h("time", {}, stamp(e.at)))))),
    more("Original document", h("pre", {}, d.raw)),
    toolbar(d));
}
function toolbar(d) {
  if (!["READY", "HELD", "BLOCKED"].includes(d.state)) return null;
  const parts = [];
  if (d.state === "READY") parts.push(h("span", { class: "note-state" }, "In the next sign-off"));
  if (d.state === "HELD" && d.can_approve) parts.push(tbtn("filled", "check", "Approve", "A", () => openDrawer(d, "approve")));
  if (d.can_alias) parts.push(tbtn("ghost", "building", "Confirm name", null, () => act("/api/alias", { id: d.id }, "Name confirmed and rechecked.")));
  if (d.can_propose_bank) parts.push(tbtn("filled", "phone", "Log the call", null, () => openDrawer(d, "call")));
  if (d.bank_change) parts.push(tbtn("filled", "user", "Approve change", null, () => act("/api/bank-change/approve", { change: d.bank_change.id }, "Bank details updated. Open invoices were rechecked.")));
  if (d.state === "BLOCKED" && !d.can_propose_bank && !d.bank_change) parts.push(tbtn("filled", "x", "Reject", "R", () => openDrawer(d, "reject")));
  parts.push(tbtn("ghost", "refresh", "Recheck", "C", () => act("/api/recheck", { id: d.id }, "Rechecked against the records.")));
  if (!(d.state === "BLOCKED" && !d.can_propose_bank && !d.bank_change)) parts.push(h("button", { class: "icon-btn", "aria-label": "Reject", title: "Reject (R)", onclick: () => openDrawer(d, "reject") }, icon("x")));
  return h("div", { class: "toolbar-wrap", id: "toolbarWrap" }, h("div", { class: "toolbar", role: "toolbar", "aria-label": "Your decision" }, parts));
}
const tbtn = (kind, ic, label, key, run) => h("button", { class: "btn " + kind, onclick: run, title: key ? `${label} (${key})` : label }, icon(ic, 18), label);
function closeDrawer() { drawerKind = null; document.getElementById("drawer")?.remove(); }
function openDrawer(d, kind) {
  closeDrawer(); drawerKind = kind;
  const note = h("textarea", { class: "input", id: "noteText", rows: 2, placeholder: { approve: "What did you check?", reject: "Why are you rejecting it?", call: "Who did you call, on which number from your records, and what did they confirm?" }[kind] });
  const retain = h("input", { type: "checkbox" }), tds = h("input", { class: "input", id: "tdsIn", inputmode: "decimal", placeholder: "TDS in rupees" });
  const submit = () => {
    const text = note.value.trim();
    if (kind === "approve") {
      if (!text && d.state === "HELD") return note.focus();
      if (d.needs_tds && !tds.value.trim()) return tds.focus();
      closeDrawer();
      defer("/api/approve", { id: d.id, evidence: d.evidence, note: text, retain_gst: retain.checked, tds_rupees: d.needs_tds ? tds.value : "" }, `Approved ${d.vendor}.`, d.id);
    } else if (kind === "reject") {
      if (!text) return note.focus();
      closeDrawer(); defer("/api/reject", { id: d.id, note: text }, `Rejected ${d.vendor}.`, d.id);
    } else {
      if (text.length < 10) return note.focus();
      closeDrawer(); act("/api/bank-change/propose", { id: d.id, note: text }, "Call logged. A second person must approve the change.");
    }
  };
  note.addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); submit(); } if (e.key === "Escape") { e.stopPropagation(); closeDrawer(); } });
  const drawer = h("div", { class: "drawer", id: "drawer" },
    h("label", { class: "field" }, h("span", {}, { approve: "Note for the audit trail", reject: "Reason for rejecting", call: "Log the callback" }[kind]), note),
    kind === "approve" && d.needs_tds ? h("label", { class: "field", style: { marginTop: "8px" } }, h("span", {}, "TDS to deduct"), tds) : null,
    kind === "approve" && d.can_retain_gst ? h("label", { class: "tick" }, retain, `Retain GST (${d.tax}) until the supplier files`) : null,
    h("div", { class: "actions" }, h("button", { class: "btn text", onclick: closeDrawer }, "Cancel"), h("button", { class: "btn filled", onclick: submit }, { approve: "Approve", reject: "Reject", call: "Log call" }[kind], h("kbd", {}, "Ctrl+Enter"))));
  document.getElementById("toolbarWrap")?.prepend(drawer);
  note.focus();
}
/* Approve and reject wait five seconds, so they can be undone. Closing the tab records nothing, which is the safe failure. */
async function defer(path, body, label, id) {
  const by = await askReviewer();
  if (!by) return;
  await flushPending();
  await sweep(id);
  hiddenIds.add(id);
  const next = nextAfter(id);
  const entry = { path, body: { by, ...body }, id };
  entry.timer = setTimeout(() => commitPending(entry), 5000);
  pending = entry;
  snack(label, { label: "Undo", run: () => undoPending(entry) });
  sigs.list = "";
  if (next) go("review", next.id); else go("review");
  setTimeout(() => document.getElementById("detailTitle")?.focus({ preventScroll: true }), 220);
}
function nextAfter(id) {
  const q = (S.invoices || []).filter(i => ["BLOCKED", "HELD"].includes(i.state) && !hiddenIds.has(i.id));
  const order = S.invoices.map(i => i.id), from = order.indexOf(id);
  return q.find(i => order.indexOf(i.id) > from) || q[0] || null;
}
async function commitPending(entry) {
  if (pending !== entry) return;
  pending = null; clearTimeout(entry.timer);
  try { await post(entry.path, entry.body); } catch (e) { snack(e.message); }
  hiddenIds.delete(entry.id);
  sigs.list = sigs.detail = sigs.view = "";
  await tick();
}
const flushPending = async () => { if (pending) await commitPending(pending); };
function undoPending(entry) {
  if (pending !== entry) return;
  clearTimeout(entry.timer); pending = null; hiddenIds.delete(entry.id); hideSnack();
  sigs.list = ""; go("review", entry.id);
}

/* Record sheet */
function digitRow(text, other, offset) {
  return h("span", { class: "digits", "aria-label": text }, [...text].map((c, i) => h("i", { class: c !== [...other][i] ? "diff" : "", "aria-hidden": "true", style: { animationDelay: reduced.matches ? "0ms" : `${(offset + i) * 40}ms` } }, c)));
}
async function openRecord(invoice, check) {
  let r;
  try { r = await get(`/api/record?invoice=${invoice}&check=${encodeURIComponent(check)}`); } catch { snack("That record is not available."); return; }
  const sheet = document.getElementById("sheet"), scrim = document.getElementById("scrim"), opener = document.activeElement;
  let release;
  const close = () => { leave(sheet); leave(scrim); release(); opener?.focus?.(); };
  const [label] = CHECKS[check] || [check];
  const compare = r.compare ? h("div", { class: "compare", "aria-label": "Invoice compared with vendor master" }, compareView(r.compare)) : null;
  const shown = r.compare ? (r.rows || []).filter(x => !["Account on invoice", "IFSC on invoice", "Bank account", "IFSC"].includes(x.label)).map(x => ({ ...x, hit: false })) : r.rows;
  const body = r.kind === "passage" ? h("div", { class: "rec passage" }, r.lines.map(l => h("div", { class: l.hit ? "hit" : "" }, l.text)))
    : h("div", { class: "rec" }, shown.map(x => h("div", { class: "rec-row" + (x.hit ? " hit" : "") }, h("span", {}, x.label.replace("basic_info.name", "Company name")), h("span", {}, human(x.value)))));
  sheet.replaceChildren(
    h("div", { class: "sheet-h" }, h("div", {}, h("div", { class: "label" }, label), h("h2", { class: "title", id: "sheet-title" }, r.title)), h("button", { class: "icon-btn", "aria-label": "Close", onclick: close, id: "sheetClose" }, icon("x"))),
    h("div", { class: "claim" }, tag(r.status, STATUS), h("p", {}, human(r.claim))), compare || "", body,
    h("div", { class: "source-line" }, icon("link", 15), h("span", {}, r.url ? h("a", { href: r.url, target: "_blank", rel: "noopener noreferrer" }, sourceLabel(r.url)) : sourceLabel(r.source))),
    h("div", { class: "source-line" }, icon("clock", 15), h("span", {}, `Retrieved ${day(r.retrieved)}`)));
  scrim.hidden = false; sheet.hidden = false; scrim.onclick = close; release = trap(sheet, close);
  document.getElementById("sheetClose").focus();
}
function showKeys() {
  const sheet = document.getElementById("sheet"), scrim = document.getElementById("scrim"), opener = document.activeElement;
  let release;
  const close = () => { leave(sheet); leave(scrim); release(); opener?.focus?.(); };
  const keys = [["J / K", "Next or previous invoice"], ["A", "Approve with a note"], ["R", "Reject with a reason"], ["C", "Recheck against the records"], ["N", "Next exception"], ["E", "Open the first evidence line"], ["Z", "Undo the last decision"], ["Ctrl+Enter", "Submit a note"], ["Esc", "Close"], ["?", "This list"]];
  sheet.replaceChildren(h("div", { class: "sheet-h" }, h("h2", { class: "title", id: "sheet-title" }, "Keyboard shortcuts"), h("button", { class: "icon-btn", "aria-label": "Close", onclick: close, id: "sheetClose" }, icon("x"))),
    h("div", { class: "keys" }, keys.map(([k, v]) => [h("kbd", { class: "key" }, k), h("span", {}, v)])));
  scrim.hidden = false; sheet.hidden = false; scrim.onclick = close; release = trap(sheet, close);
  document.getElementById("sheetClose").focus();
}
document.addEventListener("keydown", e => {
  if (e.ctrlKey || e.metaKey || e.altKey || !S) return;
  if (e.target.closest?.("input,textarea,select") || !document.getElementById("sheet").hidden || !document.getElementById("sign").hidden || !document.getElementById("who").hidden) return;
  const k = e.key.toLowerCase();
  if (k === "?") { e.preventDefault(); return showKeys(); }
  if (k === "z" && pending) { e.preventDefault(); return undoPending(pending); }
  if (route[0] !== "review") return;
  if (k === "j" || k === "k") {
    const list = shownInvoices(), at = list.findIndex(i => String(i.id) === route[1]);
    const next = list[k === "j" ? Math.min(list.length - 1, at + 1) : Math.max(0, at - 1)];
    if (next) { e.preventDefault(); go("review", next.id); }
    return;
  }
  if (k === "n") { const q = visibleNeeds(); const next = current ? nextAfter(current.id) : q[0]; if (next) { e.preventDefault(); go("review", next.id); } return; }
  if (!current || String(current.id) !== route[1]) return;
  if (k === "a" && current.state === "HELD" && current.can_approve) { e.preventDefault(); openDrawer(current, "approve"); }
  if (k === "r" && ["READY", "HELD", "BLOCKED"].includes(current.state)) { e.preventDefault(); openDrawer(current, "reject"); }
  if (k === "c" && ["READY", "HELD", "BLOCKED"].includes(current.state)) { e.preventDefault(); act("/api/recheck", { id: current.id }, "Rechecked against the records."); }
  if (k === "e") { e.preventDefault(); document.querySelector(".evidence .li")?.click(); }
});

/* Sign and release */
function renderDock() {
  const dock = document.getElementById("dock"), c = S.counts, p = S.payment_run, count = c.READY + c.APPROVED;
  const show = count > 0 && !S.job.running && route[0] === "review" && !route[1];
  const key = JSON.stringify([show, count, p.net, c.READY]);
  if (sigs.dock === key) return; sigs.dock = key;
  dock.classList.toggle("on", show);
  if (!show) return;
  dock.replaceChildren(h("div", { class: "dockbar" }, h("div", {}, h("b", {}, p.net), h("small", {}, `${plural(count, "invoice")} net of TDS`)),
    h("button", { class: "btn", onclick: openSign }, icon("draw", 20), c.READY ? "Review and sign" : "Issue payments")));
}
function openSign(e) {
  const from = e?.currentTarget, dlg = document.getElementById("sign");
  if (!from) return openSignNow();
  dlg.style.animation = "none";
  morphTo(from, openSignNow, () => document.getElementById("sign"));
  setTimeout(() => { dlg.style.animation = ""; }, 700);
}
function openSignNow() {
  const dlg = document.getElementById("sign"), scrim = document.getElementById("scrim"), p = S.payment_run, c = S.counts, opener = document.activeElement;
  let release;
  const close = () => { leave(dlg); leave(scrim); release(); opener?.focus?.(); };
  const nameInput = h("input", { class: "input", id: "bySign", autocomplete: "name", value: reviewer(), placeholder: "Your name", oninput: e => { store.set("chukta-reviewer", e.target.value.trim()); hold.disabled = !e.target.value.trim(); renderRail(); } });
  const finish = async () => {
    hold.disabled = true;
    try {
      await flushPending();
      const items = S.payment_run.lines.filter(l => l.state === "READY").map(l => ({ id: l.id, evidence: l.evidence }));
      if (items.length) await post("/api/signoff", { by: reviewer(), items });
      await post("/api/pay", { by: reviewer() });
      hold.classList.add("done"); hold.style.clipPath = shape("cookie"); hold.querySelector(".ms").replaceWith(icon("check", 40)); holdLabel.textContent = "Signed"; navigator.vibrate?.(12);
      setTimeout(async () => { close(); composerOpen = false; snack("Signed. Issuing each payment once."); sigs.view = ""; go("today"); await tick(); }, reduced.matches ? 80 : 720);
    } catch (e) { snack(e.message); hold.disabled = false; sigs.view = ""; tick(); }
  };
  const holdLabel = h("div", { class: "hold-label" }, "Touch and hold to sign");
  const hold = holdButton(`Sign and issue ${p.net}`, finish);
  hold.disabled = !reviewer();
  const open = c.BLOCKED + c.HELD;
  dlg.replaceChildren(h("div", { class: "sign-in" },
    h("div", { class: "sign-head" }, h("h2", { class: "title", id: "sign-title" }, "Sign this payment run"), h("p", { class: "body-s" }, shortClient()), h("button", { class: "icon-btn", "aria-label": "Close", onclick: close }, icon("x"))),
    money(p.net, "sign"),
    h("div", { class: "sign-sum" }, h("span", {}, h("b", {}, p.gross), "Gross"), h("span", {}, h("b", {}, p.tds), "TDS draft"), h("span", {}, h("b", {}, p.retained), "GST retained")),
    h("div", { class: "sign-list" }, p.lines.map(l => h("div", { class: "sign-row" }, h("span", {}, l.vendor, h("small", {}, `${l.number}${l.due ? ` · MSME pay by ${day(l.due)}` : ""}`)), h("b", {}, l.net)))),
    open ? h("p", { class: "body-s", style: { marginBottom: "12px", textAlign: "center" } }, `${plural(open, "exception")} stay${open === 1 ? "s" : ""} out of this run.`) : null,
    h("label", { class: "field" }, h("span", {}, "Reviewer"), nameInput),
    h("div", { class: "hold-wrap" }, hold, holdLabel, h("p", { class: "body-s", style: { textAlign: "center", fontSize: "12px" } }, `Issues payment requests in ${S.provider}. This can't be undone.`))));
  dlg.hidden = false; scrim.hidden = false; scrim.onclick = close; release = trap(dlg, close);
  (reviewer() ? hold : nameInput).focus();
}
function holdButton(label, onDone) {
  let timer = null, viaKey = false;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg"), ring = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  svg.setAttribute("viewBox", "0 0 108 108"); svg.setAttribute("aria-hidden", "true");
  ring.setAttribute("cx", "54"); ring.setAttribute("cy", "54"); ring.setAttribute("r", "52"); svg.append(ring);
  const btn = h("button", { class: "hold", type: "button", "aria-label": `${label}. Press and hold.` }, svg, icon("draw", 38));
  const begin = () => { if (btn.disabled || timer) return; btn.classList.add("holding"); timer = setTimeout(() => { timer = null; btn.classList.remove("holding"); onDone(); }, 1000); };
  const end = () => { if (timer) { clearTimeout(timer); timer = null; btn.classList.remove("holding"); snack("Keep holding to sign."); } };
  btn.addEventListener("pointerdown", e => { try { btn.setPointerCapture(e.pointerId); } catch { /* Not every pointer can be captured. */ } begin(); });
  btn.addEventListener("pointerup", end); btn.addEventListener("pointercancel", end);
  btn.addEventListener("keydown", e => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); viaKey = true; begin(); } });
  btn.addEventListener("keyup", e => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); end(); } });
  btn.addEventListener("blur", end);
  btn.addEventListener("click", e => { if (e.detail === 0 && !viaKey && !btn.disabled) onDone(); viaKey = false; }); // Assistive tech activates without a press.
  return btn;
}

/* Bank */
async function renderBank() {
  const data = await get("/api/statement").catch(() => null);
  if (!data || route[0] !== "bank") return;
  const key = "bank" + JSON.stringify([data.lines, S.job.running]);
  if (sigs.view === key || document.activeElement?.id === "stmt" || document.activeElement?.closest?.(".resolve")) return;
  sigs.view = key;
  const text = h("textarea", { class: "input mono", id: "stmt", rows: 4, "aria-label": "Statement lines", placeholder: "3 Oct 2026 · SWIGGY BANGALORE · ₹1,240", oninput: e => { bankDraft = e.target.value; } });
  text.value = bankDraft;
  const send = async body => { try { await post("/api/statement", body); bankDraft = ""; sigs.view = ""; await tick(); } catch (e) { snack(e.message); } };
  mount("bank", h("div", { class: "page" },
    appbar("Bank", [h("span", { class: "note-pill" }, icon("check", 16), `${data.posted} posted`), h("span", { class: "note-pill" }, icon("warn", 16), `${data.held} held`)], shortClient()),
    h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "4px" } }, "Post statement lines"),
      h("p", { class: "body-s", style: { marginBottom: "14px" } }, "A third of the Indian company names we sampled are shared, so a name alone never posts a line. It needs a payment Chukta issued, or a firm rule confirmed against the company's record."),
      text, h("div", { class: "actions" }, h("button", { class: "btn filled", disabled: S.job.running, onclick: () => send({ text: document.getElementById("stmt").value }) }, icon("play", 18), "Post lines"),
        h("button", { class: "btn tonal", disabled: S.job.running, onclick: () => send({ sample: true }) }, icon("receipt", 18), "Use October sample"))),
    data.lines.length ? h("section", { class: "group", style: { marginTop: "12px" }, "aria-label": "Statement lines" }, data.lines.map(lineRow)) : null));
}
function lineRow(l) {
  const payee = h("input", { class: "input", placeholder: "Payee", "aria-label": "Payee" }), account = h("input", { class: "input", placeholder: "Account", "aria-label": "Account" }), note = h("input", { class: "input", placeholder: "What confirmed this?", "aria-label": "Note" });
  return h("div", { class: "line" },
    h("span", { class: "sh " + l.status }, icon((STATUS[l.status] || [])[1] || "info", 18)),
    h("div", {}, h("div", { class: "title-s" }, l.narration), h("div", { class: "body-s" }, day(l.txn_date))),
    h("div", { class: "pay" }, l.payee ? h("div", {}, h("b", {}, l.payee), ` → ${l.account}`) : null, h("div", { class: "body-s" }, human(l.reason)), h("div", { class: "label", style: { fontWeight: 400, overflowWrap: "anywhere" } }, `${sourceLabel(l.source)} · ${day(l.retrieved_at)}`)),
    h("div", { style: { textAlign: "right" } }, h("div", { class: "num", style: { fontWeight: 600 } }, l.amount), h("div", { style: { marginTop: "4px" } }, tag(l.status, STATUS))),
    l.status === "HELD" ? h("details", { class: "resolve" }, h("summary", { style: { cursor: "pointer", fontWeight: 600 } }, "Settle this line"),
      h("div", { style: { marginTop: "10px", display: "grid", gap: "8px" } }, h("div", { class: "form-row" }, payee, account), note,
        h("div", { class: "actions", style: { marginTop: 0 } }, h("button", { class: "btn tonal", onclick: () => act("/api/line/resolve", { id: l.id, payee: payee.value, account: account.value, note: note.value }, "Posted, with your name on it.") }, "Post it"),
          h("button", { class: "btn text", onclick: () => act("/api/line/dismiss", { id: l.id, note: note.value }, "Dismissed, with your reason on file.") }, "Dismiss")))) : null);
}

/* Books */
const BOOKS_HELP = {
  vendors: ["Vendor master", "gstin,name,domain,account,ifsc,tds_class,msme,agreement_days", "New vendors start unverified. A CSV can never change an existing vendor's bank details.", "/api/books/vendors", r => `${plural(r, "vendor")} imported.`],
  pos: ["Purchase orders", "po,gstin,amount", "Each PO must belong to a vendor on the master.", "/api/books/pos", r => `${plural(r, "purchase order")} imported.`],
  gstr2b: ["GSTR-2B", '{"data":{"rtnprd":"102026","docdata":{"b2b":[...]}}}', "Paste the JSON from the GST portal. One bad record rejects the file.", "/api/books/gstr2b", r => `GSTR-2B for ${human(r[0])}: ${plural(r[1], "invoice")}.`],
};
async function renderBooks() {
  const d = await get("/api/books").catch(() => null);
  if (!d || route[0] !== "books") return;
  const key = "books" + JSON.stringify([d, booksKind]);
  if (sigs.view === key || document.activeElement?.id === "booksText") return;
  sigs.view = key;
  const [title, format, help, path, ok] = BOOKS_HELP[booksKind];
  const text = h("textarea", { class: "input mono", id: "booksText", rows: 5, "aria-label": `${title} data`, placeholder: format });
  const send = async () => { try { const r = await post(path, { text: text.value }); snack(ok(r.result)); text.value = ""; sigs.view = ""; await tick(); } catch (e) { snack(e.message); } };
  mount("books", h("div", { class: "page" },
    appbar("Books", null, shortClient()),
    h("section", { class: "stat-row", "aria-label": "Books" }, stat("Vendors", String(d.vendors.length), "On the master"), stat("Purchase orders", String(d.pos), "Open to match"), stat("GSTR-2B periods", String(d.periods.length), d.periods.map(human).join(", ") || "None imported"), stat("Bank changes", String(d.changes.length), "Two-person approval")),
    h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "10px" } }, "Bring in records"),
      h("div", { class: "chips", role: "group", "aria-label": "Record type", style: { marginBottom: "12px" } }, Object.entries(BOOKS_HELP).map(([k, v]) => h("button", { class: "chip", "aria-pressed": String(booksKind === k), onclick: () => { booksKind = k; sigs.view = ""; renderBooks(); } }, v[0]))),
      h("p", { class: "body-s", style: { marginBottom: "10px" } }, help), text, h("div", { class: "actions" }, h("button", { class: "btn filled", onclick: send }, icon("download", 18), `Import ${title.toLowerCase()}`))),
    h("section", { class: "card", style: { padding: "16px 12px" } }, h("h2", { class: "title", style: { margin: "0 12px 8px" } }, "Vendor master"),
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("thead", {}, h("tr", {}, ["Vendor", "GSTIN", "Domain", "Bank", "TDS", "MSME"].map(x => h("th", { scope: "col" }, x)))),
        h("tbody", {}, d.vendors.map(v => h("tr", {}, h("td", { style: { fontWeight: 600 } }, v.name), h("td", { class: "num" }, v.gstin), h("td", {}, v.domain), h("td", { class: "num" }, `${v.account} · ${v.ifsc}`), h("td", {}, v.tds_class || "Not set"), h("td", {}, v.msme || "Not known")))))))));
}

/* Audit: the finished work, the attacks, and the ledger */
const auditTabs = () => h("nav", { class: "tabs", "aria-label": "Audit views" }, [["", "Run sheet"], ["drills", "Break it"], ["ledger", "Ledger"]].map(([id, label]) =>
  h("a", { href: "#/audit" + (id ? "/" + id : ""), "aria-current": (route[1] || "") === id ? "page" : null }, label)));
const auditPage = (kind, ...body) => mount("audit-" + kind, h("div", { class: "page" }, appbar("Audit", null, shortClient()), auditTabs(), ...body));
const exportRow = (href, ic, title, text) => h("a", { class: "export", href, download: "" }, h("span", { class: "sh" }, icon(ic, 22)), h("span", {}, h("b", {}, title), h("span", { class: "body-s" }, text)), icon("download", 22));
const nil = amount => amount === "₹0.00" ? "Nil" : amount;
const stat = (a, b, c) => h("div", { class: "stat" }, h("span", {}, a), h("b", {}, b), h("small", {}, c));
const SOURCE_NAMES = { crustdata: "Crustdata", ifsc: "IFSC registry", model: "Model (DeepSeek)", razorpay_test: "Razorpay test mode" };
const outcomeText = o => /^20\d$/.test(String(o)) ? "OK" : o === "429" ? "Rate limited, retried" : /^\d{3}$/.test(String(o)) ? `Error ${o}` : String(o).replace("error:", "Failed: ");
const requestText = r => String(r).replace("/company/identify", "Company lookup").replace("/company/search", "Company status").replace("POST /v1/payment_links", "Payment request").replace("GET /v1/payment_links", "Payment lookup").replace("deepseek/deepseek-v4.1-flash", "Read invoice").replace("investigator", "Look into exception").replace(/^ifsc$/, "Branch lookup");

async function renderAudit() {
  if (route[1] === "ledger") return renderLedger();
  if (route[1] === "drills") return renderDrills();
  const d = await get("/api/replay").catch(() => null);
  if (!d || route[0] !== "audit" || route[1]) return;
  const open = S.invoices.filter(i => ["BLOCKED", "HELD"].includes(i.state));
  const key = "sheet" + JSON.stringify([d, open.map(i => [i.id, i.check])]);
  if (sigs.view === key) return; sigs.view = key;
  if (!d.lines.length) return auditPage("sheet", h("section", { class: "card" }, h("div", { class: "empty", style: { minHeight: "320px" } }, shaped("sh", "cookie", icon("receipt", 44)), h("div", { class: "title" }, "No run signed yet"), h("p", { class: "body-s" }, "The signed run sheet appears here, ready to print."), h("a", { class: "btn tonal", href: "#/today" }, "Go to Today"))));
  const signers = [...new Set(d.lines.map(l => l.signed_by))].join(", ");
  const check = async () => { sigs.view = ""; const again = await get("/api/replay"); snack(again.ok ? `Checked ${plural(again.lines.length, "payment")} against sign-off, evidence, provider and hash chain. All clean.` : again.problems[0]); renderAudit(); };
  auditPage("sheet",
    h("section", { class: "sheet-doc" },
      h("div", { class: "doc-head" }, h("div", {}, h("h2", { class: "headline" }, "Payment run sheet"), h("p", { class: "body-s" }, `${S.client} · ${longDate()}`), h("p", { class: "body-s" }, `Signed by ${signers}`)),
        h("div", { class: "bar-end" }, h("span", { class: "tag " + (d.ok ? "pass" : "fail") }, icon(d.ok ? "verified" : "warn", 16), d.ok ? "Replay clean" : "Replay failed"),
          h("button", { class: "icon-btn no-print", "aria-label": "Check again", title: "Check again", onclick: check }, icon("refresh")), h("button", { class: "icon-btn no-print", "aria-label": "Print", title: "Print", onclick: () => print() }, icon("print")))),
      d.ok ? null : h("p", { style: { color: "var(--md-error)", marginBottom: "12px" } }, d.problems[0]),
      h("div", { class: "table-wrap" }, h("table", { class: "table" },
        h("thead", {}, h("tr", {}, ["Payee", "Account", "Gross", "TDS", "GST held", "Net", "Reference"].map((x, i) => h("th", { class: i > 1 && i < 6 ? "r" : "", scope: "col" }, x)))),
        h("tbody", {}, d.lines.map(l => h("tr", {}, h("td", {}, h("span", { style: { fontWeight: 500 } }, l.payee), h("small", {}, `${l.number}${l.due ? ` · MSME by ${day(l.due)}` : ""}`)), h("td", { class: "num", style: { whiteSpace: "nowrap" } }, l.account, h("small", {}, l.ifsc)),
          h("td", { class: "r" }, l.gross), h("td", { class: "r" }, nil(l.tds)), h("td", { class: "r" }, nil(l.retained)), h("td", { class: "r", style: { fontWeight: 500 } }, l.net), h("td", { style: { overflowWrap: "anywhere" } }, l.reference || (l.state === "APPROVED" ? "Not issued yet" : ""))))),
        h("tfoot", {}, h("tr", {}, h("td", { colspan: 2 }, plural(d.lines.length, "payment")), h("td", { class: "r" }, d.totals.gross), h("td", { class: "r" }, nil(d.totals.tds)), h("td", { class: "r" }, nil(d.totals.retained)), h("td", { class: "r" }, d.totals.net), h("td", {}))))),
      h("div", { class: "doc-foot" },
        h("div", {}, h("div", { class: "title-s", style: { marginBottom: "6px" } }, "TDS to deposit (draft)"), d.tds_by_section.length ? d.tds_by_section.map(x => h("div", { class: "kv" }, h("span", {}, x.section), h("b", {}, x.amount))) : h("p", { class: "body-s" }, "None in this run.")),
        h("div", {}, h("div", { class: "title-s", style: { marginBottom: "6px" } }, `Left out of this run (${open.length})`), open.length ? open.map(i => h("div", { class: "kv" }, h("span", {}, `${i.vendor} · ${problem(i.check)}`), h("b", {}, i.gross))) : h("p", { class: "body-s" }, "Nothing.")))),
    h("div", { class: "sec no-print" }, "Downloads"),
    h("div", { class: "group no-print" }, exportRow("/export/bank.csv", "bank", "Bank file", "Beneficiary, mode, amount, reference"), exportRow("/export/tally.csv", "receipt", "Tally vouchers", "Taxable, GST, TDS and net"), exportRow("/export/audit.json", "shield", "Audit file", "Every decision, source and call")));
}
function renderDrills() {
  const key = "drills" + JSON.stringify([drillResult, drillBusy]);
  if (sigs.view === key) return; sigs.view = key;
  const run = async () => {
    drillBusy = true; renderDrills();
    try { drillResult = await post("/api/drills"); } catch (e) { snack(e.message); }
    drillBusy = false; sigs.view = ""; renderDrills();
    if (drillResult?.passed === drillResult?.total) setTimeout(() => celebrate(document.querySelector(".hero .stamp")), 120);
  };
  const r = drillResult;
  auditPage("drills",
    h("section", { class: "hero " + (r && r.passed === r.total ? "good" : r ? "" : "quiet"), style: { marginBottom: "12px" } },
      r && r.passed === r.total ? shaped("stamp", "cookie", icon("verified", 34)) : null,
      h("div", { class: "kicker" }, r ? "Attacks stopped" : "Try to break it"),
      r ? h("div", { class: "amount" }, `${r.passed} of ${r.total}`) : h("div", { class: "headline", style: { margin: "4px 0" } }, "Nine ways this could lose a client's money"),
      h("div", { class: "sub", style: { maxWidth: "620px" } }, "Runs the real decision and payment code on a private copy of the sample books. Your books, credits and Razorpay are not touched."),
      h("div", { class: "actions" }, h("button", { class: "btn filled", disabled: drillBusy, onclick: run }, icon("play", 22), drillBusy ? "Running" : r ? "Run again" : "Run all attacks"))),
    r ? h("div", { class: "group" }, r.drills.map((x, i) => h("div", { class: "drill" + (x.held ? "" : " bad"), style: { animationDelay: `${i * 80}ms` } },
      shaped("sh", x.held ? "cookie" : "burst", icon(x.held ? "check" : "x", 22)), h("div", {}, h("b", {}, x.attack), h("div", { class: "body-s" }, x.outcome)), h("span", { class: "tag " + (x.held ? "pass" : "fail") }, icon(x.held ? "check" : "x", 15), x.held ? "Stopped" : "Failed")))) : null);
}
async function renderLedger() {
  const d = await get("/api/ledger").catch(() => null);
  if (!d || route[1] !== "ledger") return;
  const key = "ledger" + JSON.stringify([d.total_calls, d.credits, d.usd]);
  if (sigs.view === key) return; sigs.view = key;
  const max = Math.max(1, ...d.by_source.map(s => s.calls));
  auditPage("ledger",
    h("section", { class: "stat-row", "aria-label": "Totals" }, stat("Credits per invoice", String(d.per_invoice_credits), plural(d.invoices, "invoice")), stat("Model cost per invoice", `$${d.per_invoice_usd.toFixed(5)}`, "DeepSeek V4.1 Flash"), stat("Total credits", String(d.credits), "Crustdata"), stat("Calls recorded", String(d.total_calls), "Every source")),
    d.total_calls ? [h("div", { class: "two" },
      h("section", { class: "card" }, h("h2", { class: "title-s", style: { marginBottom: "14px" } }, "Calls by source"), d.by_source.map(s => h("div", { class: "meter" },
        h("div", { class: "meter-h" }, h("span", {}, SOURCE_NAMES[s.source] || s.source), h("b", {}, `${s.calls} calls${s.credits ? ` · ${s.credits} cr` : ""}${s.usd ? ` · $${s.usd}` : ""}`)),
        h("div", { class: "track" }, h("i", { style: { width: s.calls / max * 100 + "%" } }))))),
      d.run ? h("section", { class: "card" }, h("h2", { class: "title-s", style: { marginBottom: "14px" } }, "Latest run against its ceiling"),
        meter("Crustdata credits", d.run.credits, d.run.credit_limit, `${d.run.credits} of ${d.run.credit_limit}`),
        meter("Model spend", d.run.usd, d.run.model_usd_limit, `$${d.run.usd.toFixed(4)} of $${d.run.model_usd_limit.toFixed(2)}`),
        h("p", { class: "body-s" }, `Time limit ${Math.round(d.run.time_limit_s / 60)} minutes. At a ceiling, Chukta holds what it cannot check.`)) : null),
    h("section", { class: "card", style: { marginTop: "12px", padding: "20px 12px" } }, h("h2", { class: "title-s", style: { margin: "0 12px 8px" } }, "Every call"),
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("thead", {}, h("tr", {}, ["When", "Source", "What", "Result", "Credits", "Model $"].map((x, i) => h("th", { class: i > 3 ? "r" : "", scope: "col" }, x)))),
        h("tbody", {}, d.calls.slice(0, 60).map(c => h("tr", {}, h("td", { style: { whiteSpace: "nowrap" } }, stamp(c.at)), h("td", {}, SOURCE_NAMES[c.source] || c.source), h("td", {}, requestText(c.request)), h("td", {}, outcomeText(c.outcome)), h("td", { class: "r" }, c.credits ? String(c.credits) : "0"), h("td", { class: "r" }, c.usd ? c.usd.toFixed(5) : "0")))))))]
      : h("section", { class: "card" }, h("div", { class: "empty", style: { minHeight: "240px" } }, shaped("sh", "soft", icon("receipt", 40)), h("div", { class: "title" }, "No calls yet"), h("p", { class: "body-s" }, "Every source call and its cost will appear here."))));
}

/* Motion */
function stagger(root) {
  if (reduced.matches) return;
  root.querySelectorAll(".bar,.tabs,.hero,.live,.ask-card,.sheet-doc,.card,.stat,details.fold,.sec,.list-group,.group > :not(.drill)").forEach((el, i) => { el.style.setProperty("--i", Math.min(i, 16)); el.classList.add("in"); });
}
function morphTo(from, update, target) {
  if (!document.startViewTransition || reduced.matches || !from) return update();
  from.style.viewTransitionName = "morph";
  const t = document.startViewTransition(() => { from.style.viewTransitionName = ""; const done = update(); const to = target(); if (to) to.style.viewTransitionName = "morph"; return done; });
  t.finished.finally(() => { const to = target(); if (to) to.style.viewTransitionName = ""; });
}
function leave(el) {
  if (reduced.matches || el.hidden) { el.hidden = true; return; }
  el.animate([{ opacity: 1 }, { opacity: 0, transform: el.id === "scrim" ? "none" : "translateY(14px) scale(.98)" }], { duration: 170, easing: "cubic-bezier(.3,0,1,1)" }).finished.finally(() => { el.hidden = true; });
}
async function sweep(id) {
  const row = document.querySelector(`#listPane .row[data-id="${id}"]`);
  if (!row || reduced.matches) return;
  await row.animate([{ opacity: 1, transform: "none", maxHeight: row.offsetHeight + "px", minHeight: "0" }, { opacity: 0, transform: "translateX(64px) scale(.96)", maxHeight: "0px", minHeight: "0", paddingTop: 0, paddingBottom: 0 }], { duration: 260, easing: "cubic-bezier(.3,0,.2,1)", fill: "forwards" }).finished.catch(() => {});
}
function celebrate(anchor) {
  if (reduced.matches || !anchor) return;
  const box = anchor.getBoundingClientRect(), x = box.left + box.width / 2, y = box.top + box.height / 2;
  const colors = ["--md-primary", "--md-tertiary", "--md-success", "--md-warning", "--md-secondary"], kinds = ["cookie", "clover", "soft", "burst", "circle"];
  for (let n = 0; n < 34; n++) {
    const size = 8 + Math.random() * 18, angle = n / 34 * Math.PI * 2 + Math.random() * .4, reach = 110 + Math.random() * 260;
    const bit = h("i", { class: "bit", style: { left: x - size / 2 + "px", top: y - size / 2 + "px", width: size + "px", height: size + "px", background: `var(${colors[n % colors.length]})`, clipPath: shape(kinds[n % kinds.length]) } });
    document.body.append(bit);
    const dx = Math.cos(angle) * reach, dy = Math.sin(angle) * reach;
    bit.animate([{ transform: "translate(0,0) scale(.2) rotate(0)", opacity: 1 }, { transform: `translate(${dx * .78}px,${dy * .78}px) scale(1) rotate(${200 + n * 11}deg)`, opacity: 1, offset: .55 }, { transform: `translate(${dx}px,${dy + 130}px) scale(.3) rotate(${420 + n * 17}deg)`, opacity: 0 }],
      { duration: 1000 + Math.random() * 600, easing: "cubic-bezier(.12,.7,.3,1)", delay: Math.random() * 90 }).finished.finally(() => bit.remove());
  }
}

/* Loop */
function renderView() {
  if (route[0] === "review") return renderReview();
  if (route[0] === "bank") return renderBank();
  if (route[0] === "books") return renderBooks();
  if (route[0] === "audit") return renderAudit();
  return renderToday();
}
function setOnline(on) {
  if (on === online) return;
  online = on;
  document.body.classList.toggle("offline", !on);
  const bar = document.getElementById("offline");
  bar.hidden = on;
  if (!on) bar.replaceChildren(icon("off", 18), "Chukta is not responding. Restart it and the work resumes.");
}
async function tick() {
  clearTimeout(pollTimer);
  try {
    S = await get("/api/state");
    setOnline(true);
    const need = S.counts.BLOCKED + S.counts.HELD;
    if (need > startedExceptions) startedExceptions = need;
    if (!S.invoices.length) startedExceptions = 0;
    document.title = need ? `(${need}) Chukta` : "Chukta";
    renderRail(); await renderView(); renderDock();
    if (S.job.error && sigs.err !== S.job.error) { sigs.err = S.job.error; snack(S.job.error); }
  } catch { setOnline(false); }
  pollTimer = setTimeout(tick, S?.job?.running ? 450 : 3000);
}
document.documentElement.style.setProperty("--cookie", shape("cookie"));
onRoute();
tick();
