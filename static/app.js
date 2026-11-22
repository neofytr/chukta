"use strict";
/* Chukta reviewer app. Plain DOM, one polling loop, and every value rendered as text. */

const ICONS = {
  today: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z M19 16l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z",
  inbox: "M4 13l2.6-7.2A2 2 0 0 1 8.5 4.5h7a2 2 0 0 1 1.9 1.3L20 13v5a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-5z M4 13h4.5l1.5 2.5h4l1.5-2.5H20",
  bank: "M3 10l9-6 9 6 M5 10v8 M10 10v8 M14 10v8 M19 10v8 M3 20h18",
  receipt: "M6 3h12v18l-3-2-3 2-3-2-3 2V3z M9 8h6 M9 12h6",
  shield: "M12 3l7.5 3v5.5c0 4.6-3.1 8-7.5 9.5-4.4-1.5-7.5-4.9-7.5-9.5V6L12 3z M8.8 12l2.2 2.2 4.4-4.6",
  shieldx: "M12 3l7.5 3v5.5c0 4.6-3.1 8-7.5 9.5-4.4-1.5-7.5-4.9-7.5-9.5V6L12 3z M9.5 9.5l5 5 M14.5 9.5l-5 5",
  plus: "M12 5v14 M5 12h14",
  palette: "M12 3a9 9 0 1 0 0 18c1.2 0 2-.8 2-1.8 0-.5-.2-.9-.5-1.3-.3-.4-.5-.8-.5-1.3 0-1 .8-1.6 1.8-1.6H17a4 4 0 0 0 4-4c0-4.4-4-8-9-8z M7.5 11.5h.01 M10 7.5h.01 M14.5 7.5h.01 M17 11h.01",
  moon: "M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z M12 2v2 M12 20v2 M4.9 4.9l1.4 1.4 M17.7 17.7l1.4 1.4 M2 12h2 M20 12h2 M4.9 19.1l1.4-1.4 M17.7 6.3l1.4-1.4",
  check: "M5 12.5l4.5 4.5L19 7.5", x: "M6 6l12 12 M18 6L6 18", chevron: "M9 6l6 6-6 6", back: "M19 12H5 M11 6l-6 6 6 6", arrow: "M5 12h14 M13 6l6 6-6 6",
  warn: "M12 4l9 16H3L12 4z M12 10v4 M12 17.5h.01", info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 11v5 M12 8h.01",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3.5 2",
  phone: "M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z",
  doc: "M7 3h7l5 5v11a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M14 3v5h5 M9 13h6 M9 17h6",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1 M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  download: "M12 4v11 M7 11l5 5 5-5 M5 20h14",
  refresh: "M20 11a8 8 0 0 0-14.3-4.3L4 9 M4 4v5h5 M4 13a8 8 0 0 0 14.3 4.3L20 15 M20 20v-5h-5",
  play: "M8 5.5v13l10.5-6.5L8 5.5z",
  lock: "M7 11V8a5 5 0 0 1 10 0v3 M6 11h12a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-8a1 1 0 0 1 1-1z",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M5 20a7 7 0 0 1 14 0",
  building: "M5 21V5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v16 M16 9h3a1 1 0 0 1 1 1v11 M3 21h18 M9 7h3 M9 11h3 M9 15h3",
  percent: "M19 5L5 19 M7.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z M16.5 18a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z",
  mail: "M4 6h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1z M3.5 7l8.5 6 8.5-6",
  copy: "M9 9h10a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V10a1 1 0 0 1 1-1z M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1",
  cart: "M4 5h2l2 11h10l2-8H7 M9 20h.01 M17 20h.01", hash: "M5 9h15 M4 15h15 M10 4L8 20 M16 4l-2 16",
  agent: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M20 20l-4-4 M11 8l.9 2.1L14 11l-2.1.9L11 14l-.9-2.1L8 11l2.1-.9z",
  rupee: "M7 5h10 M7 9h10 M10 5c3.8 0 5 2 5 4s-1.8 4-5 4H7l7 7", paste: "M9 4h6v3H9z M8 5H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-2",
  history: "M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5 M12 8v4l3 2", books: "M5 4h4v16H5z M10 4h4v16h-4z M16 5l3.5 1-3.5 14.5-3-1",
  note: "M5 4h14v11l-5 5H5V4z M14 20v-5h5 M8 9h8 M8 12h4", keys: "M4 7h16a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z M7 11h.01 M11 11h.01 M15 11h.01 M8 14.5h8",
  off: "M4 4l16 16 M8.5 16.5a5 5 0 0 1 7 0 M5 12.5a10 10 0 0 1 5-2.7 M19 12.5a10 10 0 0 0-3.5-2.3 M12 20h.01",
};
const CHECKS = {
  required: ["Invoice fields", "doc"], document: ["Document", "doc"], invoice_date: ["Invoice date", "clock"], buyer: ["Billed to", "building"], gstin: ["GSTIN", "hash"], vendor: ["Vendor master", "building"],
  duplicate: ["Duplicate", "copy"], near_duplicate: ["Possible duplicate", "copy"], po: ["Purchase order", "cart"], bank: ["Bank details", "bank"], bank_request: ["Bank change request", "warn"],
  ifsc: ["IFSC registry", "bank"], gst: ["GSTR-2B", "receipt"], credit: ["GST credit clock", "clock"], einvoice: ["E-invoice", "doc"], sender: ["Sender", "mail"], company: ["Company record", "building"],
  msme: ["MSME deadline", "clock"], tds: ["TDS draft", "percent"], instruction: ["Your instruction", "note"], internal: ["System", "info"], payment_conflict: ["Payment", "rupee"], payment: ["Payment provider", "rupee"], master_changed: ["Changed fact", "warn"],
};
const STATES = { BLOCKED: ["Blocked", "shieldx"], HELD: ["Held", "warn"], READY: ["Ready", "check"], APPROVED: ["Signed", "lock"], PAID: ["Issued", "check"], REJECTED: ["Rejected", "x"], NEW: ["Checking", "clock"] };
const STATUS = { pass: ["Verified", "check"], fail: ["Failed", "x"], unverified: ["Can't verify", "info"], info: ["Note", "info"], POSTED: ["Posted", "check"], HELD: ["Held", "warn"], REJECTED: ["Dismissed", "x"] };
const SHAPE_OF = { READY: "circle", HELD: "soft", BLOCKED: "burst", APPROVED: "clover", PAID: "cookie", REJECTED: "circle", NEW: "soft" };
const SEEDS = { forest: ["#2f6b52", "#b3f0d0", "#a6cdb9"], bay: ["#3a5f9f", "#d6e3ff", "#bcc7dc"], peony: ["#8f4a60", "#ffd9e2", "#e3bdc6"], marigold: ["#7a5a17", "#ffdea8", "#d9c4a0"] };
const NAV = [["today", "Today", "today"], ["review", "Review", "inbox"], ["bank", "Bank", "bank"], ["books", "Books", "books"], ["ledger", "Ledger", "receipt"], ["audit", "Audit", "shield"]];
const FILTERS = { needs: ["Needs you", ["BLOCKED", "HELD"]], ready: ["Ready", ["READY", "APPROVED"]], issued: ["Issued", ["PAID"]], all: ["All", Object.keys(STATES)] };
const GROUPS = [["Needs your decision", ["BLOCKED", "HELD"]], ["Ready to sign", ["READY"]], ["Signed, waiting to issue", ["APPROVED"]], ["Payment requests issued", ["PAID"]], ["Rejected", ["REJECTED"]], ["Checking", ["NEW"]]];

let S = null, route = ["today"], filter = "needs", sigs = {}, composerOpen = false, useSample = true, draft = null, pollTimer = null, online = true;
let mounted = "", busyMorph = null, railRefs = null, current = null, drawerKind = null, pending = null, bankDraft = "", booksKind = "vendors", startedExceptions = 0;
const hiddenIds = new Set();
const reduced = matchMedia("(prefers-reduced-motion: reduce)");

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
function icon(name, size = 22) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("width", size); svg.setAttribute("height", size); svg.setAttribute("aria-hidden", "true"); svg.classList.add("ic");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", ICONS[name] || ICONS.info); svg.append(path);
  return svg;
}
function shape(kind) {
  const pts = [], n = 120;
  const radius = { circle: () => 1, soft: a => .93 + .07 * Math.cos(5 * a), cookie: a => .9 + .1 * Math.cos(9 * a), clover: a => .8 + .2 * Math.cos(4 * a), burst: a => .84 + .16 * Math.cos(12 * a), pebble: a => .9 + .07 * Math.cos(3 * a + 1) + .03 * Math.cos(5 * a) }[kind];
  for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2, r = radius(a) * 50; pts.push(`${(50 + r * Math.cos(a)).toFixed(2)}% ${(50 + r * Math.sin(a)).toFixed(2)}%`); }
  return `polygon(${pts.join(",")})`;
}
const shaped = (cls, kind, ...kids) => h("span", { class: cls, style: { clipPath: shape(kind) } }, ...kids);
const tag = (key, map = STATES) => h("span", { class: "tag " + key }, icon((map[key] || [key, "info"])[1], 15), (map[key] || [key])[0]);
const avatar = (name, state) => h("span", { class: "avw" }, shaped("av", SHAPE_OF[state] || "circle", name[0].toUpperCase()), h("span", { class: "pip " + state, title: (STATES[state] || [state])[0] }, icon((STATES[state] || [])[1] || "info", 11)));
function money(text) {
  const m = /^(.*)(\.\d\d)$/.exec(text || "");
  return m ? h("span", { class: "amount num" }, m[1], h("small", {}, m[2])) : h("span", { class: "amount missing" }, "Amount missing");
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
      h("div", { class: "brand", style: { clipPath: shape("cookie") }, "aria-hidden": "true" }, "च"),
      h("button", { class: "fab", "aria-label": "New run", title: "New run", onclick: () => { composerOpen = true; go("today"); sigs.view = ""; renderView(); } }, icon("plus", 26)),
      ...NAV.map(([id, label, ic]) => { const a = h("a", { class: "dest", href: "#/" + id }, h("span", { class: "pill" }, icon(ic)), id === "review" ? railRefs.badge : null, label); railRefs.dests[id] = a; return a; }),
      h("div", { class: "rail-end" }, h("button", { class: "icon-btn", "aria-label": "Keyboard shortcuts", title: "Keyboard shortcuts (?)", onclick: showKeys }, icon("keys")),
        h("button", { class: "icon-btn", "aria-label": "Reviewer and theme", title: "Reviewer and theme", "aria-haspopup": "true", onclick: toggleMenu }, railRefs.me)));
  }
  for (const [id, a] of Object.entries(railRefs.dests)) { if (route[0] === id) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); }
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
  if (!NAV.some(n => n[0] === route[0])) route = ["today"];
  drawerKind = null;
  sigs.detail = "";
  if (before[0] !== route[0]) { sigs.view = ""; sigs.list = ""; }
  if (S) { renderRail(); renderView(); renderDock(); }
}
addEventListener("hashchange", onRoute);
function mount(type, node) {
  if (mounted === type) node.style.animation = "none";
  mounted = type;
  document.getElementById("view").replaceChildren(node);
}

/* Today */
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
    { title: "Check against independent records", note: "GST, PO, vendor, bank, IFSC and company", st: pos(1) },
    { title: "Investigate exceptions", note: past ? (ex ? plural(ex, "exception") + " explained" : "None open") : "Read-only agent, citations checked", st: pos(2) },
    { title: "Your sign-off", note: signNote, st: signSt },
    { title: "Issue each payment request once", note: c.PAID ? `${c.PAID} issued in ${S.provider}` : S.provider, st: stage === "paying" ? "active" : c.PAID && !c.APPROVED ? "done" : c.APPROVED ? "need" : "todo" },
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
const promise = (ic, title, text) => h("div", { class: "promise" }, shaped("sh", "soft", icon(ic)), h("div", {}, h("div", { class: "title-s" }, title), h("p", { class: "body-s" }, text)));
function composer() {
  if (draft === null) draft = S.sample_request;
  const pasted = h("textarea", { class: "input mono", id: "pasteText", "aria-label": "Invoice text", placeholder: "Paste invoices or emails. Separate them with a line containing only ---. Use fictional data." });
  const box = h("div", { class: "paste", hidden: useSample }, pasted);
  const sampleChip = h("button", { class: "chip", "aria-pressed": String(useSample), onclick: () => choose(true) }, icon("receipt", 18), `This week's ${S.sample_count} sample invoices`);
  const pasteChip = h("button", { class: "chip", "aria-pressed": String(!useSample), onclick: () => choose(false) }, icon("paste", 18), "Paste an unseen invoice");
  function choose(sample) { useSample = sample; sampleChip.setAttribute("aria-pressed", String(sample)); pasteChip.setAttribute("aria-pressed", String(!sample)); box.hidden = sample; if (!sample) pasted.focus(); }
  const ask = h("textarea", { class: "ask", "aria-label": "What should Chukta do?", rows: 4, oninput: e => { draft = e.target.value; } });
  ask.value = draft;
  const start = h("button", { class: "btn filled lg", onclick: async () => {
    try {
      await post("/api/run", { request: ask.value, ...(useSample ? { sample: true } : { text: pasted.value }) });
      composerOpen = false; sigs.view = ""; await tick();
    } catch (e) { snack(e.message); }
  } }, icon("play", 22), "Start the job");
  return h("div", { class: "page" },
    h("section", { class: "composer" }, shaped("blob b1", "cookie"), shaped("blob b2", "clover"),
      h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "sr" }, "New request"), ask),
      h("div", {}, h("div", { class: "composer-foot" }, h("div", { class: "chips" }, sampleChip, pasteChip), start), box)),
    h("section", { class: "promises", "aria-label": "How Chukta works" },
      promise("shield", "An invoice is never its own proof", "Every claim must agree with a record the sender does not control."),
      promise("lock", "A person signs every payment", "Your sign-off freezes the payee and the amount before anything moves."),
      promise("refresh", "Each payment happens once", "Stop it at any moment. It carries on where it stopped.")));
}
function renderToday() {
  if (composerOpen || !S.run) {
    if (sigs.view !== "composer") { sigs.view = "composer"; mount("composer", composer()); }
    return;
  }
  const key = "run" + JSON.stringify([S.run, S.counts, S.job, S.audit_problems, S.issued]);
  if (sigs.view === key) return; sigs.view = key;
  const c = S.counts, r = S.run, ex = c.BLOCKED + c.HELD, busy = S.job.running, cleared = c.READY + c.APPROVED + c.PAID;
  const complete = !busy && c.PAID > 0 && !c.READY && !c.APPROVED;
  const headline = busy ? S.job.message : complete && !ex ? "Payment run complete" : complete ? `${plural(c.PAID, "payment request")} issued. ${ex} open` : c.READY || ex ? `${c.READY} ready to sign, ${ex} need you` : "Nothing is waiting";
  const sub = busy ? S.job.name : complete ? `${S.issued} issued once, in ${S.provider}.` : ex ? "Each exception has a reason and a source." : "Sign when you are ready.";
  if (!busy) busyMorph = null;
  const morph = busy ? (busyMorph ||= morphing(shaped("morph", "soft", h("span", { style: { display: "grid" } }, icon("agent", 30)))))
    : shaped("morph", complete && !ex ? "cookie" : "clover", h("span", { style: { display: "grid" } }, icon(complete && !ex ? "check" : "inbox", 30)));
  const parts = [["s", cleared, "Cleared", "check", "ready"], ["w", c.HELD, "Held", "warn", "needs"], ["e", c.BLOCKED, "Blocked", "shieldx", "needs"], ["n", c.REJECTED, "Rejected", "x", "all"]];
  const page = h("div", { class: "page" },
    h("header", { class: "top" }, h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "headline" }, "This week's payment run")), h("span", { class: "pill-note" }, h("span", { class: "dot" }), S.provider)),
    h("div", { class: "run-grid" },
      h("div", {},
        h("section", { class: "hero " + (complete && !ex ? "good" : "") },
          h("div", { class: "hero-top" }, morph, h("div", { style: { flex: 1, minWidth: 0 } }, h("h2", { class: "headline" }, headline), h("p", { class: "body-s" }, sub)),
            !busy && ex ? h("a", { class: "btn filled", href: "#/review", onclick: () => { filter = "needs"; } }, `Review ${ex}`, icon("arrow", 18)) : null),
          S.invoices.length ? [h("div", { class: "segbar", role: "img", "aria-label": parts.filter(p => p[1]).map(p => `${p[1]} ${p[2]}`).join(", ") }, parts.filter(p => p[1]).map(p => h("i", { class: p[0], style: { flexGrow: p[1] } }))),
            h("div", { class: "legend" }, parts.filter(p => p[1]).map(p => h("a", { href: "#/review", onclick: () => { filter = p[4]; sigs.list = ""; } }, icon(p[3], 16), h("b", {}, String(p[1])), p[2])))] : null),
        h("section", { class: "card" }, h("div", { class: "card-h" }, h("h2", { class: "title" }, "What you asked for"), h("button", { class: "btn text", onclick: () => { composerOpen = true; draft = r.request; sigs.view = ""; renderView(); } }, icon("plus", 18), "New run")),
          h("p", { class: "quote" }, r.request),
          h("p", { class: "body-s", style: { marginTop: "12px" } }, h("b", {}, "Finished work: "), r.understood.finished),
          r.understood.notes.map(n => h("p", { class: "body-s", style: { marginTop: "6px" } }, n)))),
      h("div", {},
        h("section", { class: "card", "aria-label": "Plan" }, h("div", { class: "card-h" }, h("h2", { class: "title" }, "The plan")),
          h("ol", { class: "steps" }, stepsFor().map((s, i) => h("li", { class: "step " + s.st, "aria-current": s.st === "active" ? "step" : null },
            h("span", { class: "st" }, s.st === "done" ? icon("check", 18) : s.st === "need" ? icon("user", 18) : String(i + 1)),
            h("div", {}, h("div", { class: "title-s" }, s.title), h("div", { class: "body-s" }, s.note),
              s.st === "active" ? h("div", { class: "wave", style: s.pct !== undefined ? { width: Math.max(8, s.pct * 100) + "%" } : null }, wave()) : null))))),
        h("section", { class: "card" }, h("div", { class: "card-h" }, h("h2", { class: "title" }, "This run's ceiling")),
          meter("Crustdata credits", r.credits, r.credit_limit, `${r.credits} of ${r.credit_limit}`),
          meter("Model spend", r.usd, r.model_usd_limit, `$${r.usd.toFixed(4)} of $${r.model_usd_limit.toFixed(2)}`),
          h("p", { class: "body-s" }, `Time limit ${Math.round(r.time_limit_s / 60)} minutes. ${plural(r.calls, "call")} in the ledger.`)))));
  mount("today", page);
}
const meter = (name, used, limit, text) => h("div", { class: "meter" }, h("div", { class: "meter-h" }, h("span", {}, name), h("b", {}, text)),
  h("div", { class: "track", role: "img", "aria-label": `${name}: ${text}` }, used > 0 ? h("i", { style: { width: Math.max(1, Math.min(100, limit ? used / limit * 100 : 0)) + "%" } }) : null));

/* Review */
const visibleNeeds = () => (S?.invoices || []).filter(i => ["BLOCKED", "HELD"].includes(i.state) && !hiddenIds.has(i.id));
const shownInvoices = () => S.invoices.filter(i => FILTERS[filter][1].includes(i.state) && !hiddenIds.has(i.id));
function renderReview() {
  const v = document.getElementById("view");
  if (!v.querySelector(".ld")) {
    sigs.list = ""; sigs.detail = ""; mounted = "review";
    v.replaceChildren(h("div", { class: "ld" }, h("section", { class: "list-pane", id: "listPane", "aria-label": "Invoices" }), h("section", { class: "detail-pane", id: "detailPane", "aria-label": "Invoice detail" })));
  }
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
    items.push(h("div", { class: "list-group" }, `${name} · ${rows.length}`));
    for (const i of rows) items.push(h("a", { class: "row", href: `#/review/${i.id}`, "data-id": String(i.id), "aria-current": String(route[1] === String(i.id)) },
      avatar(i.vendor, i.state),
      h("span", { style: { minWidth: 0 } }, h("span", { class: "who" }, i.vendor), h("span", { class: "sub" }, human(i.reason) || (i.due ? `MSME: pay by ${day(i.due)}` : `${i.number} · ${day(i.date)}`))),
      h("span", { class: "amt" }, i.net || i.gross, h("small", {}, i.number))));
  }
  pane.replaceChildren(h("header", {}, h("h1", { class: "headline" }, "Review"),
    h("div", { class: "chips", role: "group", "aria-label": "Filter" }, Object.entries(FILTERS).map(([id, [label]]) => h("button", { class: "chip", "aria-pressed": String(filter === id), onclick: () => { filter = id; sigs.list = ""; renderReview(); } }, filter === id ? icon("check", 15) : null, label, h("span", { class: "n" }, String(count(id))))))),
  ...(items.length ? items : [h("div", { class: "empty", style: { height: "auto" } }, shaped("sh", "cookie", icon("check", 36)), h("div", { class: "title" }, filter === "needs" ? "Nothing needs you" : "Nothing here yet"), h("p", { class: "body-s" }, S.invoices.length ? "Choose another filter." : "Start a job from Today."))]));
  pane.scrollTop = keep;
}
async function renderDetail() {
  const pane = document.getElementById("detailPane");
  if (!pane) return;
  if (!route[1]) {
    const zero = S.invoices.length && !visibleNeeds().length && startedExceptions > 0;
    const k = zero ? "zero" : "none";
    if (sigs.detail !== k) {
      sigs.detail = k; current = null;
      pane.replaceChildren(zero
        ? h("div", { class: "empty zero" }, shaped("sh", "cookie", icon("check", 42)), h("div", { class: "headline" }, `All ${startedExceptions} exceptions cleared`), h("p", { class: "body-s" }, S.counts.READY + S.counts.APPROVED ? "Your payment run is ready to sign." : "Nothing is waiting on you."))
        : h("div", { class: "empty" }, shaped("sh", "clover", icon("inbox", 36)), h("div", { class: "title" }, "Pick an invoice"), h("p", { class: "body-s" }, "See the decision, the reason and each record behind it. Press ? for shortcuts.")));
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
  if (!fresh) node.style.animation = "none";
  pane.replaceChildren(node);
  if (fresh) pane.scrollTop = 0;
}
const fact = (a, b) => h("div", {}, h("span", {}, a), h("b", {}, b || "Not recorded"));
const more = (title, body) => h("details", { class: "more" }, h("summary", {}, title, icon("chevron", 18)), h("div", {}, body));
function evidenceRow(d, f) {
  const [label, ic] = CHECKS[f.check_name] || [f.check_name, "info"];
  return h("button", { class: "li", onclick: () => openRecord(d.id, f.check_name), "aria-haspopup": "dialog" },
    h("span", { class: "sh " + f.status }, icon(ic, 18)),
    h("span", {}, h("strong", {}, label), h("span", { class: "what" }, human(f.detail)), h("span", { class: "src" }, `${(STATUS[f.status] || [f.status])[0]} · ${sourceLabel(f.source)} · ${day(f.retrieved_at)}`), h("span", { class: "sr" }, "Open record")),
    icon("chevron", 18));
}
function detailView(d) {
  const n = d.investigation, open = ["HELD", "BLOCKED"].includes(d.state);
  const titles = { READY: "Clean. It is in the next sign-off.", APPROVED: "Signed. Waiting to be issued.", PAID: "Payment request issued once.", REJECTED: "Rejected." };
  const bodies = { READY: "Every record agrees with this invoice.", APPROVED: d.order ? `Signed by ${d.order.by}. The payee and amount are frozen.` : "", PAID: `Reference ${d.payment_ref || ""}, in ${S.provider}.`, REJECTED: "This invoice will not be paid." };
  const queue = visibleNeeds(), at = queue.findIndex(i => String(i.id) === String(d.id));
  const problems = d.findings.filter(f => !["pass", "info"].includes(f.status)), rest = d.findings.filter(f => ["pass", "info"].includes(f.status));
  const verified = h("div", { hidden: problems.length > 0 }, rest.map(f => evidenceRow(d, f)));
  const toggle = problems.length && rest.length ? h("button", { class: "ev-more", id: "evToggle", "aria-expanded": "false", onclick: e => { verified.hidden = !verified.hidden; e.currentTarget.setAttribute("aria-expanded", String(!verified.hidden)); e.currentTarget.textContent = verified.hidden ? `Show ${rest.length} other checks` : "Hide other checks"; } }, `Show ${rest.length} other checks`) : null;
  return h("article", { class: "detail" },
    h("a", { class: "icon-btn back", href: "#/review", "aria-label": "Back to list" }, icon("back")),
    h("header", { class: "d-head" }, avatar(d.vendor, d.state),
      h("div", {}, at >= 0 ? h("div", { class: "position" }, `${at + 1} of ${queue.length} to review`) : null, h("h2", { class: "title", id: "detailTitle", tabindex: "-1" }, d.vendor), h("p", { class: "body-s" }, `${d.number || "No number"} · ${day(d.date)} · ${d.po || "No PO"}`)), tag(d.state)),
    h("section", { class: "verdict " + d.state, "aria-label": "Decision" },
      shaped("sh", SHAPE_OF[d.state] || "soft", icon((STATES[d.state] || [])[1] || "info", 24)),
      h("div", {}, h("h3", { class: "title-s" }, n && open ? n.action_text : titles[d.state] || d.state),
        h("p", {}, n && open ? human(n.explanation) : bodies[d.state]),
        n?.callback && open ? h("div", { class: "callback" }, icon("phone", 20), h("span", {}, n.callback)) : null,
        d.bank_change ? h("div", { class: "callback" }, icon("user", 20), h("span", {}, `${d.bank_change.by} logged a call and proposed ${d.bank_change.account}: "${d.bank_change.note}" A second person must approve it.`)) : null,
        n && open ? h("div", { class: "provenance" }, icon(n.author === "agent" ? "agent" : "doc", 15), n.author === "agent" ? `Investigator agent. Code checked its ${plural(n.citations.length, "citation")}.` : "Rule-based explanation.") : null)),
    h("div", {}, h("div", { class: "label" }, d.order ? "Net amount" : "Net payable"), money(d.order ? d.order.net_paise : d.net)),
    h("div", { class: "breakdown" }, fact("Gross", d.order?.gross_paise || d.gross), fact("GST", d.tax), fact(d.order ? "TDS" : "TDS draft", d.order?.tds_paise || d.tds), d.due ? fact("MSME pay by", day(d.due)) : fact("Taxable", d.taxable)),
    h("div", { class: "sec-h" }, h("h3", { class: "title" }, "Evidence"), h("span", { class: "body-s" }, "Open any line to see its record")),
    h("div", { class: "evidence" }, problems.map(f => evidenceRow(d, f)), toggle, verified),
    d.reader_notes.length ? more("How it was read", h("ul", { class: "trail" }, d.reader_notes.map(x => h("li", {}, x)))) : null,
    more("Audit trail", h("ul", { class: "trail" }, d.events.map(e => h("li", {}, h("b", {}, e.event.replaceAll("_", " ")), ` by ${e.actor}. ${human(e.detail)}`, h("time", {}, stamp(e.at)))))),
    more("Original document, accounts masked", h("pre", {}, d.raw)),
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
  const close = () => { sheet.hidden = true; scrim.hidden = true; release(); opener?.focus?.(); };
  const [label] = CHECKS[check] || [check];
  const compare = r.compare ? h("div", { class: "compare", "aria-label": "Invoice compared with vendor master" }, r.compare.map((c, n) => h("div", { class: "cmp" }, h("div", { class: "label" }, c.label),
    h("div", { class: "cmp-row" }, h("span", { class: "body-s" }, "Invoice"), digitRow(c.invoice, c.master, n * 8)), h("div", { class: "cmp-row" }, h("span", { class: "body-s" }, "Master"), digitRow(c.master, c.invoice, n * 8 + 4))))) : null;
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
  const close = () => { sheet.hidden = true; scrim.hidden = true; release(); opener?.focus?.(); };
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
  const show = count > 0 && !S.job.running && (route[0] === "today" && !composerOpen || (route[0] === "review" && !route[1]));
  const key = JSON.stringify([show, count, p.net, c.READY]);
  if (sigs.dock === key) return; sigs.dock = key;
  dock.classList.toggle("on", show);
  if (!show) return;
  dock.replaceChildren(h("div", { class: "dockbar" }, h("div", {}, h("b", {}, p.net), h("small", {}, `${plural(count, "invoice")} net of TDS`)),
    h("button", { class: "btn", onclick: openSign }, icon("lock", 18), c.READY ? "Review and sign" : "Issue payments")));
}
function openSign() {
  const dlg = document.getElementById("sign"), scrim = document.getElementById("scrim"), p = S.payment_run, c = S.counts, opener = document.activeElement;
  let release, sealAnim;
  const close = () => { dlg.hidden = true; scrim.hidden = true; release(); opener?.focus?.(); };
  const seal = shaped("seal", "soft", icon("lock", 28));
  const nameInput = h("input", { class: "input", id: "bySign", autocomplete: "name", value: reviewer(), placeholder: "Your name", oninput: e => { store.set("chukta-reviewer", e.target.value.trim()); hold.disabled = !e.target.value.trim(); renderRail(); } });
  const finish = async () => {
    hold.disabled = true;
    try {
      await flushPending();
      const items = S.payment_run.lines.filter(l => l.state === "READY").map(l => ({ id: l.id, evidence: l.evidence }));
      if (items.length) await post("/api/signoff", { by: reviewer(), items });
      await post("/api/pay", { by: reviewer() });
      seal.classList.add("done"); seal.style.clipPath = shape("cookie"); seal.replaceChildren(icon("check", 30)); navigator.vibrate?.(12);
      setTimeout(async () => { close(); composerOpen = false; snack("Signed. Issuing each payment request once."); sigs.view = ""; go("today"); await tick(); }, reduced.matches ? 80 : 620);
    } catch (e) { snack(e.message); hold.disabled = false; sigs.view = ""; tick(); }
  };
  const hold = holdButton(`Hold to sign and issue ${p.net}`, finish, on => {
    if (reduced.matches) return;
    sealAnim?.cancel();
    if (on) sealAnim = seal.animate(["soft", "cookie", "burst"].map(k => ({ clipPath: shape(k) })), { duration: 1000, fill: "forwards", easing: "cubic-bezier(.4,0,.2,1)" });
  });
  hold.disabled = !reviewer();
  dlg.replaceChildren(h("div", { class: "sign-in" },
    h("div", { class: "sheet-h", style: { marginBottom: "2px" } }, h("h2", { class: "headline", id: "sign-title" }, "Sign this payment run"), h("button", { class: "icon-btn", "aria-label": "Close", onclick: close }, icon("x"))),
    h("p", { class: "body-s" }, `${S.client}. Issued as payment requests in ${S.provider}.`),
    h("section", { class: "sign-total" }, h("div", {}, h("div", { class: "label", style: { color: "inherit" } }, "Net to issue"), money(p.net)), seal,
      h("div", { class: "sign-sum" }, h("span", {}, "Gross", h("b", {}, p.gross)), h("span", {}, "TDS draft", h("b", {}, p.tds)), h("span", {}, "GST retained", h("b", {}, p.retained)))),
    h("div", { class: "sign-list" }, p.lines.map(l => h("div", { class: "sign-row" }, h("span", {}, l.vendor, h("small", {}, `${l.number}${l.due ? ` · MSME pay by ${day(l.due)}` : ""}`)), h("b", {}, l.net)))),
    c.BLOCKED + c.HELD ? h("p", { class: "body-s", style: { marginBottom: "10px" } }, `${plural(c.BLOCKED + c.HELD, "exception")} stay${c.BLOCKED + c.HELD === 1 ? "s" : ""} out of this run until you decide.`) : null,
    h("label", { class: "field", style: { marginBottom: "10px" } }, h("span", {}, "Reviewer"), nameInput),
    hold,
    h("div", { class: "sign-foot" }, h("span", { class: "body-s" }, "This cannot be undone. Your name goes on the audit trail."), h("button", { class: "btn text", onclick: close }, "Not yet"))));
  dlg.hidden = false; scrim.hidden = false; scrim.onclick = close; release = trap(dlg, close);
  (reviewer() ? hold : nameInput).focus();
}
function holdButton(label, onDone, onChange) {
  let timer = null, viaKey = false;
  const btn = h("button", { class: "hold", type: "button", "aria-label": `${label}. Press and hold.` }, h("span", { class: "fill" }), icon("lock", 20), h("span", {}, label));
  const begin = () => { if (btn.disabled || timer) return; btn.classList.add("holding"); onChange?.(true); timer = setTimeout(() => { timer = null; btn.classList.remove("holding"); onDone(); }, 1000); };
  const end = () => { if (timer) { clearTimeout(timer); timer = null; btn.classList.remove("holding"); onChange?.(false); snack("Keep holding to confirm."); } };
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
    h("header", { class: "top" }, h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "headline" }, "Bank statement")),
      h("div", { class: "chips" }, h("span", { class: "pill-note" }, icon("check", 16), `${data.posted} posted`), h("span", { class: "pill-note" }, icon("warn", 16), `${data.held} held`))),
    h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "4px" } }, "Post these lines to the right payee and account"),
      h("p", { class: "body-s", style: { marginBottom: "12px" } }, "A name alone never identifies a business: a third of the Indian company names we sampled are shared. A line posts only through a payment Chukta issued, or a firm's payee rule confirmed against the company's record."),
      text, h("div", { class: "actions" }, h("button", { class: "btn filled", disabled: S.job.running, onclick: () => send({ text: document.getElementById("stmt").value }) }, icon("play", 18), "Post lines"),
        h("button", { class: "btn tonal", disabled: S.job.running, onclick: () => send({ sample: true }) }, icon("receipt", 18), "Use October sample"))),
    data.lines.length ? h("section", { class: "card", style: { padding: "6px 0" }, "aria-label": "Statement lines" }, data.lines.map(lineRow)) : null));
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
    h("header", { class: "top" }, h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "headline" }, "The client's books"))),
    h("section", { class: "stat-row", "aria-label": "Books" }, stat("Vendors", String(d.vendors.length), "On the master"), stat("Purchase orders", String(d.pos), "Open to match"), stat("GSTR-2B periods", String(d.periods.length), d.periods.map(human).join(", ") || "None imported"), stat("Bank changes", String(d.changes.length), "Two-person approval")),
    h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "10px" } }, "Bring in records"),
      h("div", { class: "chips", role: "group", "aria-label": "Record type", style: { marginBottom: "12px" } }, Object.entries(BOOKS_HELP).map(([k, v]) => h("button", { class: "chip", "aria-pressed": String(booksKind === k), onclick: () => { booksKind = k; sigs.view = ""; renderBooks(); } }, v[0]))),
      h("p", { class: "body-s", style: { marginBottom: "10px" } }, help), text, h("div", { class: "actions" }, h("button", { class: "btn filled", onclick: send }, icon("download", 18), `Import ${title.toLowerCase()}`))),
    h("section", { class: "card", style: { padding: "16px 12px" } }, h("h2", { class: "title", style: { margin: "0 12px 8px" } }, "Vendor master"),
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("thead", {}, h("tr", {}, ["Vendor", "GSTIN", "Domain", "Bank", "TDS", "MSME"].map(x => h("th", { scope: "col" }, x)))),
        h("tbody", {}, d.vendors.map(v => h("tr", {}, h("td", { style: { fontWeight: 600 } }, v.name), h("td", { class: "num" }, v.gstin), h("td", {}, v.domain), h("td", { class: "num" }, `${v.account} · ${v.ifsc}`), h("td", {}, v.tds_class || "Not set"), h("td", {}, v.msme || "Not known")))))))));
}

/* Ledger */
const SOURCE_NAMES = { crustdata: "Crustdata", ifsc: "IFSC registry", model: "Model (DeepSeek)", razorpay_test: "Razorpay test mode" };
const outcomeText = o => /^20\d$/.test(String(o)) ? "OK" : o === "429" ? "Rate limited, retried" : /^\d{3}$/.test(String(o)) ? `Error ${o}` : String(o).replace("error:", "Failed: ");
const requestText = r => String(r).replace("/company/identify", "Company lookup").replace("/company/search", "Company status").replace("POST /v1/payment_links", "Payment request").replace("GET /v1/payment_links", "Payment lookup").replace("deepseek/deepseek-v4.1-flash", "Read invoice").replace("investigator", "Investigate exception").replace(/^ifsc$/, "Branch lookup");
async function renderLedger() {
  const d = await get("/api/ledger").catch(() => null);
  if (!d || route[0] !== "ledger") return;
  const key = "ledger" + JSON.stringify([d.total_calls, d.credits, d.usd]);
  if (sigs.view === key) return; sigs.view = key;
  const max = Math.max(1, ...d.by_source.map(s => s.calls));
  mount("ledger", h("div", { class: "page" },
    h("header", { class: "top" }, h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "headline" }, "Cost ledger"))),
    h("section", { class: "stat-row", "aria-label": "Totals" }, stat("Credits per invoice", String(d.per_invoice_credits), `${plural(d.invoices, "invoice")}`), stat("Model cost per invoice", `$${d.per_invoice_usd.toFixed(5)}`, "DeepSeek V4.1 Flash"), stat("Total credits", String(d.credits), "Crustdata"), stat("Calls recorded", String(d.total_calls), "Every source")),
    d.total_calls ? [h("div", { class: "two" },
      h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "8px" } }, "Calls by source"), d.by_source.map(s => h("div", { class: "meter" },
        h("div", { class: "meter-h" }, h("span", {}, SOURCE_NAMES[s.source] || s.source), h("b", {}, `${s.calls} calls${s.credits ? ` · ${s.credits} cr` : ""}${s.usd ? ` · $${s.usd}` : ""}`)),
        h("div", { class: "track" }, h("i", { style: { width: s.calls / max * 100 + "%" } }))))),
      d.run ? h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "8px" } }, "Latest run against its ceiling"),
        meter("Crustdata credits", d.run.credits, d.run.credit_limit, `${d.run.credits} of ${d.run.credit_limit}`),
        meter("Model spend", d.run.usd, d.run.model_usd_limit, `$${d.run.usd.toFixed(4)} of $${d.run.model_usd_limit.toFixed(2)}`),
        h("p", { class: "body-s" }, `Time limit ${Math.round(d.run.time_limit_s / 60)} minutes. At a ceiling, Chukta holds what it cannot check.`)) : null),
    h("section", { class: "card", style: { marginTop: "14px", padding: "16px 12px" } }, h("h2", { class: "title", style: { margin: "0 12px 8px" } }, "Every call"),
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("thead", {}, h("tr", {}, ["When", "Source", "What", "Result", "Credits", "Model $"].map((x, i) => h("th", { class: i > 3 ? "r" : "", scope: "col" }, x)))),
        h("tbody", {}, d.calls.slice(0, 60).map(c => h("tr", {}, h("td", { style: { whiteSpace: "nowrap" } }, stamp(c.at)), h("td", {}, SOURCE_NAMES[c.source] || c.source), h("td", {}, requestText(c.request)), h("td", {}, outcomeText(c.outcome)), h("td", { class: "r" }, c.credits ? String(c.credits) : "0"), h("td", { class: "r" }, c.usd ? c.usd.toFixed(5) : "0")))))))]
      : h("section", { class: "card" }, h("div", { class: "empty", style: { minHeight: "240px" } }, shaped("sh", "soft", icon("receipt", 36)), h("div", { class: "title" }, "No calls yet"), h("p", { class: "body-s" }, "Every source call and its cost will appear here.")))));
}
const stat = (a, b, c) => h("div", { class: "stat" }, h("span", {}, a), h("b", {}, b), h("small", {}, c));

/* Audit */
async function renderAudit() {
  const d = await get("/api/replay").catch(() => null);
  if (!d || route[0] !== "audit") return;
  const key = "audit" + JSON.stringify(d);
  if (sigs.view === key) return; sigs.view = key;
  const ok = d.ok, n = d.lines.length;
  const list = h("div", { id: "replay" }, d.lines.map((l, i) => h("div", { class: "replay-row" + (l.ok ? "" : " bad"), style: { animationDelay: `${i * 90}ms` } },
    h("span", { class: "sh" }, icon(l.ok ? "check" : "x", 17)), h("div", {}, h("div", { class: "title-s" }, l.payee), h("div", { class: "body-s" }, `${l.number} · signed by ${l.signed_by}`)),
    h("div", { class: "body-s hide-s", style: { overflowWrap: "anywhere" } }, l.reference || "Not issued yet"), h("div", { class: "num", style: { fontWeight: 600, textAlign: "right" } }, l.net, h("div", { class: "body-s" }, `TDS ${l.tds}`)))));
  let shown = list;
  const replay = () => { const fresh = shown.cloneNode(true); shown.replaceWith(fresh); shown = fresh; snack(ok ? "Replayed. Every issued payment matches its sign-off, and the trail is unbroken." : "The replay found a problem."); };
  mount("audit", h("div", { class: "page" },
    h("header", { class: "top" }, h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "headline" }, "Audit"))),
    h("section", { class: "hero " + (ok && n ? "good" : "") }, h("div", { class: "hero-top" }, shaped("morph", ok ? "cookie" : "burst", icon(ok ? "shield" : "warn", 30)),
      h("div", { style: { flex: 1, minWidth: 0 } }, h("h2", { class: "headline" }, !n ? "Nothing signed yet" : ok ? `${plural(n, "payment")}, each signed and issued once` : "The books do not replay"),
        h("p", { class: "body-s" }, ok ? "Checks each payment against its sign-off, frozen evidence, the provider's record and a hash-chained trail." : d.problems[0])),
      n ? h("button", { class: "btn filled", onclick: replay }, icon("history", 18), "Replay") : null)),
    n ? h("section", { class: "card", style: { padding: "6px 0" }, "aria-label": "Replay" }, list) : null,
    h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "12px" } }, "The finished work"),
      h("div", { class: "exports" }, exportCard("/export/bank.csv", "bank", "Bank file", "Beneficiary, mode, amount, reference"), exportCard("/export/tally.csv", "receipt", "Voucher sheet", "Taxable, GST, TDS and net for Tally"), exportCard("/export/audit.json", "shield", "Audit file", "Every decision, source and call")))));
}
const exportCard = (href, ic, title, text) => h("a", { class: "export", href, download: "" }, icon(ic, 24), h("div", { class: "title-s" }, title), h("div", { class: "body-s" }, text));

/* Loop */
function renderView() {
  if (route[0] === "review") return renderReview();
  if (route[0] === "bank") return renderBank();
  if (route[0] === "books") return renderBooks();
  if (route[0] === "ledger") return renderLedger();
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
  pollTimer = setTimeout(tick, S?.job?.running ? 900 : 3000);
}
onRoute();
tick();
