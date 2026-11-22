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
  rupee: "M7 5h10 M7 9h10 M10 5c3.8 0 5 2 5 4s-1.800 4-5 4H7l7 7", paste: "M9 4h6v3H9z M8 5H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1h-2",
  history: "M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5 M12 8v4l3 2", tag: "M4 4h8l8 8-8 8-8-8V4z M8.500 8.500h.01",
};
const CHECKS = {
  required: ["Invoice fields", "doc"], document: ["Document", "doc"], gstin: ["GSTIN", "hash"], vendor: ["Vendor master", "building"], duplicate: ["Duplicate", "copy"],
  near_duplicate: ["Near duplicate", "copy"], po: ["Purchase order", "cart"], bank: ["Bank details", "bank"], bank_request: ["Bank change request", "warn"], ifsc: ["IFSC registry", "bank"],
  gst: ["GSTR-2B", "receipt"], sender: ["Sender", "mail"], company: ["Company record", "building"], msme: ["MSME deadline", "clock"], tds: ["TDS draft", "percent"],
  internal: ["System", "info"], payment_conflict: ["Payment", "rupee"], payment: ["Payment provider", "rupee"],
};
const STATES = { BLOCKED: ["Blocked", "shieldx"], HELD: ["Held", "warn"], READY: ["Ready", "check"], APPROVED: ["Signed", "lock"], PAID: ["Issued", "check"], REJECTED: ["Rejected", "x"], NEW: ["Checking", "clock"] };
const STATUS = { pass: ["Verified", "check"], fail: ["Failed", "x"], unverified: ["Can't verify", "info"], info: ["Note", "info"], POSTED: ["Posted", "check"], HELD: ["Held", "warn"], REJECTED: ["Dismissed", "x"] };
const SHAPE_OF = { READY: "circle", HELD: "soft", BLOCKED: "burst", APPROVED: "clover", PAID: "cookie", REJECTED: "circle", NEW: "soft" };
const SEEDS = { forest: ["#2f6b52", "#b3f0d0", "#a6cdb9"], bay: ["#3a5f9f", "#d6e3ff", "#bcc7dc"], peony: ["#8f4a60", "#ffd9e2", "#e3bdc6"], marigold: ["#7a5a17", "#ffdea8", "#d9c4a0"] };

let S = null, route = ["today"], filter = "needs", detailData = null, sigs = {}, composerOpen = false, useSample = true, draft = null, pollTimer = null;
const reduced = matchMedia("(prefers-reduced-motion: reduce)");

/* Small helpers */
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
function money(text) {
  const m = /^(.*)(\.\d\d)$/.exec(text || "");
  return m ? h("span", { class: "amount num" }, m[1], h("small", {}, m[2])) : h("span", { class: "amount" }, text || "Unclear");
}
function day(iso) {
  if (!iso) return "No date";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return `${d} ${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m - 1]} ${y}`;
}
const stamp = iso => iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;
const store = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch { /* Optional. */ } } };
const reviewer = () => store.get("chukta-reviewer") || "";
function reviewerField(id) {
  return h("label", { class: "field" }, h("span", {}, "Reviewer"), h("input", { class: "input", id, autocomplete: "name", value: reviewer(), placeholder: "Your name", oninput: e => store.set("chukta-reviewer", e.target.value.trim()) }));
}
let snackTimer;
function snack(text, bad = false) {
  const el = document.getElementById("snack");
  el.textContent = text; el.className = "on" + (bad ? " err" : "");
  clearTimeout(snackTimer); snackTimer = setTimeout(() => { el.className = ""; }, bad ? 6500 : 3800);
}
async function get(path) { const r = await fetch(path); if (!r.ok) throw new Error("Not available"); return r.json(); }
async function post(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "content-type": "application/json", "x-chukta": "1" }, body: JSON.stringify(body || {}) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || "That did not work");
  return data;
}
async function act(path, body, done) {
  try {
    await post(path, { by: reviewer(), ...body });
    if (done) snack(done);
    sigs = {}; await tick();
    return true;
  } catch (e) {
    snack(e.message, true);
    if (/reviewer/i.test(e.message)) document.querySelector("input[id^=by]")?.focus();
    return false;
  }
}
document.addEventListener("pointerdown", e => {
  const host = e.target.closest?.(".btn,.chip,.fab,.icon-btn,.row,.li");
  if (!host || host.disabled || reduced.matches) return;
  const box = host.getBoundingClientRect(), size = Math.max(box.width, box.height) * 2.2;
  const dot = h("span", { class: "ripple", style: { width: size + "px", height: size + "px", left: e.clientX - box.left - size / 2 + "px", top: e.clientY - box.top - size / 2 + "px" } });
  host.append(dot); setTimeout(() => dot.remove(), 560);
});

/* Navigation */
const NAV = [["today", "Today", "today"], ["review", "Review", "inbox"], ["bank", "Bank", "bank"], ["ledger", "Ledger", "receipt"], ["audit", "Audit", "shield"]];
function renderRail() {
  const c = S.counts, need = c.BLOCKED + c.HELD;
  const key = JSON.stringify([route[0], need]);
  if (sigs.rail === key) return; sigs.rail = key;
  document.getElementById("rail").replaceChildren(
    h("div", { class: "brand", style: { clipPath: shape("cookie") }, "aria-hidden": "true" }, "च"),
    h("button", { class: "fab", "aria-label": "New run", title: "New run", onclick: () => { composerOpen = true; go("today"); sigs.view = ""; renderView(); } }, icon("plus", 26)),
    ...NAV.map(([id, label, ic]) => h("a", { class: "dest", href: "#/" + id, "aria-current": route[0] === id ? "page" : null },
      h("span", { class: "pill" }, icon(ic)), id === "review" && need ? h("span", { class: "badge", "aria-label": plural(need, "exception") }, String(need)) : null, label)),
    h("div", { class: "rail-end" }, h("button", { class: "icon-btn", "aria-label": "Theme", title: "Theme", "aria-haspopup": "true", onclick: toggleMenu }, icon("palette"))));
}
function toggleMenu(e) {
  e?.stopPropagation();
  const menu = document.getElementById("menu");
  if (!menu.hidden) { menu.hidden = true; return; }
  const root = document.documentElement;
  const paint = () => menu.replaceChildren(h("div", { class: "title-s" }, "Your palette"),
    h("div", { class: "swatches" }, Object.entries(SEEDS).map(([name, [a, b, c]]) => h("button", { class: "swatch", "aria-label": name, "aria-pressed": String(root.dataset.seed === name), onclick: () => { root.dataset.seed = name; store.set("chukta-seed", name); paint(); } },
      h("i", { style: { background: a } }), h("i", { style: { background: b } }), h("i", { style: { background: c } })))),
    h("div", { class: "seg", role: "group", "aria-label": "Brightness" }, [["light", "Light", "sun"], ["dark", "Dark", "moon"]].map(([m, label, ic]) => h("button", { "aria-pressed": String(root.dataset.mode === m), onclick: () => { root.dataset.mode = m; store.set("chukta-mode", m); paint(); } }, icon(ic, 18), label))));
  paint(); menu.hidden = false;
}
document.addEventListener("click", e => { const m = document.getElementById("menu"); if (!m.hidden && !m.contains(e.target)) m.hidden = true; });
function go(...parts) { const hash = "#/" + parts.join("/"); if (location.hash !== hash) location.hash = hash; else onRoute(); }
function onRoute() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  route = parts.length ? parts : ["today"];
  if (!NAV.some(n => n[0] === route[0])) route = ["today"];
  const swap = () => { sigs.view = ""; sigs.list = ""; sigs.detail = ""; detailData = null; if (S) { renderRail(); renderView(); renderDock(); } };
  swap();
}
addEventListener("hashchange", onRoute);

/* A view animates in only when you arrive at it, never on a data refresh. */
let mounted = "", busyMorph = null;
function mount(type, node) {
  if (mounted === type) node.style.animation = "none";
  mounted = type;
  document.getElementById("view").replaceChildren(node);
}

/* Today */
function stepsFor() {
  const r = S.run, c = S.counts, stage = r.stage;
  const early = ["reading", "checking", "investigating"], at = early.indexOf(stage), past = at === -1;
  const pos = i => past || at > i ? "done" : at === i ? "active" : "todo";
  const signed = c.APPROVED + c.PAID > 0 && c.READY === 0;
  const ex = c.BLOCKED + c.HELD;
  return [
    { title: "Understand the request", note: r.understood.job, st: "done" },
    { title: "Read every invoice", note: `${r.inputs_done} of ${r.inputs_total}`, st: pos(0), pct: r.inputs_total ? r.inputs_done / r.inputs_total : 0 },
    { title: "Check against independent records", note: "GST, PO, vendor, bank, IFSC and company", st: pos(1) },
    { title: "Investigate exceptions", note: past ? (ex ? plural(ex, "exception") + " explained" : "None") : "Read-only agent, citations checked", st: pos(2) },
    { title: "Your sign-off", note: signed ? "Signed" : past ? (c.READY ? `${c.READY} ready to sign` : "Nothing to sign") : "Waits for a person", st: !past ? "todo" : signed ? "done" : c.READY ? "need" : "todo" },
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
  const frames = ["soft", "cookie", "clover", "burst", "pebble", "soft"].map(k => ({ clipPath: shape(k) }));
  el.animate(frames, { duration: 5200, iterations: Infinity, easing: "cubic-bezier(.4,0,.2,1)" });
  el.animate([{ transform: "rotate(0)" }, { transform: "rotate(360deg)" }], { duration: 6400, iterations: Infinity });
  return el;
}
function composer() {
  if (draft === null) draft = S.sample_request;
  const pasted = h("textarea", { class: "input", id: "pasteText", "aria-label": "Invoice text", placeholder: "Paste invoices or emails. Separate them with a line containing only ---. Use fictional data." });
  const box = h("div", { class: "paste", hidden: useSample });
  box.append(pasted);
  const sampleChip = h("button", { class: "chip", "aria-pressed": String(useSample), onclick: () => choose(true) }, icon("receipt", 18), `This week's ${S.sample_count} sample invoices`);
  const pasteChip = h("button", { class: "chip", "aria-pressed": String(!useSample), onclick: () => choose(false) }, icon("paste", 18), "Paste an unseen invoice");
  function choose(sample) { useSample = sample; sampleChip.setAttribute("aria-pressed", String(sample)); pasteChip.setAttribute("aria-pressed", String(!sample)); box.hidden = sample; if (!sample) pasted.focus(); }
  const start = h("button", { class: "btn filled lg", onclick: async () => {
    try {
      await post("/api/run", { request: ask.value, ...(useSample ? { sample: true } : { text: pasted.value }) });
      composerOpen = false; sigs = {}; await tick();
    } catch (e) { snack(e.message, true); }
  } }, icon("play", 22), "Start the job");
  const ask = h("textarea", { class: "ask", "aria-label": "What should Chukta do?", rows: 4, oninput: e => { draft = e.target.value; } });
  ask.value = draft;
  return h("div", { class: "page" },
    h("section", { class: "composer" },
      shaped("blob b1", "cookie"), shaped("blob b2", "clover"),
      h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "sr" }, "New request"), ask),
      h("div", {}, h("div", { class: "composer-foot" }, h("div", { class: "chips" }, sampleChip, pasteChip), start), box)),
    h("section", { class: "promises", "aria-label": "How Chukta works" },
      promise("shield", "An invoice is never its own proof", "Every claim must agree with a record the sender does not control."),
      promise("lock", "A person signs every payment", "Your sign-off freezes the payee and the amount before anything moves."),
      promise("refresh", "Each payment happens once", "Stop it at any moment. It carries on where it stopped.")));
}
const promise = (ic, title, text) => h("div", { class: "promise" }, shaped("sh", "soft", icon(ic)), h("div", {}, h("div", { class: "title-s" }, title), h("p", { class: "body-s" }, text)));
function renderToday() {
  const v = document.getElementById("view");
  if (composerOpen || !S.run) {
    if (sigs.view !== "composer") { sigs.view = "composer"; mount("composer", composer()); }
    return;
  }
  const key = "run" + JSON.stringify([S.run, S.counts, S.job, S.audit_problems, S.issued]);
  if (sigs.view === key) return; sigs.view = key;
  const c = S.counts, r = S.run, ex = c.BLOCKED + c.HELD, busy = S.job.running;
  const complete = !busy && c.PAID > 0 && !c.READY && !c.APPROVED;
  const heroClass = busy ? "" : complete && !ex ? "good" : "need";
  const headline = busy ? S.job.message : complete && !ex ? "Payment run complete" : complete ? `${plural(c.PAID, "payment")} issued. ${plural(ex, "exception")} left` : c.READY || ex ? `${c.READY} ready to sign, ${ex} need you` : "Nothing is waiting";
  const sub = busy ? S.job.name : complete ? `${S.issued} issued once, in ${S.provider}.` : "Each exception has a reason and a source.";
  if (!busy) busyMorph = null;
  const morph = busy ? (busyMorph ||= morphing(shaped("morph", "soft", h("span", { style: { display: "grid" } }, icon("agent", 32)))))
    : shaped("morph", complete ? "cookie" : "clover", h("span", { style: { display: "grid" } }, icon(complete ? "check" : "inbox", 32)));
  const steps = stepsFor();
  const page = h("div", { class: "page" },
    h("header", { class: "top" }, h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "headline" }, "This week's payment run")),
      h("span", { class: "pill-note" }, h("span", { class: "dot" }), S.provider)),
    h("div", { class: "run-grid" },
      h("div", {},
        h("section", { class: "hero " + heroClass }, morph, h("div", {}, h("h2", { class: "headline" }, headline), h("p", { class: "body-s" }, sub),
          !busy && ex ? h("a", { class: "btn filled", style: { marginTop: "12px" }, href: "#/review" }, `Review ${plural(ex, "exception")}`, icon("arrow", 18)) : null)),
        h("section", { class: "bento", "aria-label": "Outcome" },
          h("a", { class: "tile s", href: "#/review", onclick: () => { filter = "ready"; } }, h("span", {}, icon("check", 16), "Cleared"), h("b", {}, String(c.READY + c.APPROVED + c.PAID))),
          h("a", { class: "tile w", href: "#/review", onclick: () => { filter = "needs"; } }, h("span", {}, icon("warn", 16), "Held"), h("b", {}, String(c.HELD))),
          h("a", { class: "tile e", href: "#/review", onclick: () => { filter = "needs"; } }, h("span", {}, icon("shieldx", 16), "Blocked"), h("b", {}, String(c.BLOCKED)))),
        h("section", { class: "card" }, h("div", { class: "card-h" }, h("h2", { class: "title" }, "What you asked for"), h("button", { class: "btn text", onclick: () => { composerOpen = true; draft = r.request; sigs.view = ""; renderView(); } }, icon("plus", 18), "New run")),
          h("p", { class: "quote" }, r.request),
          h("p", { class: "body-s", style: { marginTop: "12px" } }, h("b", {}, "Finished work: "), r.understood.finished),
          r.understood.notes.map(n => h("p", { class: "body-s", style: { marginTop: "6px" } }, n)))),
      h("div", {},
        h("section", { class: "card", "aria-label": "Plan" }, h("div", { class: "card-h" }, h("h2", { class: "title" }, "The plan")),
          h("ol", { class: "steps" }, steps.map((s, i) => h("li", { class: "step " + s.st, "aria-current": s.st === "active" ? "step" : null },
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
  h("div", { class: "track", role: "img", "aria-label": `${name}: ${text}` }, h("i", { style: { width: Math.min(100, limit ? used / limit * 100 : 0) + "%" } })));

/* Review */
const FILTERS = { needs: ["Needs you", ["BLOCKED", "HELD"]], ready: ["Ready", ["READY", "APPROVED"]], issued: ["Issued", ["PAID"]], all: ["All", Object.keys(STATES)] };
const GROUPS = [["Needs your decision", ["BLOCKED", "HELD"]], ["Ready to sign", ["READY"]], ["Signed, waiting to issue", ["APPROVED"]], ["Issued in test mode", ["PAID"]], ["Rejected", ["REJECTED"]], ["Checking", ["NEW"]]];
function renderReview() {
  const v = document.getElementById("view");
  if (!v.querySelector(".ld")) {
    sigs.list = ""; sigs.detail = ""; mounted = "review";
    v.replaceChildren(h("div", { class: "ld" }, h("section", { class: "list-pane", id: "listPane", "aria-label": "Invoices" }), h("section", { class: "detail-pane", id: "detailPane", "aria-label": "Invoice detail" })));
  }
  v.querySelector(".ld").classList.toggle("open", Boolean(route[1]));
  const key = JSON.stringify([S.invoices, filter, route[1]]);
  if (sigs.list !== key) { sigs.list = key; renderList(); }
  renderDetail();
}
function renderList() {
  const pane = document.getElementById("listPane"), keep = pane.scrollTop;
  const counts = id => S.invoices.filter(i => FILTERS[id][1].includes(i.state)).length;
  const shown = S.invoices.filter(i => FILTERS[filter][1].includes(i.state));
  const items = [];
  for (const [name, states] of GROUPS) {
    const rows = shown.filter(i => states.includes(i.state));
    if (!rows.length) continue;
    items.push(h("div", { class: "list-group" }, `${name} · ${rows.length}`));
    for (const i of rows) items.push(h("a", { class: "row", style: { textDecoration: "none", color: "inherit" }, href: `#/review/${i.id}`, "aria-current": String(route[1] === String(i.id)) },
      shaped("av " + i.state, SHAPE_OF[i.state] || "circle", i.vendor[0].toUpperCase()),
      h("span", { style: { minWidth: 0 } }, h("span", { class: "who" }, i.vendor), h("span", { class: "sub" }, i.reason || (i.due ? `MSME: pay by ${day(i.due)}` : `${i.number} · ${day(i.date)}`))),
      h("span", { class: "amt" }, i.net || i.gross, h("small", {}, i.number))));
  }
  pane.replaceChildren(h("header", {}, h("h1", { class: "headline" }, "Review"),
    h("div", { class: "chips", role: "group", "aria-label": "Filter" }, Object.entries(FILTERS).map(([id, [label]]) => h("button", { class: "chip", "aria-pressed": String(filter === id), onclick: () => { filter = id; sigs.list = ""; renderReview(); } }, filter === id ? icon("check", 16) : null, label, h("span", { class: "n" }, String(counts(id))))))),
  ...(items.length ? items : [h("div", { class: "empty" }, shaped("sh", "cookie", icon("check", 36)), h("div", { class: "title" }, filter === "needs" ? "Nothing needs you" : "Nothing here yet"), h("p", { class: "body-s" }, S.invoices.length ? "Choose another filter." : "Start a job from Today."))]));
  pane.scrollTop = keep;
}
async function renderDetail() {
  const pane = document.getElementById("detailPane");
  if (!pane) return;
  if (!route[1]) {
    if (sigs.detail !== "none") { sigs.detail = "none"; pane.replaceChildren(h("div", { class: "empty", style: { height: "100%" } }, shaped("sh", "clover", icon("inbox", 36)), h("div", { class: "title" }, "Pick an invoice"), h("p", { class: "body-s" }, "See the decision, the reason and each record behind it."))); }
    return;
  }
  const id = route[1];
  let d;
  try { d = await get(`/api/invoice/${id}`); } catch { return; }
  if (route[1] !== id) return;
  const key = JSON.stringify([d.state, d.findings, d.investigation?.at, d.order, d.payment_ref, d.can_approve]);
  if (sigs.detail === id + key || ["note", "tdsIn", "byDecide"].includes(document.activeElement?.id)) return;
  const fresh = !(sigs.detail || "").startsWith(id + "[");
  sigs.detail = id + key; detailData = d;
  const node = detailView(d);
  if (!fresh) node.style.animation = "none";
  pane.replaceChildren(node);
  if (fresh) pane.scrollTop = 0;
}
function detailView(d) {
  const n = d.investigation;
  const verdictTitle = { READY: "Clean. It is in the next sign-off.", APPROVED: "Signed. Waiting to be issued.", PAID: "Issued once.", REJECTED: "Rejected." };
  const verdictBody = { READY: "Every record agrees with this invoice.", APPROVED: d.order ? `Signed by ${d.order.by}. The payee and amount are frozen.` : "", PAID: `Reference ${d.payment_ref || ""}, in ${S.provider}.`, REJECTED: "This invoice will not be paid." };
  const money2 = d.order ? d.order.net_paise : d.net;
  return h("article", { class: "detail" },
    h("a", { class: "icon-btn back", href: "#/review", "aria-label": "Back to list" }, icon("back")),
    h("header", { class: "d-head" }, shaped("av " + d.state, SHAPE_OF[d.state] || "circle", d.vendor[0].toUpperCase()),
      h("div", {}, h("h2", { class: "title" }, d.vendor), h("p", { class: "body-s" }, `${d.number || "No number"} · ${day(d.date)} · ${d.po || "No PO"}`)), tag(d.state)),
    h("section", { class: "verdict " + d.state, "aria-label": "Decision" },
      shaped("sh", SHAPE_OF[d.state] || "soft", icon((STATES[d.state] || [])[1] || "info", 26)),
      h("div", {}, h("h3", { class: "title-s" }, n && ["HELD", "BLOCKED"].includes(d.state) ? n.action_text : verdictTitle[d.state] || d.state),
        h("p", { style: { fontSize: "14.5px" } }, n && ["HELD", "BLOCKED"].includes(d.state) ? n.explanation : verdictBody[d.state]),
        n?.callback && ["HELD", "BLOCKED"].includes(d.state) ? h("div", { class: "callback" }, icon("phone", 20), h("span", {}, n.callback)) : null,
        n && ["HELD", "BLOCKED"].includes(d.state) ? h("div", { class: "provenance" }, icon(n.author === "agent" ? "agent" : "doc", 15), n.author === "agent" ? `Investigator agent. Code checked its ${plural(n.citations.length, "citation")}.` : "Rule-based explanation.") : null)),
    h("div", { style: { marginBottom: "2px" } }, h("div", { class: "label" }, d.order ? "Net amount" : "Net payable"), money(money2)),
    h("div", { class: "breakdown" }, fact("Gross", d.order?.gross_paise || d.gross), fact("GST", d.tax), fact(d.order ? "TDS" : "TDS draft", d.order?.tds_paise || d.tds), d.due ? fact("MSME pay by", day(d.due)) : fact("Taxable", d.taxable)),
    decide(d),
    h("div", { class: "sec-h" }, h("h3", { class: "title" }, "Evidence"), h("span", { class: "body-s" }, "Open any line to see its record")),
    h("div", { class: "evidence" }, d.findings.map(f => {
      const [label, ic] = CHECKS[f.check_name] || [f.check_name, "info"];
      return h("button", { class: "li", onclick: () => openRecord(d.id, f.check_name), "aria-haspopup": "dialog" },
        h("span", { class: "sh " + f.status }, icon(ic, 19)),
        h("span", {}, h("strong", {}, label), h("span", { class: "what" }, f.detail), h("span", { class: "src" }, `${(STATUS[f.status] || [f.status])[0]} · retrieved ${day(f.retrieved_at)}`), h("span", { class: "sr" }, "Open record")),
        icon("chevron", 20));
    })),
    d.reader_notes.length ? more("How it was read", h("ul", { class: "trail" }, d.reader_notes.map(x => h("li", {}, x)))) : null,
    more("Audit trail", h("ul", { class: "trail" }, d.events.map(e => h("li", {}, h("b", {}, e.event.replaceAll("_", " ")), ` by ${e.actor}. ${e.detail}`, h("time", {}, stamp(e.at)))))),
    more("Original document, accounts masked", h("pre", {}, d.raw)));
}
const fact = (a, b) => h("div", {}, h("span", {}, a), h("b", {}, b || "Not recorded"));
const more = (title, body) => h("details", { class: "more" }, h("summary", {}, title, icon("chevron", 18)), h("div", {}, body));
function decide(d) {
  if (!["READY", "HELD", "BLOCKED"].includes(d.state)) return null;
  const note = h("textarea", { class: "input", id: "note", rows: 2, placeholder: d.state === "HELD" ? "What did you check?" : "Why?" });
  const retain = h("input", { type: "checkbox", id: "retain" });
  const tds = h("input", { class: "input", id: "tdsIn", inputmode: "decimal", placeholder: "Amount in rupees" });
  const buttons = [];
  if (d.state === "HELD" && d.can_approve) buttons.push(h("button", { class: "btn filled", onclick: () => act("/api/approve", { id: d.id, note: note.value, retain_gst: retain.checked, tds_rupees: d.needs_tds ? tds.value : "" }, "Signed. It joins the next payment release.") }, icon("check", 18), "Approve with note"));
  if (d.can_alias) buttons.push(h("button", { class: "btn tonal", onclick: () => act("/api/alias", { id: d.id }, "Name confirmed and rechecked.") }, icon("building", 18), "Confirm new name"));
  buttons.push(h("button", { class: "btn outlined", onclick: () => act("/api/recheck", { id: d.id }, "Rechecked against the records.") }, icon("refresh", 18), "Recheck"));
  buttons.push(h("button", { class: "btn danger", onclick: () => act("/api/reject", { id: d.id, note: note.value }, "Rejected, with your reason on file.") }, icon("x", 18), "Reject"));
  return h("section", { class: "decide", "aria-label": "Your decision" }, h("h3", { class: "title-s" }, "Your decision"),
    h("div", { class: "grid2" }, h("label", { class: "field" }, h("span", {}, "Note for the audit trail"), note), reviewerField("byDecide")),
    d.needs_tds ? h("label", { class: "field", style: { marginBottom: "8px" } }, h("span", {}, "TDS to deduct"), tds) : null,
    d.can_retain_gst ? h("label", { class: "tick" }, retain, `Retain GST (${d.tax}) until the supplier files`) : null,
    h("div", { class: "actions" }, buttons));
}

/* Record side sheet */
async function openRecord(invoice, check) {
  let r;
  try { r = await get(`/api/record?invoice=${invoice}&check=${encodeURIComponent(check)}`); } catch { snack("That record is not available.", true); return; }
  const sheet = document.getElementById("sheet"), scrim = document.getElementById("scrim");
  const opener = document.activeElement;
  const close = () => { sheet.hidden = true; scrim.hidden = true; document.removeEventListener("keydown", onKey); opener?.focus?.(); };
  const onKey = e => { if (e.key === "Escape") close(); };
  const [label] = CHECKS[check] || [check];
  const body = r.kind === "passage"
    ? h("div", { class: "rec passage" }, r.lines.map(l => h("div", { class: l.hit ? "hit" : "" }, l.text)))
    : h("div", { class: "rec" }, r.rows.map(x => h("div", { class: "rec-row" + (x.hit ? " hit" : "") }, h("span", {}, x.label), h("span", {}, x.value))));
  sheet.replaceChildren(
    h("div", { class: "sheet-h" }, h("div", {}, h("div", { class: "label" }, label), h("h2", { class: "title", id: "sheet-title" }, r.title)), h("button", { class: "icon-btn", "aria-label": "Close", onclick: close, id: "sheetClose" }, icon("x"))),
    h("div", { class: "claim" }, tag(r.status, STATUS), h("p", {}, r.claim)),
    body,
    h("div", { class: "source-line" }, icon("link", 16), h("span", {}, r.url ? h("a", { href: r.url, target: "_blank", rel: "noopener noreferrer" }, r.url) : r.source)),
    h("div", { class: "source-line" }, icon("clock", 16), h("span", {}, `Retrieved ${day(r.retrieved)}`)));
  scrim.hidden = false; sheet.hidden = false; scrim.onclick = close;
  document.addEventListener("keydown", onKey);
  document.getElementById("sheetClose").focus();
}

/* Sign and release */
function renderDock() {
  const dock = document.getElementById("dock"), c = S.counts, p = S.payment_run, count = c.READY + c.APPROVED;
  const show = count > 0 && !S.job.running && (route[0] === "today" && !composerOpen || route[0] === "review");
  const key = JSON.stringify([show, count, p.net, c.READY]);
  if (sigs.dock === key) return; sigs.dock = key;
  dock.classList.toggle("on", show);
  if (!show) return;
  dock.replaceChildren(h("div", { class: "dockbar" }, h("div", {}, h("b", {}, p.net), h("small", {}, `${plural(count, "invoice")} net of TDS`)),
    h("button", { class: "btn", onclick: openSign }, icon("lock", 18), c.READY ? "Review and sign" : "Release payments")));
}
function holdButton(label, onDone) {
  let timer = null, viaKey = false;
  const btn = h("button", { class: "hold", type: "button", "aria-label": `${label}. Press and hold.` }, h("span", { class: "fill" }), icon("lock", 20), h("span", {}, label));
  const begin = () => { if (btn.disabled || timer) return; btn.classList.add("holding"); timer = setTimeout(() => { timer = null; btn.classList.remove("holding"); onDone(); }, 1000); };
  const end = () => { if (timer) { clearTimeout(timer); timer = null; btn.classList.remove("holding"); snackHint(); } };
  const snackHint = () => snack("Keep holding to confirm.");
  btn.addEventListener("pointerdown", e => { try { btn.setPointerCapture(e.pointerId); } catch { /* Not every pointer can be captured. */ } begin(); });
  btn.addEventListener("pointerup", end); btn.addEventListener("pointercancel", end);
  btn.addEventListener("keydown", e => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); viaKey = true; begin(); } });
  btn.addEventListener("keyup", e => { if (e.key === " " || e.key === "Enter") { e.preventDefault(); end(); } });
  btn.addEventListener("blur", end);
  btn.addEventListener("click", e => { if (e.detail === 0 && !viaKey) onDone(); viaKey = false; }); // Assistive tech activates without a press.
  return btn;
}
function openSign() {
  const dlg = document.getElementById("sign"), scrim = document.getElementById("scrim"), p = S.payment_run, c = S.counts, opener = document.activeElement;
  const close = () => { dlg.hidden = true; scrim.hidden = true; document.removeEventListener("keydown", onKey); opener?.focus?.(); };
  const onKey = e => {
    if (e.key === "Escape") return close();
    if (e.key !== "Tab") return;
    const items = [...dlg.querySelectorAll("button:not(:disabled),input")], first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  const confirm = async () => {
    if (!reviewer()) { snack("Enter the reviewer's name first", true); document.getElementById("bySign").focus(); return; }
    hold.disabled = true;
    try {
      if (S.counts.READY) await post("/api/signoff", { by: reviewer() });
      await post("/api/pay", { by: reviewer() });
      close(); composerOpen = false; snack("Signed. Issuing each payment once."); sigs = {}; go("today"); await tick();
    } catch (e) { snack(e.message, true); hold.disabled = false; }
  };
  const hold = holdButton(`Hold to sign and issue ${p.net}`, confirm);
  dlg.replaceChildren(h("div", { class: "sign-in" },
    h("div", { class: "sheet-h", style: { marginBottom: "4px" } }, h("h2", { class: "headline", id: "sign-title" }, "Sign this payment run"), h("button", { class: "icon-btn", "aria-label": "Close", onclick: close }, icon("x"))),
    h("p", { class: "body-s" }, `${S.client}. Issued in ${S.provider}.`),
    h("section", { class: "sign-total" }, h("div", { class: "label", style: { color: "inherit" } }, "Net to issue"), money(p.net),
      h("div", { class: "sign-sum" }, h("span", {}, "Gross", h("b", {}, p.gross)), h("span", {}, "TDS draft", h("b", {}, p.tds)), h("span", {}, "GST retained", h("b", {}, p.retained)))),
    h("div", { class: "sign-list" }, p.lines.map(l => h("div", { class: "sign-row" }, h("span", {}, l.vendor, h("small", {}, `${l.number}${l.due ? ` · MSME pay by ${day(l.due)}` : ""}`)), h("b", {}, l.net)))),
    c.BLOCKED + c.HELD ? h("p", { class: "body-s", style: { marginBottom: "12px" } }, `${plural(c.BLOCKED + c.HELD, "exception")} stay${c.BLOCKED + c.HELD === 1 ? "s" : ""} out of this run until you decide.`) : null,
    h("div", { style: { marginBottom: "12px" } }, reviewerField("bySign")),
    hold,
    h("div", { class: "sign-foot" }, h("span", { class: "body-s" }, "This cannot be undone. Your name goes on the audit trail."), h("button", { class: "btn text", onclick: close }, "Not yet"))));
  dlg.hidden = false; scrim.hidden = false; scrim.onclick = close;
  document.addEventListener("keydown", onKey);
  (reviewer() ? hold : document.getElementById("bySign")).focus();
}

/* Bank */
let bankData = null, bankDraft = "";
async function renderBank() {
  const data = await get("/api/statement").catch(() => null);
  if (!data || route[0] !== "bank") return;
  bankData = data;
  const key = "bank" + JSON.stringify([data.lines, S.job.running]);
  if (sigs.view === key || ["stmt", "byLine"].includes(document.activeElement?.id) || document.activeElement?.closest?.(".resolve")) return;
  sigs.view = key;
  const text = h("textarea", { class: "input", id: "stmt", rows: 5, "aria-label": "Statement lines", placeholder: "3 Oct 2026 · SWIGGY BANGALORE · ₹1,240", oninput: e => { bankDraft = e.target.value; } });
  text.value = bankDraft;
  const send = async body => { try { await post("/api/statement", body); bankDraft = ""; sigs.view = ""; await tick(); } catch (e) { snack(e.message, true); } };
  mount("bank", h("div", { class: "page" },
    h("header", { class: "top" }, h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "headline" }, "Bank statement")),
      h("div", { class: "chips" }, h("span", { class: "pill-note" }, icon("check", 16), `${data.posted} posted`), h("span", { class: "pill-note" }, icon("warn", 16), `${data.held} held`))),
    h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "4px" } }, "Post these lines to the right payee and account"),
      h("p", { class: "body-s", style: { marginBottom: "12px" } }, "A name alone never identifies a business. A line posts only through a payment Chukta issued, or a payee rule confirmed against the company's record."),
      text, h("div", { class: "actions" }, h("button", { class: "btn filled", disabled: S.job.running, onclick: () => send({ text: document.getElementById("stmt").value }) }, icon("play", 18), "Post lines"),
        h("button", { class: "btn tonal", disabled: S.job.running, onclick: () => send({ sample: true }) }, icon("receipt", 18), "Use October sample"))),
    data.lines.length ? h("section", { class: "card", style: { padding: "6px 0" }, "aria-label": "Posted lines" }, data.lines.map(lineRow)) : null));
}
function lineRow(l) {
  const payee = h("input", { class: "input", placeholder: "Payee", "aria-label": "Payee" }), account = h("input", { class: "input", placeholder: "Account", "aria-label": "Account" }), note = h("input", { class: "input", placeholder: "What confirmed this?", "aria-label": "Note" });
  return h("div", { class: "line" },
    h("span", { class: "sh " + l.status }, icon((STATUS[l.status] || [])[1] || "info", 19)),
    h("div", {}, h("div", { class: "title-s" }, l.narration), h("div", { class: "body-s" }, day(l.txn_date))),
    h("div", { class: "pay" }, l.payee ? h("div", {}, h("b", {}, l.payee), ` → ${l.account}`) : null, h("div", { class: "body-s" }, l.reason), h("div", { class: "body-s", style: { fontSize: "12px", overflowWrap: "anywhere" } }, `${l.source} · ${day(l.retrieved_at)}`)),
    h("div", { style: { textAlign: "right" } }, h("div", { class: "num", style: { fontWeight: 600 } }, l.amount), h("div", { style: { marginTop: "4px" } }, tag(l.status, STATUS))),
    l.status === "HELD" ? h("details", { class: "resolve" }, h("summary", { style: { cursor: "pointer", fontWeight: 600 } }, "Settle this line"),
      h("div", { style: { marginTop: "10px", display: "grid", gap: "8px" } }, h("div", { class: "form-row" }, payee, account), note, reviewerField(`byLine${l.id}`),
        h("div", { class: "actions", style: { marginTop: 0 } }, h("button", { class: "btn tonal", onclick: () => act("/api/line/resolve", { id: l.id, payee: payee.value, account: account.value, note: note.value }, "Posted, with your name on it.") }, "Post it"),
          h("button", { class: "btn text", onclick: () => act("/api/line/dismiss", { id: l.id, note: note.value }, "Dismissed, with your reason on file.") }, "Dismiss")))) : null);
}

/* Ledger */
async function renderLedger() {
  const d = await get("/api/ledger").catch(() => null);
  if (!d || route[0] !== "ledger") return;
  const key = "ledger" + JSON.stringify([d.total_calls, d.credits, d.usd]);
  if (sigs.view === key) return; sigs.view = key;
  const max = Math.max(1, ...d.by_source.map(s => s.calls));
  const names = { crustdata: "Crustdata", ifsc: "IFSC registry", model: "Model (DeepSeek)", razorpay_test: "Razorpay test mode" };
  mount("ledger", h("div", { class: "page" },
    h("header", { class: "top" }, h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "headline" }, "Cost ledger"))),
    h("section", { class: "stat-row", "aria-label": "Totals" },
      stat("Credits per invoice", String(d.per_invoice_credits), `${d.invoices} invoices`), stat("Model cost per invoice", `$${d.per_invoice_usd.toFixed(5)}`, "DeepSeek V4.1 Flash"),
      stat("Total credits", String(d.credits), "Crustdata"), stat("Calls recorded", String(d.total_calls), "Every source")),
    h("div", { class: "two" },
      h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "8px" } }, "Calls by source"), d.by_source.map(s => h("div", { class: "meter" },
        h("div", { class: "meter-h" }, h("span", {}, names[s.source] || s.source), h("b", {}, `${s.calls} calls${s.credits ? ` · ${s.credits} cr` : ""}${s.usd ? ` · $${s.usd}` : ""}`)),
        h("div", { class: "track" }, h("i", { style: { width: s.calls / max * 100 + "%" } }))))),
      d.run ? h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "8px" } }, "Latest run against its ceiling"),
        meter("Crustdata credits", d.run.credits, d.run.credit_limit, `${d.run.credits} of ${d.run.credit_limit}`),
        meter("Model spend", d.run.usd, d.run.model_usd_limit, `$${d.run.usd.toFixed(4)} of $${d.run.model_usd_limit.toFixed(2)}`),
        h("p", { class: "body-s" }, `Time limit ${Math.round(d.run.time_limit_s / 60)} minutes. When a ceiling is reached, Chukta holds what it cannot check.`)) : null),
    h("section", { class: "card", style: { marginTop: "14px", padding: "16px 12px" } }, h("h2", { class: "title", style: { margin: "0 12px 8px" } }, "Every call"),
      h("div", { class: "table-wrap" }, h("table", { class: "table" }, h("thead", {}, h("tr", {}, ["When", "Source", "Request", "Result", "Credits", "Model $"].map((x, i) => h("th", { class: i > 3 ? "r" : "", scope: "col" }, x)))),
        h("tbody", {}, d.calls.slice(0, 60).map(c => h("tr", {}, h("td", { style: { whiteSpace: "nowrap" } }, stamp(c.at)), h("td", {}, names[c.source] || c.source), h("td", {}, c.request), h("td", {}, c.outcome), h("td", { class: "r" }, c.credits ? String(c.credits) : "0"), h("td", { class: "r" }, c.usd ? c.usd.toFixed(5) : "0")))))))));
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
  const replay = () => { const fresh = list.cloneNode(true); list.replaceWith(fresh); snack(ok ? "Replayed. Every payment matches its sign-off." : "The replay found a problem.", !ok); };
  mount("audit", h("div", { class: "page" },
    h("header", { class: "top" }, h("div", {}, h("p", { class: "eyebrow" }, S.client), h("h1", { class: "headline" }, "Audit"))),
    h("section", { class: "hero " + (ok && n ? "good" : ok ? "" : "need") }, shaped("morph", ok ? "cookie" : "burst", icon(ok ? "shield" : "warn", 32)),
      h("div", { style: { flex: 1 } }, h("h2", { class: "headline" }, !n ? "Nothing signed yet" : ok ? `${plural(n, "payment")}, each signed and issued once` : "The books do not replay"),
        h("p", { class: "body-s" }, ok ? "Each payment is checked against its sign-off, its frozen evidence and the provider's record." : d.problems[0])),
      n ? h("button", { class: "btn filled", onclick: replay }, icon("history", 18), "Replay") : null),
    n ? h("section", { class: "card", style: { padding: "6px 0" }, "aria-label": "Replay" }, list) : null,
    h("section", { class: "card" }, h("h2", { class: "title", style: { marginBottom: "12px" } }, "The finished work"),
      h("div", { class: "exports" }, exportCard("/export/bank.csv", "bank", "Bank file", "Beneficiaries, amounts, references"), exportCard("/export/tally.csv", "receipt", "Tally vouchers", "Taxable, GST, TDS and net"), exportCard("/export/audit.json", "shield", "Audit file", "Every decision, source and call")))));
}
const exportCard = (href, ic, title, text) => h("a", { class: "export", href, download: "" }, icon(ic, 24), h("div", { class: "title-s" }, title), h("div", { class: "body-s" }, text));

/* Loop */
function renderView() {
  if (route[0] === "review") return renderReview();
  if (route[0] === "bank") return renderBank();
  if (route[0] === "ledger") return renderLedger();
  if (route[0] === "audit") return renderAudit();
  return renderToday();
}
async function tick() {
  clearTimeout(pollTimer);
  try {
    S = await get("/api/state");
    document.title = S.counts.BLOCKED + S.counts.HELD ? `(${S.counts.BLOCKED + S.counts.HELD}) Chukta` : "Chukta";
    renderRail(); await renderView(); renderDock();
    if (S.job.error && sigs.err !== S.job.error) { sigs.err = S.job.error; snack(S.job.error, true); }
  } catch { snack("Chukta is not responding. Restart it and the work resumes.", true); }
  pollTimer = setTimeout(tick, S?.job?.running ? 900 : 3000);
}
onRoute();
tick();
