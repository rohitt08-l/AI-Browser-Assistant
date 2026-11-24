"use strict";

// ---------------------------------------------------------------------------
// Config & state
// ---------------------------------------------------------------------------
// DEFAULT_BACKEND comes from config.js
const HISTORY_LIMIT = 10; // past messages sent to the backend for follow-ups
const MAX_HISTORY_CHARS = 20000;
const TASK_LABELS = {
  qa: "Answer",
  summarize: "Summary",
  notes: "Notes",
  generate_doc: "Document",
};
const CHIP_PROMPTS = {
  summarize: "Summarize this page",
  notes: "Create key notes for this page",
  generate_doc: "Create a PDF document from this page",
};

const $ = (id) => document.getElementById(id);
const els = {
  chat: $("chat"),
  empty: $("emptyState"),
  question: $("question"),
  taskType: $("taskType"),
  send: $("sendBtn"),
  stop: $("stopBtn"),
  banner: $("banner"),
  toast: $("toast"),
  pageTitle: $("pageTitle"),
  pageIcon: $("pageIcon"),
  pageBar: $("pageBar"),
  settingsPanel: $("settingsPanel"),
  backendUrl: $("backendUrl"),
  settingsStatus: $("settingsStatus"),
};

const state = {
  windowId: null,
  tab: null, // currently displayed tab
  chats: new Map(), // tabId -> { url, messages: [{role, content, task?, fileUrl?, error?, selection?}] }
  streaming: null, // { tabId, controller }
  backendUrl: DEFAULT_BACKEND,
};

// ---------------------------------------------------------------------------
// Markdown rendering (sanitised)
// ---------------------------------------------------------------------------
const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
marked.setOptions({ gfm: true, breaks: false });
// Show raw HTML in model output as text instead of interpreting it.
marked.use({ renderer: { html: ({ text }) => escapeHtml(text) } });
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
  }
});
const renderMarkdown = (text) => DOMPurify.sanitize(marked.parse(text || ""));

// ---------------------------------------------------------------------------
// Storage (chat lives in session storage: cleared when the browser closes)
// ---------------------------------------------------------------------------
const chatKey = (tabId) => `chat:${tabId}`;

async function loadChat(tabId) {
  if (state.chats.has(tabId)) return state.chats.get(tabId);
  let chat = { url: "", messages: [] };
  try {
    const stored = await chrome.storage.session.get(chatKey(tabId));
    if (stored[chatKey(tabId)]) chat = stored[chatKey(tabId)];
  } catch (e) {
    console.warn("Could not read chat", e);
  }
  state.chats.set(tabId, chat);
  return chat;
}

function saveChat(tabId) {
  const chat = state.chats.get(tabId);
  if (!chat) return;
  chrome.storage.session.set({ [chatKey(tabId)]: chat }).catch((e) => console.warn("Could not save chat", e));
}

async function loadSettings() {
  try {
    const { backendUrl } = await chrome.storage.sync.get("backendUrl");
    state.backendUrl = (backendUrl || DEFAULT_BACKEND).replace(/\/+$/, "");
  } catch (e) {
    state.backendUrl = DEFAULT_BACKEND;
  }
  els.backendUrl.value = state.backendUrl;
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
const sameDocument = (a, b) => {
  try {
    const ua = new URL(a);
    const ub = new URL(b);
    return ua.origin + ua.pathname + ua.search === ub.origin + ub.pathname + ub.search;
  } catch {
    return a === b;
  }
};

async function showTab(tab) {
  if (!tab) return;
  state.tab = tab;
  const chat = await loadChat(tab.id);
  // A new page in the same tab starts a new conversation.
  if (chat.url && tab.url && !sameDocument(chat.url, tab.url) && state.streaming?.tabId !== tab.id) {
    chat.messages = [];
    chat.url = tab.url;
    saveChat(tab.id);
  }
  els.pageTitle.textContent = tab.title || tab.url || "Untitled page";
  els.pageBar.title = tab.url || "";
  els.pageIcon.src = tab.favIconUrl && /^https?:|^data:/.test(tab.favIconUrl) ? tab.favIconUrl : "";
  hideBanner();
  renderChat();
  updateControls();
}

async function refreshActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, windowId: state.windowId });
  await showTab(tab);
}

chrome.tabs.onActivated.addListener((info) => {
  if (info.windowId === state.windowId) refreshActiveTab();
});
chrome.tabs.onUpdated.addListener((tabId, change, tab) => {
  if (tabId === state.tab?.id && tab.active && (change.url || change.title || change.favIconUrl || change.status === "complete")) {
    showTab(tab);
  }
});
chrome.tabs.onRemoved.addListener((tabId) => {
  state.chats.delete(tabId);
  chrome.storage.session.remove(chatKey(tabId)).catch(() => {});
});

// ---------------------------------------------------------------------------
// Page extraction
// ---------------------------------------------------------------------------
class UserFacingError extends Error {
  constructor(message, action) {
    super(message);
    this.action = action; // optional { label, run }
  }
}

const RESTRICTED = /^(chrome|edge|brave|opera|vivaldi|about|chrome-extension|devtools|view-source):|^https:\/\/(chromewebstore\.google\.com|chrome\.google\.com\/webstore)/i;

async function extractPage(tab) {
  const url = tab.url || "";
  if (!url || RESTRICTED.test(url)) {
    throw new UserFacingError("This page can't be read by extensions (browser and Web Store pages are protected). Open a regular website and try again.");
  }
  if (/\.pdf($|[?#])/i.test(url)) {
    throw new UserFacingError("PDF files opened in Chrome's viewer can't be read yet. Try an HTML version of the document.");
  }

  let results;
  try {
    results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["lib/Readability.js", "extractor.js"],
    });
  } catch (err) {
    const msg = String(err?.message || err);
    if (url.startsWith("file:")) {
      throw new UserFacingError('To read local files, enable "Allow access to file URLs" for this extension in chrome://extensions.');
    }
    if (/permission|Cannot access|must request/i.test(msg)) {
      const origin = new URL(url).origin + "/*";
      throw new UserFacingError("The assistant needs permission to read this site.", {
        label: "Allow access to this site",
        run: async () => {
          const granted = await chrome.permissions.request({ origins: [origin] });
          if (granted) {
            hideBanner();
            toast("Access granted. Send your question again.");
          }
        },
      });
    }
    throw new UserFacingError(`Couldn't read this page: ${msg}`);
  }

  const page = results?.[0]?.result;
  if (!page || !page.content) {
    throw new UserFacingError("This page doesn't seem to have any readable text yet. Wait for it to finish loading and try again.");
  }
  return page;
}

// ---------------------------------------------------------------------------
// Backend (SSE streaming)
// ---------------------------------------------------------------------------
async function streamAnswer(payload, signal, onEvent) {
  let res;
  try {
    res = await fetch(`${state.backendUrl}/ask/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    throw new UserFacingError(`Can't reach the backend at ${state.backendUrl}. Make sure it is running, or change the URL in settings.`, {
      label: "Open settings",
      run: () => toggleSettings(true),
    });
  }

  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d) => d.msg.replace(/^Value error, /, "")).join("; ");
    } catch {}
    throw new UserFacingError(`The backend rejected the request: ${detail}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const data = raw
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart())
        .join("\n");
      if (!data) continue;
      const event = JSON.parse(data);
      if (event.type === "error") throw new UserFacingError(event.message);
      onEvent(event);
    }
  }
}

// ---------------------------------------------------------------------------
// Sending
// ---------------------------------------------------------------------------
async function send({ question, task }) {
  if (state.streaming) return;
  const tab = state.tab;
  if (!tab) return;

  question = (question || "").trim();
  if (!question && (task === "auto" || task === "qa")) {
    els.question.focus();
    return;
  }
  hideBanner();

  const chat = await loadChat(tab.id);
  chat.url = tab.url;
  const history = chat.messages
    .filter((m) => !m.error && m.content)
    .slice(-HISTORY_LIMIT)
    .map((m) => ({ role: m.role, content: m.content.slice(0, MAX_HISTORY_CHARS) }));

  const controller = new AbortController();
  state.streaming = { tabId: tab.id, controller };
  updateControls();

  const userMsg = { role: "user", content: question || CHIP_PROMPTS[task] || "" };
  const reply = { role: "assistant", content: "", task: task === "auto" ? null : task, pending: true, status: "Reading page..." };
  chat.messages.push(userMsg, reply);
  els.question.value = "";
  autosize();
  renderChat();

  try {
    const page = await extractPage(tab);
    if (page.selection) userMsg.selection = page.selection;
    reply.status = "Thinking...";
    renderChat();

    await streamAnswer(
      {
        question,
        task_type: task,
        page_content: page.content,
        page_title: page.title,
        page_url: page.url,
        selection: page.selection,
        history,
      },
      controller.signal,
      (event) => {
        if (event.type === "meta") reply.task = event.task;
        else if (event.type === "status") reply.status = event.message;
        else if (event.type === "token") {
          reply.content += event.content;
          reply.status = null;
        } else if (event.type === "done" && event.file_url) reply.fileUrl = event.file_url;
        scheduleRender(tab.id);
      },
    );
    if (!reply.content) throw new UserFacingError("The AI returned an empty response. Please try again.");
  } catch (err) {
    if (err.name === "AbortError") {
      if (!reply.content) reply.content = "_Stopped._";
    } else {
      if (!(err instanceof UserFacingError)) console.error(err);
      // Drop the failed exchange from history; show the error inline.
      reply.error = err instanceof UserFacingError ? err.message : "Something went wrong. Please try again.";
      if (err.action) showBanner(err.message, err.action);
    }
  } finally {
    reply.pending = false;
    reply.status = null;
    state.streaming = null;
    saveChat(tab.id);
    if (state.tab?.id === tab.id) renderChat();
    updateControls();
  }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
let renderQueued = false;
function scheduleRender(tabId) {
  if (renderQueued || state.tab?.id !== tabId) return;
  renderQueued = true;
  requestAnimationFrame(() => {
    renderQueued = false;
    renderChat();
  });
}

const ICONS = {
  copy: '<svg viewBox="0 0 24 24"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>',
  download: '<svg viewBox="0 0 24 24"><path d="M12 4v11M7 10l5 5 5-5M5 20h14"/></svg>',
};

function renderChat() {
  const chat = state.tab ? state.chats.get(state.tab.id) : null;
  const messages = chat?.messages || [];
  const nearBottom = els.chat.scrollHeight - els.chat.scrollTop - els.chat.clientHeight < 80;

  els.chat.replaceChildren();
  if (!messages.length) {
    els.chat.appendChild(els.empty);
    return;
  }

  for (const m of messages) {
    const div = document.createElement("div");
    div.className = `msg ${m.role}${m.error ? " error" : ""}`;

    if (m.role === "user") {
      if (m.selection) {
        const q = document.createElement("span");
        q.className = "quote";
        q.textContent = m.selection.length > 160 ? m.selection.slice(0, 160) + "..." : m.selection;
        div.appendChild(q);
      }
      div.appendChild(document.createTextNode(m.content));
    } else {
      if (m.task && TASK_LABELS[m.task]) {
        const label = document.createElement("div");
        label.className = "msg-label";
        label.textContent = TASK_LABELS[m.task];
        div.appendChild(label);
      }
      const body = document.createElement("div");
      body.className = "body";
      if (m.error) {
        body.textContent = m.error;
      } else if (!m.content && m.status) {
        body.innerHTML = "";
        const s = document.createElement("span");
        s.className = "status typing";
        s.textContent = m.status;
        body.appendChild(s);
      } else {
        body.innerHTML = renderMarkdown(m.content);
        if (m.pending) body.classList.add("typing");
      }
      div.appendChild(body);

      if (!m.pending && !m.error && m.content) {
        const actions = document.createElement("div");
        actions.className = "msg-actions";
        const copy = document.createElement("button");
        copy.innerHTML = `${ICONS.copy}<span>Copy</span>`;
        copy.addEventListener("click", () => copyText(m.content));
        actions.appendChild(copy);
        if (m.fileUrl) {
          const a = document.createElement("a");
          a.className = "download";
          a.href = m.fileUrl;
          a.target = "_blank";
          a.rel = "noopener";
          a.innerHTML = `${ICONS.download}<span>Download PDF</span>`;
          actions.appendChild(a);
        }
        div.appendChild(actions);
      }
    }
    els.chat.appendChild(div);
  }
  if (nearBottom || state.streaming) els.chat.scrollTop = els.chat.scrollHeight;
}

function updateControls() {
  const busy = Boolean(state.streaming);
  els.send.hidden = busy;
  els.stop.hidden = !busy;
  document.querySelectorAll(".chip").forEach((c) => (c.disabled = busy || !state.tab));
  els.send.disabled = !state.tab;
}

function showBanner(message, action) {
  els.banner.replaceChildren(document.createTextNode(message));
  if (action) {
    const btn = document.createElement("button");
    btn.textContent = action.label;
    // Call synchronously so chrome.permissions.request still sees the user gesture.
    btn.addEventListener("click", () => {
      try {
        const result = action.run();
        if (result && typeof result.catch === "function") result.catch((e) => console.error(e));
      } catch (e) {
        console.error(e);
      }
    });
    els.banner.appendChild(btn);
  }
  els.banner.hidden = false;
}

function hideBanner() {
  els.banner.hidden = true;
}

let toastTimer;
function toast(text) {
  els.toast.textContent = text;
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (els.toast.hidden = true), 1800);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard");
  } catch {
    toast("Couldn't copy");
  }
}

function autosize() {
  els.question.style.height = "auto";
  els.question.style.height = Math.min(els.question.scrollHeight, 140) + "px";
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
function toggleSettings(force) {
  const show = force ?? els.settingsPanel.hidden;
  els.settingsPanel.hidden = !show;
  els.settingsStatus.textContent = "";
  if (show) els.backendUrl.focus();
}

function readBackendInput() {
  const value = els.backendUrl.value.trim().replace(/\/+$/, "");
  try {
    const u = new URL(value);
    if (!/^https?:$/.test(u.protocol)) throw new Error();
    return value;
  } catch {
    els.settingsStatus.textContent = "Enter a valid http(s) URL.";
    return null;
  }
}

$("testBtn").addEventListener("click", async () => {
  const url = readBackendInput();
  if (!url) return;
  els.settingsStatus.textContent = "Testing...";
  try {
    const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(8000) });
    const body = await res.json();
    els.settingsStatus.textContent = res.ok
      ? `Connected. Provider: ${body.provider}${body.fallback ? ` (fallback: ${body.fallback})` : ""}`
      : `Backend responded with ${res.status}.`;
  } catch {
    els.settingsStatus.textContent = "Could not connect. Is the backend running and is CORS configured?";
  }
});

$("saveSettingsBtn").addEventListener("click", async () => {
  const url = readBackendInput();
  if (!url) return;
  state.backendUrl = url;
  await chrome.storage.sync.set({ backendUrl: url });
  els.settingsStatus.textContent = "Saved.";
  setTimeout(() => toggleSettings(false), 600);
});

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------
$("settingsBtn").addEventListener("click", () => toggleSettings());
$("newChatBtn").addEventListener("click", () => {
  if (!state.tab || state.streaming) return;
  state.chats.set(state.tab.id, { url: state.tab.url, messages: [] });
  saveChat(state.tab.id);
  hideBanner();
  renderChat();
  els.question.focus();
});

els.send.addEventListener("click", () => send({ question: els.question.value, task: els.taskType.value }));
els.stop.addEventListener("click", () => state.streaming?.controller.abort());
els.question.addEventListener("input", autosize);
els.question.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    send({ question: els.question.value, task: els.taskType.value });
  }
});
document.querySelectorAll(".chip").forEach((chip) =>
  chip.addEventListener("click", () => send({ question: els.question.value.trim(), task: chip.dataset.task })),
);

(async function init() {
  const win = await chrome.windows.getCurrent();
  state.windowId = win.id;
  await loadSettings();
  await refreshActiveTab();
  els.question.focus();
})();
