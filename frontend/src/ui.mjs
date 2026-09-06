// Shared presentation only. Real intake and authored demo state never cross this seam.
export const $ = (selector) => document.querySelector(selector);
export const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const paths = {
  plus: "M12 5v14M5 12h14",
  chat: "M4 4h16v12H8l-4 4V4Z",
  arrow: "M7 17 17 7M7 7h10v10",
  send: "M12 19V5m-6 6 6-6 6 6",
  back: "M19 12H5m6-6-6 6 6 6",
  chevron: "m9 5 7 7-7 7",
  down: "m6 9 6 6 6-6",
  panel: "M3 4h18v16H3V4Zm5 0v16",
  close: "m6 6 12 12M6 18 18 6",
  pipeline:
    "M5 4v16M5 5h5m-5 7h5m-5 7h5M13 3h7v4h-7V3Zm0 7h7v4h-7v-4Zm0 7h7v4h-7v-4Z",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2",
  file: "M14 3H5v18h14V8l-5-5ZM14 3v5h5M8 12h8M8 16h6",
  code: "m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18",
  activity: "M2 12h5l3-8 4 16 3-8h5",
  check: "m5 12 4 4L19 6",
  circle: "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  refresh:
    "M3 10a9 9 0 0 1 16-5l2 2M21 3v4h-4M21 14a9 9 0 0 1-16 5l-2-2M3 21v-4h4",
  history: "M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2",
  play: "m8 4 12 8-12 8V4Z",
  box: "m12 3 9 5v9l-9 5-9-5V8l9-5Zm0 10v9M3 8l9 5 9-5",
  info: "M12 11v6M12 7h.01M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
  link: "m10 13 4-4M8 15l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M16 9l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0",
};
export const icon = (name) =>
  `<svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="${paths[name] || paths.file}"/></svg>`;
export const badge = (status, label = status) =>
  `<span class="badge ${escape(status)}"><i></i>${escape(label.replaceAll("-", " "))}</span>`;
export const empty = (title, description, glyph = "chat") =>
  `<div class="empty-state">${icon(glyph)}<h2>${escape(title)}</h2><p>${escape(description)}</p></div>`;
export const welcome = () =>
  `<div class="welcome"><h1>EPOCH</h1><p>Describe the result you want.</p></div>`;
export function urlFor(demo, page, task = "", hash = "") {
  return `${demo ? "/demo" : ""}/${page}${task ? `?task=${encodeURIComponent(task)}` : ""}${hash ? `#${encodeURIComponent(hash)}` : ""}`;
}
export function currentPage() {
  return location.pathname.endsWith("/debugger") ? "debugger" : "chat";
}
export function routeLink(demo, page, task, label, glyph = "", extra = "") {
  return `<a href="${urlFor(demo, page, task)}" data-route ${extra}>${glyph ? icon(glyph) : ""}${label}</a>`;
}
export function shell({
  demo = false,
  page,
  task = "",
  title = "New chat",
  nav,
  bottom = "",
  content,
  composer = "",
  status = "",
  actions = "",
  locked = false,
}) {
  return `<aside class="sidebar" id="sidebar" aria-label="Workspace navigation"><div class="sidebar-brand"><a href="${urlFor(demo, "chat")}" data-route aria-label="Epoch chat"><span class="brand-mark">E</span><span>epoch</span></a><button class="icon-button mobile-close" data-action="close-nav" aria-label="Close navigation">${icon("close")}</button></div>
    <nav class="primary-nav"><button class="nav-item" data-action="new" ${locked ? "disabled" : ""}>${icon("plus")}<span>New chat</span><kbd>⌘ N</kbd></button>${routeLink(demo, "debugger", task, "Debugger", "pipeline", `class="nav-item ${page === "debugger" ? "selected" : ""}" ${page === "debugger" ? 'aria-current="page"' : ""}`)}</nav>
    <div class="session-heading"><span>${demo ? "DEMO SESSION" : "CHATS"}</span>${!demo ? `<button class="icon-button" id="refresh-list" data-action="refresh-list" aria-label="Refresh list">${icon("refresh")}</button>` : ""}</div><div class="session-list">${nav}</div>
    <div class="sidebar-bottom">${bottom}<a class="nav-item mode-link" href="${demo ? "/chat" : "/demo/chat"}">${icon(demo ? "chat" : "play")}<span>${demo ? "Back to real workspace" : "Explore release demo"}</span>${icon("arrow")}</a><div class="sidebar-footnote">${demo ? "Authored example · session only" : "Your local workspace"}</div></div></aside>
    <button class="nav-scrim" data-action="close-nav" aria-label="Close navigation"></button>
    <div class="shell"><header class="topbar"><div class="topbar-left"><button class="icon-button" data-action="toggle-nav" aria-label="Toggle navigation" aria-controls="sidebar" aria-expanded="false">${icon("panel")}</button>${page === "debugger" ? routeLink(demo, "chat", task, "Back to chat", "back", 'class="back-link"') : `<span class="header-title">${escape(title)}</span>`}</div><div class="topbar-actions">${demo ? '<span class="demo-label">Demo · authored data</span>' : ""}${status}${actions}</div></header>
    ${demo ? '<div class="demo-strip">All progress, repairs, tests and artifacts are authored examples. No task is executing.</div>' : ""}
    <main id="workspace" tabindex="-1" class="workspace ${page === "debugger" ? "debug-workspace" : "chat-workspace"}"><div id="page-scroll" class="page-scroll">${content}</div>${composer}</main>
    <footer class="statusbar"><span>${demo ? "Local demo" : "Local workspace"}<span class="footer-dot">·</span>${demo ? "No tools or tests execute" : "Intake only · execution unavailable"}</span><span>epoch <span class="footer-dot">/</span> ${page}</span></footer></div>`;
}

// Restore native input selection, disclosures, and independent page scroll positions.
// No rendering on input: the controllers retain drafts while the DOM owns typing.
export class View {
  constructor(root) {
    this.root = root;
    this.key = "";
    this.positions = new Map();
    this.disclosures = new Map();
    root.addEventListener(
      "toggle",
      (e) => {
        if (e.target.matches("details[data-key]"))
          this.disclosures.set(
            `${this.key}:${e.target.dataset.key}`,
            e.target.open,
          );
      },
      true,
    );
  }
  render(html, key, { focus, bottom = false } = {}) {
    const active = document.activeElement;
    const savedFocus = active?.id;
    const summaryKey = active?.matches("summary")
      ? active.parentElement.dataset.key
      : null;
    const selection =
      typeof active?.selectionStart === "number"
        ? [active.selectionStart, active.selectionEnd]
        : null;
    const oldScroll = $("#page-scroll");
    if (oldScroll && this.key)
      this.positions.set(this.key, oldScroll.scrollTop);
    const railScroll = $(".session-list")?.scrollTop || 0;
    this.root.innerHTML = html;
    this.key = key;
    this.root.querySelectorAll("details[data-key]").forEach((el) => {
      const stored = this.disclosures.get(`${key}:${el.dataset.key}`);
      if (stored !== undefined) el.open = stored;
    });
    const scroll = $("#page-scroll");
    if (scroll)
      scroll.scrollTop = bottom
        ? scroll.scrollHeight
        : this.positions.get(key) || 0;
    if ($(".session-list")) $(".session-list").scrollTop = railScroll;
    const field =
      document.getElementById(focus || savedFocus) ||
      (!focus && summaryKey
        ? this.root.querySelector(
            `details[data-key="${CSS.escape(summaryKey)}"]>summary`,
          )
        : null);
    field?.focus({ preventScroll: true });
    if (!focus && selection && field?.setSelectionRange)
      field.setSelectionRange(...selection);
    this.root.querySelectorAll("textarea[data-autogrow]").forEach(grow);
    document.title = `Epoch · ${currentPage() === "debugger" ? "Debugger" : "Chat"}`;
    syncNav();
  }
}
export function grow(el) {
  el.style.height = "auto";
  el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
}
function syncNav() {
  const open = document.body.classList.contains("nav-open");
  const mobile = matchMedia("(max-width: 760px)").matches;
  if ($("#sidebar")) $("#sidebar").inert = mobile && !open;
  $(".shell")?.toggleAttribute("inert", mobile && open);
  $('[data-action="toggle-nav"]')?.setAttribute("aria-expanded", String(open));
}
export function closeNav() {
  document.body.classList.remove("nav-open");
  syncNav();
}
export function installNavigation(root, onRoute, onNew) {
  // A skip link moves keyboard focus without scrolling the fixed app shell.
  $(".skip-link")?.addEventListener("click", (event) => {
    event.preventDefault();
    $("#workspace")?.focus({ preventScroll: true });
  });
  const navigate = (href) => {
    history.pushState(null, "", href);
    closeNav();
    onRoute({ fromLink: true });
  };
  root.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-route]");
    if (
      link &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.shiftKey &&
      event.button === 0
    ) {
      event.preventDefault();
      navigate(link.href);
    }
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "toggle-nav") {
      document.body.classList.toggle("nav-open");
      syncNav();
      if (document.body.classList.contains("nav-open"))
        $(".mobile-close")?.focus();
    }
    if (action === "close-nav") {
      closeNav();
      $('[data-action="toggle-nav"]')?.focus();
    }
  });
  window.addEventListener("popstate", () => {
    closeNav();
    onRoute();
  });
  matchMedia("(max-width: 760px)").addEventListener("change", syncNav);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && document.body.classList.contains("nav-open")) {
      closeNav();
      $('[data-action="toggle-nav"]')?.focus();
    }
    if (
      (e.metaKey || e.ctrlKey) &&
      !e.shiftKey &&
      e.key.toLowerCase() === "n"
    ) {
      e.preventDefault();
      onNew();
    }
    if (
      e.key === "Tab" &&
      document.body.classList.contains("nav-open") &&
      matchMedia("(max-width: 760px)").matches
    ) {
      const items = [
        ...$("#sidebar").querySelectorAll("a,button:not(:disabled)"),
      ].filter((el) => el.getClientRects().length);
      if (e.shiftKey && document.activeElement === items[0]) {
        e.preventDefault();
        items.at(-1)?.focus();
      } else if (!e.shiftKey && document.activeElement === items.at(-1)) {
        e.preventDefault();
        items[0]?.focus();
      }
    }
    if (
      e.key === "Enter" &&
      !e.shiftKey &&
      !e.isComposing &&
      e.target.matches("textarea[data-submit]")
    ) {
      e.preventDefault();
      e.target.form?.requestSubmit();
    }
  });
  root.addEventListener("input", (e) => {
    if (e.target.matches("textarea[data-autogrow]")) grow(e.target);
  });
  // Safari's visual viewport tracks the keyboard independently of layout viewport.
  const resize = () =>
    document.documentElement.style.setProperty(
      "--viewport-height",
      `${window.visualViewport?.height || window.innerHeight}px`,
    );
  window.visualViewport?.addEventListener("resize", resize);
  resize();
  return navigate;
}
export function installInspector() {
  const dialog = $("#inspector");
  let data;
  let trigger;
  $("#close-inspector").onclick = () => dialog.close();
  dialog.addEventListener(
    "close",
    () => trigger?.isConnected && trigger.focus({ preventScroll: true }),
  );
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      const rect = dialog.getBoundingClientRect();
      if (
        event.clientX < rect.left ||
        event.clientX > rect.right ||
        event.clientY < rect.top ||
        event.clientY > rect.bottom
      )
        dialog.close();
    }
  });
  $("#download-artifact").onclick = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "epoch-evidence.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (title, value, demo = false) => {
    trigger = document.activeElement;
    data = demo
      ? { label: "AUTHORED UI FIXTURE — NOT EXECUTION EVIDENCE", data: value }
      : { label: "PHASE 1 INTAKE RECORD — NO EXECUTION", data: value };
    $("#inspector-title").textContent = title;
    $("#inspector-label").textContent = data.label;
    $("#inspector-content").textContent = JSON.stringify(value, null, 2);
    $("#download-artifact").textContent = demo
      ? "Download fixture JSON"
      : "Download record JSON";
    dialog.showModal();
    $("#close-inspector").focus();
  };
}
export const stageNames = [
  "Failure",
  "Diagnosis",
  "Candidate change",
  "Verification",
  "Publish",
  "Resume task",
];
export function pipeline(stages) {
  return `<ol class="pipeline">${stages.map((s, i) => `<li class="pipeline-stage ${escape(s.tone || "")}" id="stage-${i}"><span class="stage-number">${String(i + 1).padStart(2, "0")}</span><details data-key="stage-${i}" ${s.open ? "open" : ""}><summary><span class="stage-heading"><span class="stage-name">${stageNames[i]}</span>${badge(s.tone || "pending", s.status)}${icon("down")}</span><span class="stage-summary">${escape(s.summary)}</span></summary>${s.body ? `<div class="stage-body">${s.body}</div>` : ""}</details></li>`).join("")}</ol>`;
}
