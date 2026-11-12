/* HCC Workbench - front end. All cryptography runs in the Python modules via /api/*. */
"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const A = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const COLORS = ["#2457c5", "#0f8a72", "#b3261e", "#9a6200", "#6b4fa0", "#4a5563"];
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const state = { defaults: null, mode: "encrypt", last: null, savedLoaded: false };

/* ------------------------------------------------------------------ utilities */
function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const letters = s => (s || "").toUpperCase().replace(/[^A-Z]/g, "");
const group = (s, n = 5) => (s.match(new RegExp(`.{1,${n}}`, "g")) || []).join(" ");
const int = n => Number(n).toLocaleString("en-US");
function ms(v) { // v already in ms
  if (v === null || v === undefined || isNaN(v)) return "–";
  if (v < 0.01) return v.toFixed(4);
  if (v < 1) return v.toFixed(3);
  if (v < 100) return v.toFixed(2);
  return v.toFixed(0);
}

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  let data;
  try { data = await res.json(); } catch { throw new Error("The server returned an unreadable response."); }
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status}).`);
  return data;
}

function showError(el, msg) {
  if (!msg) { el.hidden = true; el.textContent = ""; return; }
  el.hidden = false; el.textContent = msg;
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.hidden = true; }, 1800);
}

async function copy(text, what) {
  try { await navigator.clipboard.writeText(text); toast(`${what} copied`); }
  catch { toast("Copy is blocked by the browser. Select the text instead."); }
}

async function busy(btn, fn) {
  const label = btn.textContent;
  btn.disabled = true; btn.textContent = "Working…";
  try { await fn(); } finally { btn.disabled = false; btn.textContent = label; }
}

function smallestPeriod(w) {
  for (let p = 1; p <= w.length; p++) {
    if (w.length % p === 0 && w.slice(0, p).repeat(w.length / p) === w) return p;
  }
  return w.length;
}

/* ------------------------------------------------------------------ navigation */
function showView(name) {
  $$(".nav-item").forEach(b => b.classList.toggle("is-active", b.dataset.view === name));
  $$(".view").forEach(v => v.classList.toggle("is-active", v.id === `view-${name}`));
  window.scrollTo({ top: 0 });
  if (name === "performance" && !state.savedLoaded) loadSaved();
  try { localStorage.setItem("hcc-view", name); } catch { /* storage unavailable */ }
}
$$(".nav-item").forEach(b => b.addEventListener("click", () => showView(b.dataset.view)));

/* ------------------------------------------------------------------ charts (SVG) */
function scale(d0, d1, r0, r1, log) {
  const f = log ? Math.log10 : (x => x);
  const a = f(d0), b = f(d1);
  return x => r0 + ((f(x) - a) / ((b - a) || 1)) * (r1 - r0);
}
function niceStep(range, count) {
  const raw = range / count, p = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / p;
  return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * p;
}
function linTicks(min, max, count = 5) {
  if (max === min) max = min + 1;
  const step = niceStep(max - min, count);
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}
function logTicks(min, max) {
  const out = [];
  for (let e = Math.floor(Math.log10(min)); e <= Math.ceil(Math.log10(max)); e++) out.push(Math.pow(10, e));
  return out;
}
function tickLabel(v) {
  if (v >= 1000) return int(v);
  if (v >= 1) return String(+v.toFixed(2));
  return String(+v.toPrecision(2));
}

function lineChart(o) {
  const W = o.width || 560, H = o.height || 300, m = { l: 58, r: 30, t: 14, b: 46 };
  const pts = o.series.flatMap(s => s.points);
  if (!pts.length) return "";
  let xmin = Math.min(...pts.map(p => p[0])), xmax = Math.max(...pts.map(p => p[0]));
  let ymin = o.yMin ?? Math.min(...pts.map(p => p[1])), ymax = o.yMax ?? Math.max(...pts.map(p => p[1]));
  let yt;
  if (o.logY) { yt = logTicks(ymin, ymax); ymin = yt[0]; ymax = yt[yt.length - 1]; }
  else { yt = linTicks(ymin, ymax); ymin = Math.min(ymin, yt[0]); ymax = Math.max(ymax, yt[yt.length - 1]); }
  const xt = o.xTicks || [...new Set(pts.map(p => p[0]))].sort((a, b) => a - b);
  if (xmin === xmax) { xmin -= 1; xmax += 1; }
  const X = scale(xmin, xmax, m.l, W - m.r, o.logX), Y = scale(ymin, ymax, H - m.b, m.t, o.logY);
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label || "chart")}">`;
  yt.forEach(v => {
    s += `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>`;
    s += `<text x="${m.l - 8}" y="${Y(v) + 4}" text-anchor="end">${tickLabel(v)}</text>`;
  });
  xt.forEach(v => { s += `<text x="${X(v)}" y="${H - m.b + 18}" text-anchor="middle">${tickLabel(v)}</text>`; });
  s += `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${H - m.b}" y2="${H - m.b}"/>`;
  if (o.vline !== undefined) {
    s += `<line x1="${X(o.vline)}" x2="${X(o.vline)}" y1="${m.t}" y2="${H - m.b}" stroke="#7b8592" stroke-dasharray="3 4"/>`;
    s += `<text x="${X(o.vline) + 5}" y="${m.t + 12}">${esc(o.vlineLabel || "")}</text>`;
  }
  o.series.forEach((ser, i) => {
    const c = ser.color || COLORS[i % COLORS.length];
    const d = ser.points.map((p, j) => `${j ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join("");
    s += `<path d="${d}" fill="none" stroke="${c}" stroke-width="2" ${ser.dash ? 'stroke-dasharray="6 4"' : ""}/>`;
    ser.points.forEach(p => {
      s += `<circle cx="${X(p[0])}" cy="${Y(p[1])}" r="3.2" fill="#fff" stroke="${c}" stroke-width="1.8"><title>${esc(ser.name)}: ${tickLabel(p[0])} → ${(+p[1]).toPrecision(4)}</title></circle>`;
    });
  });
  s += `<text class="ttl" x="${(m.l + W - m.r) / 2}" y="${H - 8}" text-anchor="middle">${esc(o.xLabel || "")}</text>`;
  s += `<text class="ttl" transform="translate(14 ${(m.t + H - m.b) / 2}) rotate(-90)" text-anchor="middle">${esc(o.yLabel || "")}</text>`;
  s += "</svg>";
  const legend = o.series.length > 1
    ? `<div class="legend">${o.series.map((ser, i) => `<span><i style="background:${ser.color || COLORS[i % COLORS.length]}"></i>${esc(ser.name)}</span>`).join("")}</div>` : "";
  return legend + s;
}

function barChart(o) {
  const W = o.width || 900, H = o.height || 250, m = { l: 52, r: 10, t: 12, b: 44 };
  const n = o.values.length; if (!n) return "";
  const yt = linTicks(0, Math.max(...o.values, o.minMax || 1));
  const ymax = yt[yt.length - 1];
  const bw = (W - m.l - m.r) / n, Y = scale(0, ymax, H - m.b, m.t);
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(o.label || "bar chart")}">`;
  yt.forEach(v => {
    s += `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>`;
    s += `<text x="${m.l - 8}" y="${Y(v) + 4}" text-anchor="end">${tickLabel(v)}</text>`;
  });
  const every = Math.ceil(n / 26);
  o.values.forEach((v, i) => {
    const x = m.l + i * bw, h = Math.max(0, Y(0) - Y(v));
    const c = o.color ? o.color(i, v) : COLORS[0];
    s += `<rect x="${x + bw * 0.16}" y="${Y(0) - h}" width="${bw * 0.68}" height="${h}" fill="${c}" rx="1.5"><title>${esc(o.labels[i])}: ${(+v).toPrecision(4)}</title></rect>`;
    if (o.zeroMark && v === 0) s += `<rect x="${x + bw * 0.16}" y="${Y(0) - 4}" width="${bw * 0.68}" height="4" fill="${o.zeroMark}"/>`;
    if (i % every === 0) s += `<text x="${x + bw / 2}" y="${H - m.b + 16}" text-anchor="middle">${esc(o.labels[i])}</text>`;
  });
  s += `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${Y(0)}" y2="${Y(0)}"/>`;
  s += `<text class="ttl" x="${(m.l + W - m.r) / 2}" y="${H - 8}" text-anchor="middle">${esc(o.xLabel || "")}</text>`;
  s += `<text class="ttl" transform="translate(14 ${(m.t + H - m.b) / 2}) rotate(-90)" text-anchor="middle">${esc(o.yLabel || "")}</text>`;
  return s + "</svg>";
}

/* Letter histogram with English reference ticks */
function freqChart(percent, opt = {}) {
  const W = opt.width || 640, H = opt.height || 230, m = { l: 40, r: 8, t: 10, b: 28 };
  const eng = state.defaults.englishPercent;
  const top = Math.max(14, ...percent, ...eng);
  const yt = linTicks(0, top, 4), ymax = yt[yt.length - 1];
  const bw = (W - m.l - m.r) / 26, Y = scale(0, ymax, H - m.b, m.t);
  let s = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Letter frequencies compared with English">`;
  yt.forEach(v => {
    s += `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}"/>`;
    s += `<text x="${m.l - 6}" y="${Y(v) + 4}" text-anchor="end">${v}%</text>`;
  });
  for (let i = 0; i < 26; i++) {
    const x = m.l + i * bw, h = Y(0) - Y(percent[i]);
    s += `<rect x="${x + bw * 0.18}" y="${Y(0) - h}" width="${bw * 0.64}" height="${Math.max(0, h)}" fill="${opt.color || "#2457c5"}" rx="1"><title>${A[i]}: ${percent[i].toFixed(2)}% (English ${eng[i].toFixed(2)}%)</title></rect>`;
    s += `<line x1="${x + bw * 0.06}" x2="${x + bw * 0.94}" y1="${Y(eng[i])}" y2="${Y(eng[i])}" stroke="#18202b" stroke-width="2"/>`;
    s += `<text x="${x + bw / 2}" y="${H - m.b + 16}" text-anchor="middle">${A[i]}</text>`;
  }
  s += `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${Y(0)}" y2="${Y(0)}"/>`;
  return s + "</svg>";
}

/* ------------------------------------------------------------------ cipher view */
function railFenceSVG(text, pattern, rails, limit = 140) {
  const n = Math.min(text.length, limit);
  const cw = 24, rh = 32, pl = 62, pt = 20;
  const W = pl + n * cw + 20, H = pt * 2 + (rails - 1) * rh;
  const x = i => pl + i * cw, y = r => pt + r * rh;
  let s = `<svg class="fence" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Rail fence with ${rails} rails">`;
  for (let r = 0; r < rails; r++) {
    s += `<line class="railline" x1="${pl - 10}" x2="${W - 8}" y1="${y(r)}" y2="${y(r)}"/>`;
    s += `<text class="rl" x="8" y="${y(r) + 4}">Rail ${r + 1}</text>`;
  }
  const pts = [];
  for (let i = 0; i < n; i++) pts.push(`${x(i)},${y(pattern[i])}`);
  s += `<polyline class="path" id="fence-path" points="${pts.join(" ")}"/>`;
  for (let i = 0; i < n; i++) {
    s += `<g data-r="${pattern[i]}"><circle class="dot" cx="${x(i)}" cy="${y(pattern[i])}" r="10.5"/><text class="ch" x="${x(i)}" y="${y(pattern[i])}">${text[i]}</text></g>`;
  }
  return s + "</svg>";
}

function railRows(text, pattern, rails) {
  const rows = Array.from({ length: rails }, () => "");
  for (let i = 0; i < text.length; i++) rows[pattern[i]] += text[i];
  return `<div class="rows">${rows.map((r, i) => `<div><b>Rail ${i + 1}</b><span>${esc(group(r)) || "—"}</span></div>`).join("")}</div>`;
}

function alignTable(top, keyword, bottom, labels, limit = 36) {
  const n = Math.min(top.length, limit), m = keyword.length;
  const row = (cls, label, f) => `<tr class="${cls}"><th>${label}</th>${Array.from({ length: n }, (_, i) =>
    `<td${i && i % m === 0 ? ' class="cycle"' : ""}>${f(i)}</td>`).join("")}</tr>`;
  return `<div class="align"><table>
    ${row("p", labels[0], i => top[i])}
    ${row("k", labels[1], i => keyword[i % m])}
    ${row("c", labels[2], i => bottom[i])}
  </table></div>`;
}

function stage(cls, name, sub, meta, body) {
  return `<article class="stage ${cls}"><div class="stage-top"><div class="stage-name">${name}${sub ? `<small>${sub}</small>` : ""}</div><div class="stage-meta">${meta || ""}</div></div>${body}</article>`;
}

function renderPipeline(d, mode) {
  const n = d.input.length, m = d.keyword.length;
  const fence = `<div class="fence-wrap">${railFenceSVG(d.fenceText, d.pattern, d.rails)}</div>`;
  const truncated = n > 140 ? `<p class="caption">Diagram shows the first 140 of ${int(n)} letters.</p>` : "";
  const alignNote = n > 36 ? `<p class="caption">Alignment shows the first 36 letters. Blue marks show where the keyword starts again.</p>` : `<p class="caption">Blue marks show where the keyword starts again.</p>`;
  let html = "";
  if (mode === "encrypt") {
    html += stage("", "Normalised plaintext", "", `${int(n)} letters${d.removed ? `, ${int(d.removed)} other characters removed` : ""}`,
      `<p class="letters">${esc(group(d.input))}</p>`);
    html += stage("s1", "Stage 1: Vigenère", "substitution", `<span class="formula">V[i] = (P[i] + K[i mod ${m}]) mod 26</span>`,
      alignTable(d.input, d.keyword, d.stage1, ["Plain", "Key", "Stage 1"]) + alignNote +
      `<h3>Stage 1 output</h3><p class="letters">${esc(group(d.stage1))}</p>`);
    html += stage("s2", "Stage 2: Rail Fence", "transposition", `${d.rails} rails, read rail by rail`,
      fence + truncated + railRows(d.fenceText, d.pattern, d.rails));
    html += stage("out", "Ciphertext", "", `${int(n)} letters`,
      `<p class="letters big">${esc(group(d.output))}</p>
       <div class="copy-row"><button class="btn btn-small" data-copy="out">Copy ciphertext</button>
       <button class="btn btn-small" data-go="kpa">Attack this ciphertext</button>
       <button class="btn btn-small" data-go="freq">Analyse its frequencies</button></div>`);
  } else {
    html += stage("", "Ciphertext", "", `${int(n)} letters`, `<p class="letters">${esc(group(d.input))}</p>`);
    html += stage("s2", "Undo stage 2: Rail Fence", "letters go back to their zig-zag positions", `${d.rails} rails`,
      fence + truncated + `<h3>Recovered stage 1 text</h3><p class="letters">${esc(group(d.stage1))}</p>`);
    html += stage("s1", "Undo stage 1: Vigenère", "subtract the keyword", `<span class="formula">P[i] = (V[i] − K[i mod ${m}]) mod 26</span>`,
      alignTable(d.stage1, d.keyword, d.output, ["Stage 1", "Key", "Plain"]) + alignNote);
    html += stage("out", "Plaintext", "", `${int(n)} letters`,
      `<p class="letters big">${esc(d.output)}</p><div class="copy-row"><button class="btn btn-small" data-copy="out">Copy plaintext</button></div>`);
  }
  if (d.warning) html = `<p class="note">${esc(d.warning)}</p>` + html;
  const box = $("#pipeline");
  box.innerHTML = html; box.hidden = false;
  $$("[data-copy]", box).forEach(b => b.addEventListener("click", () => copy(d.output, mode === "encrypt" ? "Ciphertext" : "Plaintext")));
  $$("[data-go]", box).forEach(b => b.addEventListener("click", () => {
    if (b.dataset.go === "kpa") { fillKpaFromLast(); showView("attack"); setAttack("known"); }
    else { $("#freq-text").value = d.output; showView("frequency"); $("#freq-form").requestSubmit(); }
  }));
  const path = $("#fence-path");
  if (path && !reduceMotion && path.getTotalLength) {
    const len = path.getTotalLength();
    path.style.strokeDasharray = len; path.style.strokeDashoffset = len;
    path.getBoundingClientRect();
    path.style.transition = "stroke-dashoffset 900ms ease-out";
    path.style.strokeDashoffset = 0;
  }
  // Hovering a letter highlights its whole rail, which is the order letters are read out.
  $$(".fence g[data-r]", box).forEach(g => {
    g.addEventListener("mouseenter", () => $$(`.fence g[data-r="${g.dataset.r}"]`, box).forEach(x => x.classList.add("hot")));
    g.addEventListener("mouseleave", () => $$(".fence g.hot", box).forEach(x => x.classList.remove("hot")));
  });
}

function setMode(mode) {
  state.mode = mode;
  $$(".seg-btn[data-mode]").forEach(b => b.classList.toggle("is-on", b.dataset.mode === mode));
  $("#cipher-text-label").textContent = mode === "encrypt" ? "Plaintext" : "Ciphertext";
  $("#cipher-run").textContent = mode === "encrypt" ? "Encrypt" : "Decrypt";
  $("#cipher-text").classList.toggle("mono", mode === "decrypt");
  if (mode === "decrypt" && state.last && !$("#cipher-text").dataset.touched) $("#cipher-text").value = state.last.ciphertext;
  if (mode === "encrypt" && !$("#cipher-text").dataset.touched) $("#cipher-text").value = state.last ? state.last.plaintextRaw : state.defaults.message;
  $("#pipeline").hidden = true;
  hideWalk();
  showError($("#cipher-error"), "");
}
$$(".seg-btn[data-mode]").forEach(b => b.addEventListener("click", () => setMode(b.dataset.mode)));
$("#cipher-text").addEventListener("input", e => { e.target.dataset.touched = "1"; });

function checkKeyword() {
  const raw = $("#cipher-key").value.trim().toUpperCase();
  const hint = $("#key-hint"), input = $("#cipher-key");
  let msg = "", ok = false;
  if (!raw) msg = "At least 10 letters, not a repeated shorter word.";
  else if (/[^A-Z]/.test(raw)) msg = "Letters A–Z only, no spaces or digits.";
  else if (raw.length < 10) msg = `${raw.length} letters. Needs at least 10.`;
  else if (smallestPeriod(raw) < 10) msg = `Repeats “${raw.slice(0, smallestPeriod(raw))}”, so its real length is only ${smallestPeriod(raw)}.`;
  else { msg = `${raw.length} letters, key space 26^${raw.length} ≈ 2^${(raw.length * Math.log2(26)).toFixed(1)}`; ok = true; }
  hint.textContent = msg;
  hint.className = "hint " + (raw ? (ok ? "good" : "bad") : "");
  input.setAttribute("aria-invalid", raw && !ok ? "true" : "false");
}
$("#cipher-key").addEventListener("input", checkKeyword);

$("#cipher-form").addEventListener("submit", e => {
  e.preventDefault();
  const btn = $("#cipher-run");
  busy(btn, async () => {
    showError($("#cipher-error"), "");
    const body = { keyword: $("#cipher-key").value, rails: $("#cipher-rails").value };
    try {
      let d;
      if (state.mode === "encrypt") {
        body.plaintext = $("#cipher-text").value;
        d = await api("/api/encrypt", body);
        state.last = { ciphertext: d.output, plaintext: d.input, plaintextRaw: body.plaintext, keyword: d.keyword, rails: d.rails };
      } else {
        body.ciphertext = $("#cipher-text").value;
        d = await api("/api/decrypt", body);
      }
      renderPipeline(d, state.mode);
      showWalk(d, state.mode);
    } catch (err) { showError($("#cipher-error"), err.message); $("#pipeline").hidden = true; hideWalk(); }
  });
});

$("#cipher-reset").addEventListener("click", () => {
  $("#cipher-key").value = state.defaults.keyword;
  $("#cipher-rails").value = state.defaults.rails;
  delete $("#cipher-text").dataset.touched;
  $("#cipher-text").value = state.mode === "encrypt" ? state.defaults.message : (state.last ? state.last.ciphertext : "");
  checkKeyword();
});

/* ------------------------------------------------------------------ step-by-step working of the ciphers
   After every Encrypt / Decrypt the result returned by /api/encrypt or /api/decrypt is worked
   through one letter at a time ("Perform next step"), stage by stage, in the order the stages are applied. No cryptography is
   done here: every letter shown comes from the server's answer (input, stage1, output, keyword,
   pattern, order). Each step is drawn from scratch from its index. */
const WALK_LIMIT = 120;
const walk = { d: null, mode: "encrypt", steps: [], first: {}, i: 0, ui: null };

function walkSteps(d, mode) {
  const n = d.input.length, steps = [], first = {};
  const add = (st, ph, count) => { if (!(st in first)) first[st] = steps.length; for (let i = 0; i < count; i++) steps.push({ st, ph, i }); };
  if (mode === "encrypt") {
    add("vig", "enc", n);
    add("rail", "write", n);
    add("rail", "read", n);
  } else {
    add("rail", "mark", 1);
    add("rail", "fill", n);
    add("rail", "zig", n);
    add("vig", "dec", n);
  }
  return { steps, first };
}

const STAGE_TITLE = {
  vig: { encrypt: ["Stage 1: Vigenère", "substitution using the Vigenère table"], decrypt: ["Undo stage 1: Vigenère", "subtract the key using the Vigenère table"] },
  rail: { encrypt: ["Stage 2: Rail Fence", "write the zig-zag, then read rail by rail"], decrypt: ["Undo stage 2: Rail Fence", "mark the zig-zag, fill it rail by rail, read it back"] },
};

function stripTable(rows) {
  const n = walk.d.input.length, m = walk.d.keyword.length;
  return `<div class="strip"><table>${rows.map(r => `<tr class="${r.cls}"><th>${r.label}</th>${
    Array.from({ length: n }, (_, i) => `<td${i && i % m === 0 && r.cycle ? ' class="cycle"' : ""}></td>`).join("")}</tr>`).join("")}</table></div>`;
}

function tableauHTML() {
  let h = `<table class="tableau" aria-label="Vigenère table: rows are key letters, columns are plaintext letters"><thead><tr><th class="corner">K \\ P</th>`;
  for (let c = 0; c < 26; c++) h += `<th>${A[c]}</th>`;
  h += "</tr></thead><tbody>";
  for (let r = 0; r < 26; r++) {
    h += `<tr><th>${A[r]}</th>`;
    for (let c = 0; c < 26; c++) h += `<td>${A[(r + c) % 26]}</td>`;
    h += "</tr>";
  }
  return h + "</tbody></table>";
}

function railSVG(n, rails, pattern) {
  const cw = 26, rh = 38, pl = 64, pt = 22;
  const W = pl + n * cw + 16, H = pt * 2 + (rails - 1) * rh;
  const x = i => pl + i * cw, y = r => pt + r * rh;
  walk.pt = i => `${x(i)},${y(pattern[i])}`;
  let s = `<svg class="fence rf" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Rail fence with ${rails} rails">`;
  for (let r = 0; r < rails; r++) {
    s += `<line class="railline" x1="${pl - 12}" x2="${W - 6}" y1="${y(r)}" y2="${y(r)}"/>`;
    s += `<text class="rl" x="6" y="${y(r) + 4}">Rail ${r + 1}</text>`;
  }
  s += `<polyline class="path" points="${Array.from({ length: n }, (_, i) => walk.pt(i)).join(" ")}"/>`;
  s += `<polyline class="trace" points=""/>`;
  for (let i = 0; i < n; i++) {
    s += `<g class="empty"><circle class="dot" cx="${x(i)}" cy="${y(pattern[i])}" r="11"/><text class="ch" x="${x(i)}" y="${y(pattern[i])}"></text></g>`;
  }
  return s + "</svg>";
}

function cardTop(st, mode, meta) {
  const [name, sub] = STAGE_TITLE[st][mode];
  return `<div class="stage-top"><div class="stage-name">${name}<small>${sub}</small></div><div class="stage-meta">${meta}</div></div>
    <p class="walk-say" aria-live="polite"></p>
    <div class="walk-ctl">
      <button type="button" class="btn btn-primary" data-next>Perform next step</button>
      <button type="button" class="btn" data-finish>Finish this part</button>
      <span class="walk-count"></span>
    </div>`;
}

function buildWalk(d, mode) {
  const n = d.input.length, m = d.keyword.length;
  const box = $("#walk");
  const enc = mode === "encrypt";
  const vigStrip = enc
    ? [{ cls: "p", label: "Plaintext P" }, { cls: "k", label: "Key K", cycle: true }, { cls: "o", label: "Stage 1 V" }]
    : [{ cls: "p", label: "Stage 1 V" }, { cls: "k", label: "Key K", cycle: true }, { cls: "o", label: "Plaintext P" }];
  const vigCard = `
    <div class="walk-card s1" data-card="vig" hidden>
      ${cardTop("vig", mode, `<span class="formula">${enc ? "Y = (X + K) mod 26" : "X = (Y − K) mod 26"}</span>`)}
      <div class="vg">
        <div class="vg-table">${tableauHTML()}</div>
        <div class="vg-side">
          <div class="calc">
            <div class="calc-title"></div>
            <div class="calc-row" data-c="a"><span class="calc-lbl"></span><b class="calc-l"></b><span class="calc-n"></span></div>
            <div class="calc-row" data-c="k"><span class="calc-lbl"></span><b class="calc-l"></b><span class="calc-n"></span></div>
            <div class="calc-eq"></div>
            <div class="calc-row out" data-c="o"><span class="calc-lbl"></span><b class="calc-l"></b><span class="calc-n"></span></div>
          </div>
          <p class="calc-how"></p>
          <p class="caption">Rule: ${enc ? "Y<sub>i</sub> = (X<sub>i</sub> + K<sub>i</sub>) mod 26" : "X<sub>i</sub> = (Y<sub>i</sub> − K<sub>i</sub>) mod 26"}, with A = 0 … Z = 25 and the ${m}-letter keyword repeated along the text.</p>
        </div>
      </div>
      ${stripTable(vigStrip)}
    </div>`;
  const railCard = `
    <div class="walk-card s2" data-card="rail" hidden>
      ${cardTop("rail", mode, `${d.rails} rails`)}
      <div class="rf-src"><span class="rf-lbl"></span><div class="rf-letters" data-r="src"></div></div>
      <div class="fence-wrap rf-wrap">${railSVG(n, d.rails, d.pattern)}</div>
      <div class="rows rf-rows"></div>
      <div class="rf-src rf-out"><span class="rf-lbl"></span><div class="rf-letters big" data-r="out"></div></div>
    </div>`;
  box.innerHTML = enc ? vigCard + railCard : railCard + vigCard;

  const tbl = $(".tableau", box);
  walk.ui = {
    box,
    cards: { vig: $('[data-card="vig"]', box), rail: $('[data-card="rail"]', box) },
    says: { vig: $('[data-card="vig"] .walk-say', box), rail: $('[data-card="rail"] .walk-say', box) },
    colHead: $$("thead th", tbl).slice(1),
    rowHead: $$("tbody th", tbl),
    cells: $$("tbody tr", tbl).map(tr => $$("td", tr)),
    lit: [],
    calc: { box: $(".calc", box), title: $(".calc-title", box), how: $(".calc-how", box), eq: $(".calc-eq", box),
      rows: ["a", "k", "o"].map(k => { const r = $(`[data-c="${k}"]`, box); return { r, lbl: $(".calc-lbl", r), l: $(".calc-l", r), n: $(".calc-n", r) }; }) },
    strip: $(".strip", box), vgWrap: $(".vg-table", box),
    stripRows: $$(".strip tr", box).map(tr => $$("td", tr)),
    svg: $(".rf", box), trace: $(".rf .trace", box), groups: $$(".rf g", box),
    rfWrap: $(".rf-wrap", box), rows: $(".rf-rows", box),
    src: $('[data-r="src"]', box), srcLbl: $(".rf-src .rf-lbl", box),
    out: $('[data-r="out"]', box), outLbl: $(".rf-out .rf-lbl", box),
  };
  // fixed rows of the strip (plaintext/stage 1 letters and the repeated key)
  const top = enc ? d.input : d.stage1;
  walk.ui.stripRows[0].forEach((td, i) => { td.textContent = top[i]; });
  walk.ui.stripRows[1].forEach((td, i) => { td.textContent = d.keyword[i % m]; });
}

function showWalk(d, mode) {
  const box = $("#walk");
  const n = d.input.length;
  if (n > WALK_LIMIT) {
    box.innerHTML = `<p class="note">The letter-by-letter working is shown for messages of up to ${WALK_LIMIT} letters so every step stays readable. This one has ${int(n)} letters; the complete result of each stage is shown below.</p>`;
    box.hidden = false; walk.d = null;
    return;
  }
  walk.d = d; walk.mode = mode; walk.i = 0;
  Object.assign(walk, walkSteps(d, mode));
  buildWalk(d, mode);
  // the user moves through the working one step at a time
  $$("[data-next]", box).forEach(btn => btn.addEventListener("click", () => walkGo(walk.i + 1)));
  $$("[data-finish]", box).forEach(btn => btn.addEventListener("click", () => walkGo(endOfPart(walk.i))));
  box.hidden = false;
  walkGo(0, true);
}

function hideWalk() { $("#walk").hidden = true; walk.d = null; }

/* last step of the part (phase) that step k belongs to; from the end of a part, the end of the next one */
function endOfPart(k) {
  const steps = walk.steps;
  if (k < steps.length - 1 && steps[k + 1].ph !== steps[k].ph) k += 1;
  const ph = steps[k].ph;
  while (k < steps.length - 1 && steps[k + 1].ph === ph) k += 1;
  return k;
}

function scrollIntoX(wrap, el) {
  if (!wrap || !el) return;
  const w = wrap.getBoundingClientRect(), r = el.getBoundingClientRect();
  if (r.left < w.left + 40 || r.right > w.right - 40) {
    // instant: Chrome cancels a smooth scroll when a second scroller starts one in the same frame
    wrap.scrollLeft += (r.left - w.left) - w.width / 2;
  }
}

function walkGo(k, force) {
  if (!walk.d) return;
  k = Math.max(0, Math.min(walk.steps.length - 1, k));
  if (k === walk.i && !force) return;
  walk.i = k;
  const s = walk.steps[k], u = walk.ui;
  // a stage's card appears when that stage starts and stays visible afterwards
  for (const st of ["vig", "rail"]) {
    const card = u.cards[st], show = walk.first[st] <= k;
    if (show && card.hidden) {
      card.hidden = false;
      if (k > 0) card.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    } else if (!show) card.hidden = true;
  }
  u.cards.vig.classList.toggle("is-active", s.st === "vig");
  u.cards.rail.classList.toggle("is-active", s.st === "rail");
  u.say = u.says[s.st];
  // only the card being worked on shows the step buttons; they disappear when the working is complete
  const last = k === walk.steps.length - 1;
  const hadFocus = document.activeElement && document.activeElement.closest("#walk .walk-ctl");
  for (const st of ["vig", "rail"]) $(".walk-ctl", u.cards[st]).hidden = st !== s.st || last;
  const ctl = $(".walk-ctl", u.cards[s.st]);
  $("[data-finish]", ctl).textContent = endOfPart(k) === k ? "Finish the next part" : "Finish this part";
  $(".walk-count", ctl).textContent = `Step ${k + 1} of ${walk.steps.length}`;
  if (hadFocus && !ctl.hidden) $("[data-next]", ctl).focus({ preventScroll: true });
  if (s.st === "vig") drawVig(s); else drawRail(s);
}

/* ---- Vigenère step: highlight the key row and plaintext column (or walk the row to the ciphertext letter) */
function drawVig(s) {
  const d = walk.d, u = walk.ui, i = s.i, m = d.keyword.length, n = d.input.length;
  const enc = s.ph === "enc";
  const top = enc ? d.input : d.stage1, bottom = enc ? d.stage1 : d.output;
  const K = d.keyword[i % m], kr = A.indexOf(K);
  const X = top[i], xn = A.indexOf(X), Y = bottom[i], yn = A.indexOf(Y);
  const STEP = reduceMotion ? 0 : 26;

  u.lit.forEach(el => { el.classList.remove("trail", "hit", "hd-on", "hd-ans"); el.style.removeProperty("--d"); });
  u.lit = [];
  const light = (el, cls, delay) => { el.style.setProperty("--d", `${delay}ms`); el.classList.add(cls); u.lit.push(el); };
  // re-trigger CSS animations on the intersection even when the same cell is hit twice in a row
  void u.box.offsetWidth;

  light(u.rowHead[kr], "hd-on", 0);
  if (enc) {
    // column of the plaintext letter from the top, row of the key letter from the left; they meet at the answer
    const col = xn, hit = u.cells[kr][col];
    light(u.colHead[col], "hd-on", 0);
    for (let r = 0; r < kr; r++) light(u.cells[r][col], "trail", r * STEP);
    for (let c = 0; c < col; c++) light(u.cells[kr][c], "trail", c * STEP);
    light(hit, "hit", Math.max(kr, col) * STEP);
  } else {
    // decryption: go along the key row until the ciphertext letter is found, then up to the column header
    const col = yn, hit = u.cells[kr][col];
    for (let c = 0; c < col; c++) light(u.cells[kr][c], "trail", c * STEP);
    light(hit, "hit", col * STEP);
    for (let r = kr - 1; r >= 0; r--) light(u.cells[r][col], "trail", (col + (kr - r)) * STEP);
    light(u.colHead[col], "hd-ans", (col + kr + 1) * STEP);
  }

  const c = u.calc, rows = c.rows;
  c.title.textContent = `Letter ${i + 1} of ${n}`;
  const set = (row, lbl, letter) => { row.lbl.textContent = lbl; row.l.textContent = letter; row.n.textContent = A.indexOf(letter); };
  if (enc) {
    set(rows[0], "Plaintext letter X", X);
    set(rows[1], `Key letter K (keyword letter ${(i % m) + 1})`, K);
    c.eq.textContent = `(${xn} + ${kr}) mod 26 = ${(xn + kr) % 26}`;
    set(rows[2], "Ciphertext letter Y", Y);
    c.how.innerHTML = `In the table, row <b>${K}</b> (key) crosses column <b>${X}</b> (plaintext) at <b>${Y}</b>.`;
    u.say.innerHTML = `<span class="tag s1">Stage 1</span> ${X} + ${K}: ${xn} + ${kr} = ${xn + kr}${xn + kr >= 26 ? `, minus 26 = ${xn + kr - 26}` : ""}, which is <b>${Y}</b>.`;
  } else {
    set(rows[0], "Ciphertext letter Y", X);
    set(rows[1], `Key letter K (keyword letter ${(i % m) + 1})`, K);
    c.eq.textContent = `(${xn} − ${kr}) mod 26 = ${(((xn - kr) % 26) + 26) % 26}`;
    set(rows[2], "Plaintext letter X", Y);
    c.how.innerHTML = `In row <b>${K}</b> (key), the letter <b>${X}</b> sits in column <b>${Y}</b>, so the plaintext letter is ${Y}.`;
    u.say.innerHTML = `<span class="tag s1">Undo stage 1</span> ${X} − ${K}: ${xn} − ${kr} = ${xn - kr}${xn - kr < 0 ? `, plus 26 = ${xn - kr + 26}` : ""}, which is <b>${Y}</b>.` +
      (i === n - 1 ? ` <span class="yes">Decryption complete.</span>` : "");
  }
  c.box.classList.remove("flash");
  void c.eq.offsetWidth;
  c.box.classList.add("flash");

  const [pRow, kRow, oRow] = u.stripRows;
  for (let j = 0; j < n; j++) {
    const cur = j === i;
    pRow[j].classList.toggle("cur", cur); kRow[j].classList.toggle("cur", cur); oRow[j].classList.toggle("cur", cur);
    oRow[j].textContent = j <= i ? bottom[j] : "";
    oRow[j].classList.toggle("new", cur);
  }
  scrollIntoX(u.strip, pRow[i]);
  scrollIntoX(u.vgWrap, u.cells[kr][enc ? xn : yn]);
}

/* ---- Rail Fence step */
function lettersHTML(text, upto, cur, dimUpto = -1) {
  let h = "";
  for (let j = 0; j < text.length; j++) {
    if (j > upto) break;
    const cls = [j === cur ? "new" : "", j <= dimUpto && j !== cur ? "used" : "", j % 5 === 4 ? "gap" : ""].filter(Boolean).join(" ");
    h += `<span${cls ? ` class="${cls}"` : ""}>${text[j]}</span>`;
  }
  return h || '<span class="none">…</span>';
}

function drawRail(s) {
  const d = walk.d, u = walk.ui, n = d.input.length, R = d.rails, pat = d.pattern, ord = d.order;
  const enc = walk.mode === "encrypt";
  const vText = d.stage1;                     // the zig-zag always holds the Stage 1 text
  const cText = enc ? d.output : d.input;     // the row-by-row reading is the ciphertext
  const pos = new Array(n);                   // position in the zig-zag -> index in the ciphertext
  ord.forEach((p, j) => { pos[p] = j; });
  const state = new Array(n).fill("empty");
  let cur = -1, traceTo = -1;

  if (s.ph === "write") { for (let p = 0; p <= s.i; p++) state[p] = "on"; cur = s.i; traceTo = s.i; }
  if (s.ph === "read") { state.fill("on"); for (let j = 0; j <= s.i; j++) state[ord[j]] = "read"; cur = ord[s.i]; }
  if (s.ph === "mark") { state.fill("ph"); }
  if (s.ph === "fill") { state.fill("ph"); for (let j = 0; j <= s.i; j++) state[ord[j]] = "on"; cur = ord[s.i]; }
  if (s.ph === "zig") { state.fill("on"); for (let p = 0; p <= s.i; p++) state[p] = "read"; cur = s.i; traceTo = s.i; }

  u.groups.forEach((g, p) => {
    const st = state[p];
    g.setAttribute("class", st + (p === cur ? " cur" : ""));
    g.lastChild.textContent = st === "empty" ? "" : st === "ph" ? "?" : vText[p];
  });
  u.trace.setAttribute("points", traceTo >= 0 ? Array.from({ length: traceTo + 1 }, (_, p) => walk.pt(p)).join(" ") : "");
  u.svg.classList.toggle("marking", s.ph === "mark");

  // letters per rail, in the order they sit on the rail
  const rails = Array.from({ length: R }, () => []);
  for (let p = 0; p < n; p++) rails[pat[p]].push(p);
  u.rows.innerHTML = rails.map((list, r) => {
    const cells = list.map(p => {
      const st = state[p];
      const ch = st === "empty" ? "" : st === "ph" ? "?" : vText[p];
      if (!ch) return "";
      return `<i class="${st}${p === cur ? " cur" : ""}">${ch}</i>`;
    }).join("");
    return `<div><b>Rail ${r + 1}</b><span>${cells || '<i class="none">·</i>'}</span><em>${list.length} letters</em></div>`;
  }).join("");

  const r = cur >= 0 ? pat[cur] : 0;
  const dir = p => { if (R === 1) return ""; if (pat[p] === 0) return p === 0 ? "start at the top rail" : "bounce off the top rail"; if (pat[p] === R - 1) return "bounce off the bottom rail"; return (p % (2 * (R - 1))) < R - 1 ? "moving down" : "moving up"; };

  if (s.ph === "write") {
    u.srcLbl.textContent = "Stage 1 text being written";
    u.src.innerHTML = lettersHTML(vText, n - 1, s.i, s.i - 1);
    u.outLbl.textContent = "Ciphertext";
    u.out.innerHTML = '<span class="none">read off once every letter is on the fence</span>';
    u.say.innerHTML = `<span class="tag s2">Stage 2</span> Letter ${s.i + 1} <b>${vText[s.i]}</b> goes on rail ${r + 1} (${dir(s.i)}).`;
  } else if (s.ph === "read") {
    u.srcLbl.textContent = "Stage 1 text";
    u.src.innerHTML = lettersHTML(vText, n - 1, -1);
    u.outLbl.textContent = "Ciphertext";
    u.out.innerHTML = lettersHTML(cText, s.i, s.i);
    const done = s.i === n - 1;
    u.say.innerHTML = `<span class="tag s2">Stage 2</span> Reading rail ${r + 1} left to right: <b>${vText[cur]}</b> is ciphertext letter ${s.i + 1}.` +
      (done ? ` <span class="yes">Encryption complete.</span>` : "");
  } else if (s.ph === "mark") {
    const counts = rails.map(l => l.length);
    u.srcLbl.textContent = "Ciphertext";
    u.src.innerHTML = lettersHTML(cText, n - 1, -1);
    u.outLbl.textContent = "Recovered Stage 1 text";
    u.out.innerHTML = '<span class="none">read along the zig-zag once the fence is full</span>';
    u.say.innerHTML = `<span class="tag s2">Undo stage 2</span> Draw the zig-zag for ${n} letters on ${R} rails and mark every place with ?. The rails hold ${counts.join(", ")} letters, so that is how the ciphertext is split.`;
  } else if (s.ph === "fill") {
    u.srcLbl.textContent = "Ciphertext";
    u.src.innerHTML = lettersHTML(cText, n - 1, s.i, s.i - 1);
    u.outLbl.textContent = "Recovered Stage 1 text";
    u.out.innerHTML = '<span class="none">read along the zig-zag once the fence is full</span>';
    u.say.innerHTML = `<span class="tag s2">Undo stage 2</span> Ciphertext letter ${s.i + 1} <b>${cText[s.i]}</b> fills the next ? on rail ${r + 1}.`;
  } else {
    u.srcLbl.textContent = "Ciphertext";
    u.src.innerHTML = lettersHTML(cText, n - 1, -1);
    u.outLbl.textContent = "Recovered Stage 1 text";
    u.out.innerHTML = lettersHTML(vText, s.i, s.i);
    u.say.innerHTML = `<span class="tag s2">Undo stage 2</span> Following the zig-zag (${dir(s.i)}), rail ${r + 1} gives <b>${vText[s.i]}</b> as letter ${s.i + 1}.`;
  }
  if (cur >= 0) scrollIntoX(u.rfWrap, u.groups[cur]);
  else u.rfWrap.scrollTo({ left: 0 });
}

// Right arrow also performs the next step (when not typing in a field)
document.addEventListener("keydown", e => {
  if (e.key !== "ArrowRight" || !walk.d || $("#walk").hidden || !$("#view-cipher").classList.contains("is-active")) return;
  if (e.target.closest("input, textarea, select, [contenteditable]")) return;
  e.preventDefault();
  walkGo(walk.i + 1);
});

/* ------------------------------------------------------------------ attack view */
function setAttack(kind) {
  $$(".seg-btn[data-attack]").forEach(b => b.classList.toggle("is-on", b.dataset.attack === kind));
  $("#kpa-form").hidden = kind !== "known";
  $("#coa-form").hidden = kind !== "cipher-only";
  $("#attack-out").hidden = true;
  showError($("#attack-error"), "");
}
$$(".seg-btn[data-attack]").forEach(b => b.addEventListener("click", () => setAttack(b.dataset.attack)));

function fillKpaFromLast() {
  if (!state.last) { showError($("#attack-error"), "Encrypt a message first, then come back here."); return false; }
  $("#kpa-cipher").value = state.last.ciphertext;
  $("#kpa-known").value = state.last.plaintext.slice(0, Math.min(16, state.last.plaintext.length));
  $("#kpa-offset").value = 0;
  $("#kpa-m").value = state.last.keyword.length;
  $("#kpa-original").value = state.last.plaintext;
  $("#attack-out").hidden = true;
  updateKnownHint();
  return true;
}

function updateKnownHint() {
  const k = letters($("#kpa-known").value).length;
  const ms_ = $("#kpa-m").value.split(/[,-]/).map(Number).filter(Boolean);
  const m = ms_.length ? Math.max(...ms_) : 0;
  const hint = $("#kpa-known-hint");
  if (!k) { hint.textContent = "Needs more letters than the key length to be decisive."; hint.className = "hint"; return; }
  if (!m) { hint.textContent = `${k} letters known.`; hint.className = "hint"; return; }
  if (k <= m) { hint.textContent = `${k} letters known, key length ${m}: not enough to rule out wrong rail counts.`; hint.className = "hint bad"; }
  else { hint.textContent = `${k} letters known, ${k - m} more than the key length. Each extra letter is a check.`; hint.className = "hint good"; }
}
["#kpa-known", "#kpa-m"].forEach(s => $(s).addEventListener("input", updateKnownHint));

$("#kpa-from-cipher").addEventListener("click", () => { showError($("#attack-error"), ""); fillKpaFromLast(); });
$("#kpa-demo").addEventListener("click", async () => {
  showError($("#attack-error"), "");
  try {
    const d = await api("/api/encrypt", { plaintext: state.defaults.message, keyword: state.defaults.keyword, rails: state.defaults.rails });
    state.last = { ciphertext: d.output, plaintext: d.input, plaintextRaw: state.defaults.message, keyword: d.keyword, rails: d.rails };
    fillKpaFromLast();
    toast("Demo ciphertext loaded. The keys are hidden from the attack.");
  } catch (err) { showError($("#attack-error"), err.message); }
});

/* ------------------------------------------------------------------ step-by-step working of the attack
   Replays the known-plaintext attack from the server's answer (r.working): for every rail guess,
   undo the fence, subtract the known plaintext to get key letters and check that the keyword
   repeats; then, for the chosen guess, read off the keyword, decrypt and verify.
   Nothing is computed here: every letter comes from attack.explain_guess() on the server. */
const atk = { r: null, steps: [], i: 0, box: null };

function atkSteps(r) {
  const steps = [];
  r.working.guesses.forEach((g, gi) => { steps.push({ t: "undo", gi }); steps.push({ t: "derive", gi }); });
  if (r.status === "recovered") steps.push({ t: "key" }, { t: "decrypt" }, { t: "verify" });
  else steps.push({ t: r.status === "partial" ? "partial" : "failed" });
  return steps;
}

function atkFence(g, n) {
  const R = g.rails, cw = 24, pl = 64, pt = 18;
  const rh = R <= 5 ? 34 : Math.max(15, Math.min(28, 190 / (R - 1)));
  const rad = rh < 22 ? 8 : 10.5;
  const W = pl + n * cw + 16, H = pt * 2 + (R - 1) * rh;
  const x = i => pl + i * cw, y = row => pt + row * rh;
  let s = `<svg class="fence rf atk-fence" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Ciphertext written back on ${R} rails">`;
  for (let row = 0; row < R; row++) {
    s += `<line class="railline" x1="${pl - 12}" x2="${W - 6}" y1="${y(row)}" y2="${y(row)}"/>`;
    if (R <= 12 || row % Math.ceil(R / 10) === 0 || row === R - 1) s += `<text class="rl" x="6" y="${y(row) + 4}">Rail ${row + 1}</text>`;
  }
  s += `<polyline class="path" points="${g.pattern.map((row, i) => `${x(i)},${y(row)}`).join(" ")}"/>`;
  const known = new Set(atk.r.working.guesses[0] ? g.letters.map(l => l.index) : []);
  g.pattern.forEach((row, i) => {
    s += `<g class="on${known.has(i) ? " kn" : ""}" style="--d:${i * 12}ms"><circle class="dot" cx="${x(i)}" cy="${y(row)}" r="${rad}"/><text class="ch" x="${x(i)}" y="${y(row)}"${rad < 10 ? ' style="font-size:11px"' : ""}>${g.stage1[i]}</text></g>`;
  });
  return s + "</svg>";
}

function atkLetters(text, mark) {
  return text.split("").map((ch, i) => `<span class="${[mark && mark.has(i) ? "kn" : "", i % 5 === 4 ? "gap" : ""].join(" ")}">${ch}</span>`).join("");
}

function buildAttackWalk(r) {
  const box = $("#kpa-walk");
  atk.r = r; atk.box = box;
  if (!r.working) {
    box.innerHTML = `<p class="note">The step-by-step working is shown for ciphertexts of up to 120 letters. This one has ${int(r.ciphertextLength)}; the full results are below.</p>`;
    return;
  }
  if (!r.working.guesses.length) { box.innerHTML = ""; return; }
  atk.steps = atkSteps(r); atk.i = 0;
  box.innerHTML = `
    <div class="walk-card atk">
      <div class="stage-top"><div class="stage-name">How the attack worked<small>one rail guess at a time</small></div>
        <div class="stage-meta"><span class="formula">K = (V′ − P) mod 26</span></div></div>
      <p class="walk-say" aria-live="polite"></p>
      <div class="walk-ctl">
        <button type="button" class="btn btn-attack" data-anext>Perform next step</button>
        <button type="button" class="btn" data-askip>Skip to the correct guess</button>
        <button type="button" class="btn" data-aend>Show the result</button>
        <span class="walk-count"></span>
      </div>
      <div class="atk-guesses"></div>
      <div class="atk-body"></div>
    </div>`;
  $("[data-anext]", box).addEventListener("click", () => atkGo(atk.i + 1));
  $("[data-aend]", box).addEventListener("click", () => atkGo(atk.steps.length - 1));
  const sel = r.selected, skip = $("[data-askip]", box);
  const gi = sel ? r.working.guesses.findIndex(g => g.rails === sel.rails) : -1;
  if (gi < 0) skip.hidden = true;
  else skip.addEventListener("click", () => atkGo(atk.steps.findIndex(s => s.t === "undo" && s.gi === gi)));
  atkGo(0, true);
}

function atkGo(k, force) {
  if (!atk.r) return;
  k = Math.max(0, Math.min(atk.steps.length - 1, k));
  if (k === atk.i && !force) return;
  atk.i = k;
  const r = atk.r, w = r.working, s = atk.steps[k], box = atk.box, m = w.keyLength;
  const say = $(".walk-say", box), body = $(".atk-body", box);
  const last = k === atk.steps.length - 1;
  $(".walk-ctl", box).querySelectorAll("button").forEach(b => { b.disabled = last; });
  $(".walk-count", box).textContent = `Step ${k + 1} of ${atk.steps.length}`;

  // row of guesses tried so far: rejected in red, consistent in green
  const doneUpTo = s.gi !== undefined ? s.gi - (s.t === "undo" ? 1 : 0) : w.guesses.length - 1;
  $(".atk-guesses", box).innerHTML = w.guesses.map((g, i) => {
    if (i > (s.gi !== undefined ? s.gi : w.guesses.length - 1)) return "";
    const cur = s.gi === i, judged = i <= doneUpTo;
    const cls = !judged ? "cur" : g.consistent ? "ok" : "bad";
    return `<span class="gchip ${cls}${cur ? " now" : ""}">r = ${g.rails}${judged ? (g.consistent ? " ✓" : ` ✗ ${g.conflicts}`) : ""}</span>`;
  }).join("");

  const known = w.known, knownIdx = new Set(w.guesses[0].letters.map(l => l.index));
  const tag = `<span class="tag atk">Attack</span>`;

  if (s.t === "undo") {
    const g = w.guesses[s.gi];
    const counts = Array.from({ length: g.rails }, (_, row) => g.pattern.filter(p => p === row).length);
    say.innerHTML = `${tag} Guess <b>r = ${g.rails}</b>: write the ciphertext back onto ${g.rails} rails, rail by rail (${counts.slice(0, 6).join(", ")}${counts.length > 6 ? ", …" : ""} letters), then read along the zig-zag. If the guess is right, this gives the Stage 1 text V′.`;
    body.innerHTML = `
      <div class="rf-src"><span class="rf-lbl">Intercepted ciphertext</span><div class="rf-letters">${atkLetters(w.ciphertext)}</div></div>
      <div class="fence-wrap rf-wrap">${atkFence(g, w.ciphertext.length)}</div>
      <div class="rf-src rf-out"><span class="rf-lbl">V′ (fence undone)</span><div class="rf-letters big">${atkLetters(g.stage1, knownIdx)}</div></div>
      <p class="caption">Underlined letters sit where the known plaintext <span class="mono">${esc(known)}</span> is.</p>`;
  } else if (s.t === "derive") {
    const g = w.guesses[s.gi];
    const cells = (f, cls) => g.letters.map(l => `<td class="${cls ? cls(l) : ""}">${f(l)}</td>`).join("");
    const st = l => l.status === "new" ? "new" : l.status === "agrees" ? "ok" : "bad";
    say.innerHTML = `${tag} For <b>r = ${g.rails}</b>, subtract each known plaintext letter from V′: K = (V′ − P) mod 26. Letters ${m} places apart use the same keyword letter, so they must agree. ` +
      (g.consistent ? `<span class="yes">Every check agrees: the key repeats correctly, so this guess is consistent.</span>`
        : `<span class="bad">${g.conflicts} check${g.conflicts > 1 ? "s" : ""} disagree, so r = ${g.rails} is rejected.</span>`);
    body.innerHTML = `
      <div class="strip atk-strip"><table>
        <tr><th>Position</th>${cells(l => l.index + 1)}</tr>
        <tr class="p"><th>Known P</th>${cells(l => l.plain)}</tr>
        <tr><th>V′</th>${cells(l => l.stage1)}</tr>
        <tr class="kk"><th>K = V′ − P</th>${cells(l => l.key, st)}</tr>
        <tr class="sl"><th>Keyword letter</th>${cells(l => l.slot + 1, st)}</tr>
      </table></div>
      <div class="atk-key"><span class="rf-lbl">Keyword from this guess</span>
        <div class="kbox-row">${g.keyword.split("").map(c => `<span class="kbox${c === "?" ? " unk" : ""}${g.consistent ? " good" : ""}">${c}</span>`).join("")}</div></div>
      <p class="caption"><span class="lg new"></span> first letter for that keyword position <span class="lg ok"></span> agrees with it <span class="lg bad"></span> contradicts it</p>`;
    body.querySelectorAll(".atk-strip td").forEach((td, i) => td.style.setProperty("--d", `${(i % g.letters.length) * 25}ms`));
  } else if (s.t === "key") {
    const sel = r.selected;
    const others = w.guesses.filter(g => g.consistent).length - 1;
    say.innerHTML = `${tag} ${others > 0 ? `${others + 1} guesses were consistent; the one whose decryption looks most like English was chosen` : `Only <b>r = ${sel.rails}</b> gave a consistent key`}. Its key letters, in keyword order, are the secret keyword.`;
    body.innerHTML = `<div class="atk-key big"><span class="rf-lbl">Recovered keys</span>
      <div class="kbox-row">${sel.keyword.split("").map((c, i) => `<span class="kbox good" style="--d:${i * 70}ms">${c}</span>`).join("")}</div>
      <p class="atk-rails">Rails = <b>${sel.rails}</b> &nbsp; Keyword = <b class="mono">${esc(sel.keyword)}</b></p></div>`;
  } else if (s.t === "decrypt") {
    const sel = r.selected, g = w.guesses.find(x => x.rails === sel.rails), n = g.stage1.length;
    say.innerHTML = `${tag} Now undo Stage 1 for the whole message: subtract the repeating keyword from V′, X = (Y − K) mod 26. The attacker never needed the keys to do this; they were recovered.`;
    body.innerHTML = `<div class="strip atk-dec"><table>
        <tr><th>V′</th>${g.stage1.split("").map(c => `<td>${c}</td>`).join("")}</tr>
        <tr class="k"><th>Keyword</th>${Array.from({ length: n }, (_, i) => `<td${i && i % m === 0 ? ' class="cycle"' : ""}>${sel.keyword[i % m]}</td>`).join("")}</tr>
        <tr class="o"><th>Plaintext</th>${r.plaintext.split("").map((c, i) => `<td class="new" style="--d:${i * 18}ms">${c}</td>`).join("")}</tr>
      </table></div>`;
  } else if (s.t === "verify") {
    say.innerHTML = `${tag} Check: encrypting the recovered plaintext with the recovered keys ${r.verified ? '<span class="yes">gives exactly the intercepted ciphertext.</span>' : '<span class="bad">does not give the intercepted ciphertext.</span>'}` +
      (r.matchesOriginal === true ? ' <span class="yes">It also matches the original message. Attack succeeded.</span>' : r.matchesOriginal === false ? ' <span class="bad">It differs from the original message.</span>' : "");
    body.innerHTML = `<div class="rf-src"><span class="rf-lbl">Recovered plaintext</span><div class="rf-letters big">${atkLetters(r.plaintext)}</div></div>
      <div class="rf-src"><span class="rf-lbl">Re-encrypted</span><div class="rf-letters">${atkLetters(w.ciphertext)}</div><span class="${r.verified ? "yes" : "bad"}">${r.verified ? "✓ same as intercepted" : "✗ different"}</span></div>`;
  } else if (s.t === "partial") {
    say.innerHTML = `${tag} <span class="bad">Not enough known plaintext.</span> The known letters cover only part of the ${m}-letter keyword, so several rail guesses look consistent and the keyword has gaps (?). Give more than ${m} known letters.`;
    body.innerHTML = "";
  } else {
    say.innerHTML = `${tag} <span class="bad">No rail guess gave a consistent key.</span> The assumptions are wrong: check the key length, the rail range, the position of the known text, or whether it really belongs to this ciphertext.`;
    body.innerHTML = "";
  }
  const wrap = $(".rf-wrap", body);
  if (wrap) wrap.scrollLeft = 0;
}

function renderKpa(r) {
  const tag = { recovered: ["ok", "Keys recovered"], partial: ["part", "Not enough known plaintext"], failed: ["fail", "Attack failed"] }[r.status];
  let html = `<div class="status ${tag[0]}"><div><div class="status-tag">${tag[1]}</div><p>${esc(r.message)}</p></div></div>`;
  const sel = r.selected;
  html += `<dl class="facts">
    <div class="fact key"><dt>Rails found</dt><dd>${sel ? sel.rails : "–"}</dd></div>
    <div class="fact key"><dt>Keyword found</dt><dd class="mono">${sel ? esc(sel.keyword) : "–"}</dd></div>
    <div class="fact"><dt>Hypotheses tested</dt><dd>${int(r.candidatesTested)}</dd></div>
    <div class="fact"><dt>Consistent</dt><dd>${int(r.consistent.length)}</dd></div>
    <div class="fact"><dt>Letter operations</dt><dd>${int(r.charOperations)}</dd></div>
    <div class="fact"><dt>Time</dt><dd>${ms(r.elapsedMs)} ms</dd></div>
  </dl>`;
  html += `<div id="kpa-walk"></div>`;
  if (r.plaintext) {
    const checks = [`Re-encrypting with the recovered keys ${r.verified ? '<span class="yes">reproduces the ciphertext exactly</span>' : '<span class="bad">does not reproduce the ciphertext</span>'}.`];
    if (r.matchesOriginal !== null) checks.push(r.matchesOriginal ? '<span class="yes">Matches the original message.</span>' : '<span class="bad">Differs from the original message.</span>');
    html += `<div class="panel"><h2>Recovered plaintext</h2><p class="letters">${esc(group(r.plaintext))}</p><p class="caption">${checks.join(" ")}</p></div>`;
  }

  // conflicts per rail guess
  const byRail = new Map();
  r.trace.forEach(t => byRail.set(t.rails, Math.min(byRail.has(t.rails) ? byRail.get(t.rails) : Infinity, t.conflicts)));
  const railsList = [...byRail.keys()];
  html += `<div class="panel"><h2>Contradictions per rail guess</h2>
    <p class="lead">For each guess the derived key letters are checked against each other. A wrong guess contradicts itself; the right one gives zero contradictions (shown in green on the axis).</p>
    ${barChart({ labels: railsList.map(String), values: railsList.map(k => byRail.get(k)), xLabel: "Rail count guessed", yLabel: "Contradictions",
      color: (i, v) => v === 0 ? "#0f8a72" : "#c9d1da", zeroMark: "#0f8a72", label: "Contradictions per rail guess" })}
  </div>`;

  html += `<div class="two">`;
  html += `<div class="panel"><h2>Search log</h2><div class="scroll"><table class="tbl"><thead><tr><th class="num">Rails</th><th class="num">Key length</th><th>Derived key</th><th class="num">Contradictions</th><th>Result</th></tr></thead><tbody>${
    r.trace.map(t => `<tr class="${sel && t.rails === sel.rails && t.keyLength === sel.keyLength ? "chosen" : t.consistent ? "hit" : ""}"><td class="num">${t.rails}</td><td class="num">${t.keyLength}</td><td class="mono">${esc(t.key)}</td><td class="num">${t.conflicts}</td><td>${t.consistent ? '<span class="yes">consistent</span>' : '<span class="no">rejected</span>'}</td></tr>`).join("")
  }</tbody></table></div></div>`;
  if (r.derivation.length) {
    html += `<div class="panel"><h2>Key derivation for rails = ${sel.rails}</h2><p class="lead">K = (V′ − P) mod 26, where V′ is the ciphertext with this rail count undone.</p><div class="scroll"><table class="tbl"><thead><tr><th class="num">i</th><th>P</th><th>V′</th><th class="num">i mod ${sel.keyLength}</th><th>K</th></tr></thead><tbody>${
      r.derivation.map(d => `<tr><td class="num">${d.index}</td><td class="mono">${d.plain}</td><td class="mono">${d.stage1}</td><td class="num">${d.slot}</td><td class="mono"><b>${d.key}</b> <span class="no">(${A.indexOf(d.stage1)} − ${A.indexOf(d.plain)} ≡ ${A.indexOf(d.key)})</span></td></tr>`).join("")
    }</tbody></table></div></div>`;
  }
  html += `</div>`;
  if (r.consistent.length > 1) {
    html += `<div class="panel"><h2>Surviving hypotheses</h2><p class="lead">More than one guess passed the check, so they are ranked by how close the decrypted text is to English (chi-squared, lower is better).</p><table class="tbl"><thead><tr><th class="num">Rails</th><th class="num">Key length</th><th>Keyword</th><th class="num">Chi-squared</th></tr></thead><tbody>${
      r.consistent.slice(0, 20).map((c, i) => `<tr class="${i === 0 ? "chosen" : ""}"><td class="num">${c.rails}</td><td class="num">${c.keyLength}</td><td class="mono">${esc(c.keyword)}</td><td class="num">${c.fitness === null ? "–" : c.fitness.toFixed(1)}</td></tr>`).join("")
    }</tbody></table></div>`;
  }
  const out = $("#attack-out"); out.innerHTML = html; out.hidden = false;
  buildAttackWalk(r);
  out.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
}

$("#kpa-form").addEventListener("submit", e => {
  e.preventDefault();
  busy(e.submitter || $("#kpa-form .btn-attack"), async () => {
    showError($("#attack-error"), "");
    try {
      renderKpa(await api("/api/attack/known", {
        ciphertext: $("#kpa-cipher").value, known: $("#kpa-known").value, offset: $("#kpa-offset").value,
        keyLengths: $("#kpa-m").value, railMin: $("#kpa-rmin").value, railMax: $("#kpa-rmax").value,
        languageModel: $("#kpa-lm").checked, original: $("#kpa-original").value,
      }));
    } catch (err) { showError($("#attack-error"), err.message); $("#attack-out").hidden = true; }
  });
});

$("#coa-demo").addEventListener("click", async () => {
  showError($("#attack-error"), "");
  try {
    const d = await api("/api/encrypt", { plaintext: state.defaults.longSample, keyword: state.defaults.keyword, rails: state.defaults.rails });
    $("#coa-cipher").value = d.output; $("#coa-original").value = d.input; $("#coa-m").value = d.keyword.length;
    toast("600-letter ciphertext loaded");
  } catch (err) { showError($("#attack-error"), err.message); }
});

$("#coa-form").addEventListener("submit", e => {
  e.preventDefault();
  busy(e.submitter || $("#coa-form .btn-attack"), async () => {
    showError($("#attack-error"), "");
    try {
      const r = await api("/api/attack/ciphertext-only", {
        ciphertext: $("#coa-cipher").value, keyLength: $("#coa-m").value,
        railMin: $("#coa-rmin").value, railMax: $("#coa-rmax").value, original: $("#coa-original").value,
      });
      const good = r.matchesOriginal;
      let html = good === null
        ? `<div class="status part"><div><div class="status-tag">Best guess</div><p>No original was given, so judge the output below: readable English means the keys are right.</p></div></div>`
        : good ? `<div class="status ok"><div><div class="status-tag">Keys recovered</div><p>The decrypted text matches the original message, without any known plaintext.</p></div></div>`
          : `<div class="status fail"><div><div class="status-tag">Attack failed</div><p>Statistics were not strong enough. Try a longer ciphertext; around 500 letters is usually enough for a 12-letter key.</p></div></div>`;
      html += `<dl class="facts">
        <div class="fact key"><dt>Rails found</dt><dd>${r.rails}</dd></div>
        <div class="fact key"><dt>Keyword found</dt><dd class="mono">${esc(r.keyword)}</dd></div>
        <div class="fact"><dt>Rail guesses</dt><dd>${r.candidatesTested}</dd></div>
        <div class="fact"><dt>Letter operations</dt><dd>${int(r.charOperations)}</dd></div>
        <div class="fact"><dt>Time</dt><dd>${ms(r.elapsedMs)} ms</dd></div>
        <div class="fact"><dt>Output chi-squared</dt><dd>${r.chi2.toFixed(1)}</dd></div>
      </dl>`;
      html += `<div class="panel"><h2>Decrypted text</h2><p class="letters">${esc(group(r.plaintext.slice(0, 600)))}${r.plaintext.length > 600 ? " …" : ""}</p></div>`;
      const sorted = [...r.ranking].sort((a, b) => a.rails - b.rails);
      html += `<div class="panel"><h2>Score per rail guess</h2><p class="lead">Sum of per-column chi-squared distances from English after the best shift for each column. The right rail count gives the lowest score.</p>${
        barChart({ labels: sorted.map(x => String(x.rails)), values: sorted.map(x => x.score), xLabel: "Rail count guessed", yLabel: "Chi-squared total",
          color: (i) => sorted[i].rails === r.rails ? "#0f8a72" : "#c9d1da", label: "Score per rail guess" })}</div>`;
      const out = $("#attack-out"); out.innerHTML = html; out.hidden = false;
    } catch (err) { showError($("#attack-error"), err.message); $("#attack-out").hidden = true; }
  });
});

/* ------------------------------------------------------------------ frequency view */
function icMeter(ic) {
  const lo = 0.03, hi = 0.075, pos = v => `${Math.max(0, Math.min(100, (v - lo) / (hi - lo) * 100))}%`;
  return `<div class="meter"><b style="left:${pos(ic)}"></b>
    <span style="left:${pos(state.defaults.icRandom)}">random 0.038</span>
    <span style="left:${pos(state.defaults.icEnglish)}">English 0.066</span></div>`;
}

$("#freq-form").addEventListener("submit", e => {
  e.preventDefault();
  busy(e.submitter || $("#freq-form .btn-primary"), async () => {
    showError($("#freq-error"), "");
    try {
      const r = await api("/api/frequency", { text: $("#freq-text").value });
      const out = $("#freq-out");
      out.innerHTML = `<div class="panel">
        <h2>Letter frequencies</h2>
        <div class="legend"><span><i style="background:#2457c5"></i>This text</span><span><i style="background:#18202b"></i>Standard English</span></div>
        ${freqChart(r.percent)}
        <div class="three" style="margin-top:14px">
          <div class="mini"><h3>Index of coincidence: ${r.ic.toFixed(4)}</h3>${icMeter(r.ic)}<p style="margin-top:20px">Chance that two letters picked at random are the same.</p></div>
          <div class="mini"><h3>Chi-squared vs English: ${r.chi2.toFixed(1)}</h3><p>Distance from the English histogram. Lower means more English-like.</p></div>
          <div class="mini"><h3>Best single shift: ${r.shiftGuess}</h3><p>Shifting back by ${r.shiftGuess} gives <span class="mono">${esc(r.shiftDecryption.slice(0, 40))}…</span></p><p>If that is not English, one shift cannot explain the text.</p></div>
        </div>
        <p class="caption">${int(r.length)} letters analysed.</p>
      </div>`;
      out.hidden = false;
    } catch (err) { showError($("#freq-error"), err.message); $("#freq-out").hidden = true; }
  });
});
$("#freq-last").addEventListener("click", () => {
  if (!state.last) { showError($("#freq-error"), "Encrypt a message first, then come back here."); return; }
  $("#freq-text").value = state.last.ciphertext; $("#freq-form").requestSubmit();
});
$("#freq-english").addEventListener("click", () => { $("#freq-text").value = state.defaults.longSample; $("#freq-form").requestSubmit(); });

$("#cmp-form").addEventListener("submit", e => {
  e.preventDefault();
  busy(e.submitter || $("#cmp-form .btn-primary"), async () => {
    showError($("#cmp-error"), "");
    try {
      const r = await api("/api/compare", { length: $("#cmp-n").value, shift: $("#cmp-shift").value });
      const colors = ["#4a5563", "#9a6200", "#2457c5"];
      let html = `<div class="three" style="margin-top:16px">${r.rows.map((row, i) => `<div class="mini">
        <h3>${esc(row.name)}</h3>${freqChart(row.percent, { width: 380, height: 170, color: colors[i] })}
        <p>IC ${row.ic.toFixed(4)}, chi-squared ${row.chi2.toFixed(0)}</p>
        <p>${i === 0 ? "Reference shape of English." : row.frequencyAttackRecovers
          ? `<span class="bad">Frequency attack recovers the message</span> (shift ${row.shiftGuess}).`
          : `<span class="yes">Frequency attack fails</span>: no single shift gives English.`}</p></div>`).join("")}</div>`;
      const t = r.timing;
      html += `<h3>Speed for ${int(r.length)} letters (mean of ${r.trials} runs)</h3>
        <table class="tbl"><thead><tr><th>Cipher</th><th class="num">Encrypt (ms)</th><th class="num">Decrypt (ms)</th><th class="num">Key space</th></tr></thead><tbody>
        <tr><td>Shift (single stage)</td><td class="num">${ms(t.shiftEncrypt)}</td><td class="num">${ms(t.shiftDecrypt)}</td><td class="num">26 ≈ 2^4.7</td></tr>
        <tr><td>HCC (two stages)</td><td class="num">${ms(t.hccEncrypt)}</td><td class="num">${ms(t.hccDecrypt)}</td><td class="num">26^12 × rails ≈ 2^${(r.keyspaceBits + Math.log2(19)).toFixed(1)}</td></tr>
        </tbody></table>
        <p class="caption">HCC encryption is ${(t.hccEncrypt / t.shiftEncrypt).toFixed(1)}× the Shift cipher's time on this run. Both grow linearly, O(n); the second stage adds a constant factor, not a higher order.</p>`;
      $("#cmp-out").innerHTML = html;
    } catch (err) { showError($("#cmp-error"), err.message); }
  });
});

/* ------------------------------------------------------------------ performance view */
function renderTiming(rows, source) {
  if (!rows || !rows.length) return `<p class="loading">No saved results yet. Run <code>python performance.py</code> or use Measure now.</p>`;
  const L = rows.map(r => r.length);
  const series = [
    ["HCC encrypt", "hcc_encrypt_s", "#2457c5"], ["HCC decrypt", "hcc_decrypt_s", "#0f8a72"],
    ["Shift encrypt", "shift_encrypt_s", "#9a6200", true], ["Shift decrypt", "shift_decrypt_s", "#6b4fa0", true],
  ].map(([name, k, color, dash]) => ({ name, color, dash, points: rows.map(r => [r.length, r[k] * 1000]) }));
  const first = rows[0], last = rows[rows.length - 1];
  const scaling = rows.length > 1 && last.length !== first.length
    ? `Length grew ${(last.length / first.length).toFixed(0)}×, HCC encryption time grew ${(last.hcc_encrypt_s / first.hcc_encrypt_s).toFixed(0)}×: linear, as O(n) predicts.` : "";
  return `<p class="caption">${esc(source)}</p>
    <div class="two">
      <div>${lineChart({ series, logX: true, logY: true, xLabel: "Message length (letters, log scale)", yLabel: "Mean time (ms, log)", label: "Encryption and decryption time" })}</div>
      <div>${lineChart({ series: [{ name: "Known-plaintext attack", color: "#b3261e", points: rows.map(r => [r.length, r.attack_s * 1000]) }], logX: true, logY: true, xLabel: "Ciphertext length (letters, log scale)", yLabel: "Attack time (ms, log)", label: "Attack time" })}
        <p class="caption">Attack: 36 known letters, key length 12, rails 2 to 20.</p></div>
    </div>
    <table class="tbl"><thead><tr><th class="num">Length</th><th class="num">HCC enc (ms)</th><th class="num">HCC dec (ms)</th><th class="num">Shift enc (ms)</th><th class="num">Shift dec (ms)</th><th class="num">Attack (ms)</th><th class="num">HCC / Shift</th></tr></thead><tbody>${
      rows.map(r => `<tr><td class="num">${int(r.length)}</td><td class="num">${ms(r.hcc_encrypt_s * 1000)}</td><td class="num">${ms(r.hcc_decrypt_s * 1000)}</td><td class="num">${ms(r.shift_encrypt_s * 1000)}</td><td class="num">${ms(r.shift_decrypt_s * 1000)}</td><td class="num">${ms(r.attack_s * 1000)}</td><td class="num">${(r.hcc_encrypt_s / r.shift_encrypt_s).toFixed(2)}×</td></tr>`).join("")
    }</tbody></table><p class="caption">${scaling}</p>`;
}

function renderSuccess(rows, source) {
  if (!rows || !rows.length) return `<p class="loading">No saved results yet.</p>`;
  const lengths = [...new Set(rows.map(r => r.length))];
  const mk = key => lengths.map((n, i) => ({ name: `n = ${int(n)}`, color: COLORS[i % COLORS.length], points: rows.filter(r => r.length === n).map(r => [r.known_k, r[key]]) }));
  return `<p class="caption">${esc(source)}</p>
    <div class="two">
      <div><h3>Unique answer from the contradiction check alone</h3>${lineChart({ series: mk("strict_pct"), yMin: 0, yMax: 100, xLabel: "Known letters k", yLabel: "Success (%)", vline: 12, vlineLabel: "key length", label: "Strict success" })}</div>
      <div><h3>Correct after ranking by English-likeness</h3>${lineChart({ series: mk("ranked_pct"), yMin: 0, yMax: 100, xLabel: "Known letters k", yLabel: "Success (%)", vline: 12, vlineLabel: "key length", label: "Ranked success" })}</div>
    </div>
    <div class="scroll"><table class="tbl"><thead><tr><th class="num">Ciphertext</th><th class="num">Known k</th><th class="num">Trials</th><th class="num">Strict %</th><th class="num">Ranked %</th><th class="num">Survivors</th><th class="num">Guesses</th><th class="num">Letter ops</th><th class="num">Time (ms)</th></tr></thead><tbody>${
      rows.map(r => `<tr class="${r.ranked_pct === 100 ? "hit" : ""}"><td class="num">${int(r.length)}</td><td class="num">${r.known_k}</td><td class="num">${r.trials}</td><td class="num">${r.strict_pct.toFixed(1)}</td><td class="num">${r.ranked_pct.toFixed(1)}</td><td class="num">${r.avg_survivors.toFixed(2)}</td><td class="num">${r.candidates_tested.toFixed(0)}</td><td class="num">${int(Math.round(r.avg_char_ops))}</td><td class="num">${ms(r.avg_time_s * 1000)}</td></tr>`).join("")
    }</tbody></table></div>
    <p class="caption">With k ≤ 12 every rail guess looks consistent, so the check alone cannot decide. From k = 13 each extra letter cuts a wrong guess's survival chance by about 26×.</p>`;
}

function renderCoa(rows, source) {
  if (!rows || !rows.length) return `<p class="loading">No saved results yet.</p>`;
  return `<p class="caption">${esc(source)}</p><div class="two"><div>${lineChart({
    series: [{ name: "Full recovery", color: "#b3261e", points: rows.map(r => [r.length, r.full_recovery_pct]) }],
    yMin: 0, yMax: 100, logX: true, xLabel: "Ciphertext length (letters, log scale)", yLabel: "Full recovery (%)", label: "Ciphertext-only success" })}</div>
    <div><table class="tbl"><thead><tr><th class="num">Ciphertext</th><th class="num">Trials</th><th class="num">Recovered %</th><th class="num">Letter ops</th><th class="num">Time (ms)</th></tr></thead><tbody>${
      rows.map(r => `<tr><td class="num">${int(r.length)}</td><td class="num">${r.trials}</td><td class="num">${r.full_recovery_pct.toFixed(1)}</td><td class="num">${int(Math.round(r.avg_char_ops))}</td><td class="num">${ms(r.avg_time_s * 1000)}</td></tr>`).join("")
    }</tbody></table><p class="caption">Short texts do not carry enough statistics per key column; a few hundred letters are enough.</p></div></div>`;
}

async function loadSaved() {
  state.savedLoaded = true;
  ["#tim-out", "#suc-out", "#coax-out"].forEach(s => { $(s).innerHTML = `<p class="loading">Loading saved results…</p>`; });
  try {
    const r = await api("/api/results");
    const src = name => `Saved full run, results/${name}`;
    $("#tim-out").innerHTML = renderTiming(r.timing, src("timing.csv"));
    $("#suc-out").innerHTML = renderSuccess(r.attack, src("attack_success.csv") + " (200 trials per cell)");
    $("#coax-out").innerHTML = renderCoa(r.cipherOnly, src("ciphertext_only.csv"));
  } catch (err) { $("#tim-out").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
}

function experiment(formSel, errSel, outSel, path, body, render) {
  $(formSel).addEventListener("submit", e => {
    e.preventDefault();
    busy(e.submitter || $(`${formSel} .btn-primary`), async () => {
      showError($(errSel), "");
      $(outSel).innerHTML = `<p class="loading">Running on this machine…</p>`;
      try {
        const r = await api(path, body());
        $(outSel).innerHTML = render(r.rows, `Measured just now on this machine${r.trials ? `, ${r.trials} trials` : ""}`);
      } catch (err) { showError($(errSel), err.message); $(outSel).innerHTML = ""; }
    });
  });
}
experiment("#tim-form", "#tim-error", "#tim-out", "/api/experiments/timing",
  () => ({ lengths: $("#tim-lengths").value, trials: $("#tim-trials").value }), renderTiming);
experiment("#suc-form", "#suc-error", "#suc-out", "/api/experiments/attack",
  () => ({ lengths: $("#suc-lengths").value, sizes: $("#suc-sizes").value, trials: $("#suc-trials").value }), renderSuccess);
experiment("#coax-form", "#coax-error", "#coax-out", "/api/experiments/ciphertext-only",
  () => ({ lengths: $("#coax-lengths").value, trials: $("#coax-trials").value }), renderCoa);

$("#full-run").addEventListener("click", e => {
  const status = $("#full-run-status");
  busy(e.currentTarget, async () => {
    showError($("#full-run-error"), "");
    status.textContent = "Running every experiment at full size. This takes about a minute…";
    try {
      const r = await api("/api/experiments/full", {});
      const src = name => `Saved full run, results/${name}`;
      $("#tim-out").innerHTML = renderTiming(r.timing, src("timing.csv"));
      $("#suc-out").innerHTML = renderSuccess(r.attack, src("attack_success.csv") + " (200 trials per cell)");
      $("#coax-out").innerHTML = renderCoa(r.cipherOnly, src("ciphertext_only.csv"));
      status.textContent = `Finished in ${r.seconds.toFixed(1)} s. results/*.csv and the graphs were updated.`;
    } catch (err) { status.textContent = ""; showError($("#full-run-error"), err.message); }
  });
});

/* ------------------------------------------------------------------ boot */
(async function boot() {
  try {
    state.defaults = await api("/api/defaults");
  } catch {
    document.querySelector(".main").innerHTML = `<div class="panel"><h2>The workbench server is not running</h2>
      <p class="lead">Open a terminal in the project folder and run <code>python app.py</code>, then reload this page.</p></div>`;
    return;
  }
  $("#cipher-text").value = state.defaults.message;
  $("#cipher-key").value = state.defaults.keyword;
  $("#cipher-rails").value = state.defaults.rails;
  checkKeyword();
  let start = "cipher";
  try { start = localStorage.getItem("hcc-view") || "cipher"; } catch { /* ignore */ }
  if (!$(`#view-${start}`)) start = "cipher";
  showView(start);
  $("#cipher-form").requestSubmit();
})();
