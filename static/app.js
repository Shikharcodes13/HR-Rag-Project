const $ = (id) => document.getElementById(id);

const stream = $("stream");
const hero = $("hero");
const form = $("composer");
const input = $("input");
const send = $("send");
const pill = $("statusPill");

let busy = false;

/* ----------------------------- status ----------------------------- */

function setPill(state, label) {
  pill.className = `status ${state}`;
  pill.innerHTML = `<i></i><span>${label}</span>`;
}

async function refreshStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    if (s.ready) {
      setPill("ok", "Policy indexed");
      $("docName").textContent = s.document || "HR Policy";
      $("docSub").textContent = `${s.chunks} indexed passages`;
    } else {
      setPill("bad", "No document");
      $("docName").textContent = "No policy indexed";
      $("docSub").textContent = "Upload a PDF to begin";
    }
    return s.ready;
  } catch {
    setPill("bad", "Server offline");
    return false;
  }
}

/* --------------------------- rendering --------------------------- */

const esc = (s) =>
  s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const BULLET = /^\s*([*\-•]|\d+[.)])\s+/;

const fmtInline = (s) =>
  s
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[(Section[^\]]+|Annexure[^\]]+)\]/g, '<span class="cite">$1</span>');

/**
 * Minimal, safe markdown: escape first, then format.
 * Handles blocks that mix prose with bullets, e.g. an intro line
 * followed by list items — which is how the model usually answers.
 */
const TABLE_ROW = /^\s*\|.*\|\s*$/;
const TABLE_RULE = /^\s*\|[\s:|-]+\|\s*$/;

const cells = (line) =>
  line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());

function renderAnswer(text) {
  return esc(text)
    .split(/\n{2,}/)
    .map((block) => {
      let html = "";
      let para = [];
      let items = [];
      let rows = [];

      const flushPara = () => {
        if (para.length) html += `<p>${fmtInline(para.join("<br>"))}</p>`;
        para = [];
      };
      const flushList = () => {
        if (items.length) html += `<ul>${items.join("")}</ul>`;
        items = [];
      };
      const flushTable = () => {
        if (!rows.length) return;
        const [head, ...body] = rows;
        const th = head.map((c) => `<th>${fmtInline(c)}</th>`).join("");
        const tb = body
          .map((r) => `<tr>${r.map((c) => `<td>${fmtInline(c)}</td>`).join("")}</tr>`)
          .join("");
        html += `<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>${tb}</tbody></table></div>`;
        rows = [];
      };

      for (const line of block.split("\n")) {
        if (TABLE_RULE.test(line)) continue; // the |---|---| separator
        if (TABLE_ROW.test(line)) {
          flushPara();
          flushList();
          rows.push(cells(line));
        } else if (BULLET.test(line)) {
          flushPara();
          flushTable();
          items.push(`<li>${fmtInline(line.replace(BULLET, ""))}</li>`);
        } else if (line.trim()) {
          flushList();
          flushTable();
          para.push(line);
        }
      }
      flushPara();
      flushList();
      flushTable();
      return html;
    })
    .join("");
}

function addUser(text) {
  hero?.remove();
  const el = document.createElement("div");
  el.className = "msg user";
  el.innerHTML = `<div class="bubble">${esc(text)}</div>`;
  stream.appendChild(el);
  el.scrollIntoView({ block: "end" });
}

function addBot() {
  const el = document.createElement("div");
  el.className = "msg bot";
  el.innerHTML = `
    <div class="bubble">
      <div class="bot-head">
        <div class="bot-avatar">XY</div>
        <span class="bot-name">HR Policy Assistant</span>
      </div>
      <div class="body"><div class="dots"><i></i><i></i><i></i></div></div>
    </div>`;
  stream.appendChild(el);
  el.scrollIntoView({ block: "end" });
  return el;
}

function fillBot(el, data) {
  const head = el.querySelector(".bot-head");
  const body = el.querySelector(".body");

  const tag = document.createElement("span");
  tag.className = `bot-tag${data.grounded ? "" : " ungrounded"}`;
  tag.textContent = data.grounded ? "Verified from PDF" : "Not in policy";
  head.appendChild(tag);

  let html = `<div class="answer">${renderAnswer(data.answer)}</div>`;

  if (data.sources?.length) {
    const rows = data.sources
      .map(
        (s) => `
        <div class="src">
          <span class="src-sec">${esc(s.section)}</span>
          <span class="src-page">Page ${s.page}</span>
          <span class="src-score">${Math.round(s.score * 100)}%</span>
        </div>`
      )
      .join("");
    html += `
      <details class="sources">
        <summary>${data.sources.length} source passage${data.sources.length === 1 ? "" : "s"} from ${esc(data.sources[0].source)}</summary>
        ${rows}
      </details>`;
  }

  body.innerHTML = html;
  el.scrollIntoView({ block: "end" });
}

function fillError(el, message) {
  el.querySelector(".body").innerHTML = `<div class="error">${esc(message)}</div>`;
}

/* ------------------------------ ask ------------------------------ */

async function ask(question) {
  if (busy || !question.trim()) return;
  busy = true;
  send.disabled = true;
  input.value = "";

  addUser(question);
  const bot = addBot();

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Something went wrong.");
    fillBot(bot, data);
  } catch (err) {
    fillError(bot, err.message);
  } finally {
    busy = false;
    send.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  ask(input.value);
});

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-q]");
  if (btn) ask(btn.dataset.q);
});

/* ---------------------------- upload ---------------------------- */

$("fileInput").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const label = $("uploadLabel");
  const text = $("uploadText");
  label.classList.add("busy");
  text.textContent = "Indexing…";
  setPill("", "Indexing document");

  try {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed.");

    stream.innerHTML = "";
    const note = addBot();
    fillBot(note, {
      answer: `**${data.document}** is indexed and ready — ${data.chunks} passages embedded. Ask me anything from it.`,
      sources: [],
      grounded: true,
    });
  } catch (err) {
    const note = addBot();
    fillError(note, err.message);
  } finally {
    label.classList.remove("busy");
    text.textContent = "Replace policy PDF";
    e.target.value = "";
    refreshStatus();
  }
});

refreshStatus();
input.focus();
