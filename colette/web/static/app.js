// Colette web GUI — vanilla ES module, no build step.

const main = document.getElementById("main");
const tabsEl = document.getElementById("tabs");
const toastEl = document.getElementById("toast");

// ---------------------------------------------------------------- helpers
function esc(s) {
  return String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }[c]),
  );
}

let toastTimer = null;
function toast(message, isError = false) {
  toastEl.textContent = message;
  toastEl.classList.toggle("error", isError);
  toastEl.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(
    () => toastEl.classList.remove("show"),
    isError ? 5000 : 2500,
  );
}

async function api(path, { method = "GET", body, timeoutMs } = {}) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  let timer;
  if (timeoutMs) {
    const ctrl = new AbortController();
    opts.signal = ctrl.signal;
    timer = setTimeout(() => ctrl.abort(), timeoutMs);
  }
  try {
    const res = await fetch(path, opts);
    const text = await res.text();
    const data = text ? JSON.parse(text) : null;
    if (!res.ok) {
      throw new Error((data && data.error) || `Request failed (${res.status})`);
    }
    return data;
  } catch (e) {
    if (e.name === "AbortError") {
      throw new Error(
        "Request timed out — the server is still working; reload to check.",
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

function loading() {
  main.innerHTML =
    `<div class="empty"><span class="spinner"></span> Loading…</div>`;
}

// ---------------------------------------------------------------- routing
// Views are driven by the URL hash (#/people, #/round/57, …) so the browser
// back/forward buttons work and views are linkable.
const views = {};

function setActiveTab(view) {
  for (const tab of tabsEl.querySelectorAll(".tab")) {
    tab.classList.toggle("active", tab.dataset.view === view);
  }
}

// Navigate (adds a history entry). Re-rendering happens via the hashchange.
function setView(name) {
  location.hash = "#/" + name;
}
function gotoRound(n) {
  location.hash = "#/round/" + n;
}

function handleRoute() {
  const [seg, arg] = location.hash.replace(/^#\/?/, "").split("/");
  if (seg === "people") {
    setActiveTab("people");
    views.people();
  } else if (seg === "rounds") {
    setActiveTab("rounds");
    views.rounds();
  } else if (seg === "round" && arg) {
    setActiveTab("rounds");
    showRound(Number(arg));
  } else if (seg === "email") {
    setActiveTab("email");
    views.email();
  } else if (seg === "history") {
    setActiveTab("history");
    views.history();
  } else {
    setActiveTab("overview");
    views.overview();
  }
}

globalThis.addEventListener("hashchange", handleRoute);

tabsEl.addEventListener("click", (e) => {
  const tab = e.target.closest(".tab");
  if (tab) setView(tab.dataset.view);
});

async function refreshPath() {
  try {
    const s = await api("/api/status");
    document.getElementById("path-display").textContent = s.path;
  } catch {
    /* ignore */
  }
}

// ================================================================ OVERVIEW
views.overview = async function () {
  loading();
  let s, rounds;
  try {
    [s, rounds] = await Promise.all([api("/api/status"), api("/api/rounds")]);
  } catch (e) {
    main.innerHTML = `<div class="card"><p class="muted">${
      esc(e.message)
    }</p></div>`;
    return;
  }

  const solved = rounds.filter((r) => r.has_solution);
  const last = solved.length ? solved[solved.length - 1] : null;

  let actionCard;
  if (s.rounds_solved === 0) {
    // brand-new / not-yet-running directory → guided setup
    actionCard = renderGettingStarted(s, rounds);
  } else {
    let nextState;
    const actions = [];
    if (!s.next_config_exists) {
      nextState = `Round ${s.next_round} hasn't been created yet.`;
      actions.push(
        `<button class="btn primary" data-act="create-round">Create round ${s.next_round}</button>`,
      );
    } else {
      nextState =
        `Round ${s.next_round} is set up, but pairings haven't been generated.`;
      actions.push(
        `<button class="btn primary" data-act="generate">Generate pairings</button>`,
        `<button class="btn" data-act="open-next">Edit round ${s.next_round}</button>`,
      );
    }
    actionCard = `<div class="card">
      <h3>Next steps</h3>
      <p class="muted" style="margin-top:0">${nextState}</p>
      ${actions.length ? `<div class="row">${actions.join("")}</div>` : ""}
      ${
      !s.has_templates
        ? `<p class="small muted" style="margin-top:.7rem">No email templates found — email preview is disabled. Set them up on the Email tab.</p>`
        : ""
    }
    </div>`;
  }

  const recent = rounds
    .slice()
    .reverse()
    .slice(0, 6)
    .map((r) => {
      const badge = r.has_solution
        ? `<span class="badge ok">${r.num_pairs} pairs</span>`
        : r.has_config
        ? `<span class="badge warn">not generated</span>`
        : `<span class="badge muted">—</span>`;
      return `<tr data-round="${r.number}" class="clickable">
        <td>Round ${r.number}</td>
        <td class="muted small">${r.date ? esc(r.date) : ""}</td>
        <td>${badge}</td></tr>`;
    })
    .join("");

  main.innerHTML = `
    <div class="card">
      <h2>Overview</h2>
      <div class="metrics">
        <div class="metric"><div class="label">Active people</div><div class="value">${s.people_active}</div></div>
        <div class="metric"><div class="label">Total people</div><div class="value">${s.people_total}</div></div>
        <div class="metric"><div class="label">Rounds run</div><div class="value">${s.rounds_solved}</div></div>
        <div class="metric"><div class="label">Next round</div><div class="value">${s.next_round}</div></div>
      </div>
    </div>
    ${actionCard}
    ${
    last
      ? `<div class="card">
      <div class="row spread">
        <h3 style="margin:0">Latest round</h3>
        <button class="btn small" data-act="open-last">Open round ${last.number}</button>
      </div>
      <p class="muted" style="margin-bottom:0">Round ${last.number}${
        last.date ? ` · ${esc(last.date)}` : ""
      } · ${last.num_pairs} pairs${
        last.num_removed ? ` · ${last.num_removed} sitting out` : ""
      }</p>
    </div>`
      : ""
  }
    ${
    recent
      ? `<div class="card">
      <h3>Recent rounds</h3>
      <table class="grid"><tbody>${recent}</tbody></table>
    </div>`
      : ""
  }`;

  main.querySelector('[data-act="goto-people"]')?.addEventListener(
    "click",
    () => setView("people"),
  );
  main.querySelector('[data-act="goto-email"]')?.addEventListener(
    "click",
    () => setView("email"),
  );
  main.querySelector('[data-act="create-round"]')?.addEventListener(
    "click",
    async (ev) => {
      await withBusy(ev.target, async () => {
        const r = await api("/api/rounds", { method: "POST", body: {} });
        toast(`Created round ${r.number}`);
        gotoRound(r.number);
      });
    },
  );
  main.querySelector('[data-act="generate"]')?.addEventListener(
    "click",
    async (ev) => {
      await withSolve(ev.target, "Generating pairings…", async () => {
        const sol = await api("/api/rounds/solve", {
          method: "POST",
          body: {},
          timeoutMs: SOLVE_TIMEOUT_MS,
        });
        toast(
          `Generated ${sol.pairs.length} pairs for round ${sol.round}${
            solvedNote(sol)
          }`,
        );
        gotoRound(sol.round);
      });
    },
  );
  main.querySelector('[data-act="open-next"]')?.addEventListener(
    "click",
    () => gotoRound(s.next_round),
  );
  main.querySelector('[data-act="open-last"]')?.addEventListener(
    "click",
    () => gotoRound(s.last_round),
  );
  main.querySelectorAll("tr.clickable").forEach((tr) =>
    tr.addEventListener("click", () => gotoRound(Number(tr.dataset.round)))
  );
};

async function withBusy(btn, fn) {
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>`;
  try {
    await fn();
  } catch (e) {
    toast(e.message, true);
    btn.disabled = false;
    btn.innerHTML = old;
  }
}

// Client-side backstop for a normal solve (server caps it at ~30s); the
// "try for longer" action raises both this and the server budget.
const SOLVE_TIMEOUT_MS = 60000;
// Only surface a progress message once a solve has run this long, so quick
// solves (the common case) stay silent.
const SOLVE_NOTICE_MS = 500;
// After this long, tell the user it's a genuinely hard round.
const SOLVE_HARD_MS = 10000;
// Note appended to a success toast when the solver hit its time limit. The
// optimal flag is persisted with the solution, so it survives reloads.
function solvedNote(sol) {
  return sol && sol.optimal === false
    ? " — time-limited, may not be optimal"
    : "";
}

const statusEl = document.getElementById("status");
function showStatus(message) {
  statusEl.innerHTML = `<span class="spinner"></span> ${esc(message)}`;
  statusEl.classList.add("show");
}
function hideStatus() {
  statusEl.classList.remove("show");
}

let busy = false;
async function withSolve(btn, message, fn) {
  if (busy) return; // a solve is already in flight — ignore double-clicks
  busy = true;
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span>`;
  // Stay silent for quick solves; show a message only if it's slow, and
  // escalate the wording if it's genuinely taking a while.
  const noticeTimer = setTimeout(() => showStatus(message), SOLVE_NOTICE_MS);
  const hardTimer = setTimeout(
    () => showStatus("Still working — this is a hard round to solve…"),
    SOLVE_HARD_MS,
  );
  try {
    await fn();
  } catch (e) {
    toast(e.message, true);
    btn.disabled = false;
    btn.innerHTML = old;
  } finally {
    clearTimeout(noticeTimer);
    clearTimeout(hardTimer);
    hideStatus();
    busy = false;
  }
}

// Guided checklist shown on the Overview until the first round is generated.
function renderGettingStarted(s, rounds) {
  const peopleDone = s.people_total >= 2;
  const templatesDone = s.has_templates;
  const roundDone = rounds.length > 0;
  const pairedDone = s.rounds_solved > 0;

  const step = (done, label, extra = "") =>
    `<div class="step"><span class="step-mark ${done ? "done" : ""}">${
      done ? "✓" : "○"
    }</span><span>${label}${extra}</span></div>`;

  let cta = "";
  if (!peopleDone) {
    cta =
      '<button class="btn primary" data-act="goto-people">Add people</button>';
  } else if (!roundDone) {
    cta =
      `<button class="btn primary" data-act="create-round">Create round ${s.next_round}</button>`;
  } else if (!pairedDone) {
    cta =
      '<button class="btn primary" data-act="generate">Generate pairings</button>';
  }
  const tplBtn = templatesDone
    ? ""
    : '<button class="btn" data-act="goto-email">Set up email templates</button>';

  return `<div class="card">
    <h3>Getting started</h3>
    <p class="muted" style="margin-top:0">Set up this working directory in a few steps:</p>
    <div class="steps">
      ${
    step(
      peopleDone,
      "Add at least two participants",
      s.people_total
        ? ` <span class="muted small">(${s.people_total} so far)</span>`
        : "",
    )
  }
      ${
    step(
      templatesDone,
      "Add email templates",
      ' <span class="muted small">(optional)</span>',
    )
  }
      ${step(roundDone, "Create the first round")}
      ${step(pairedDone, "Generate pairings")}
    </div>
    <div class="row" style="margin-top:.8rem">${cta}${tplBtn}</div>
  </div>`;
}

// ================================================================ PEOPLE
views.people = async function () {
  loading();
  let people;
  try {
    people = await api("/api/people");
  } catch (e) {
    // A missing people.csv is fine (handled as empty); this only fires for a
    // people.csv that exists but can't be parsed.
    main.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p>
      <p class="small muted">Fix or remove people.csv in the working directory, then reload.</p></div>`;
    return;
  }

  const rows = people
    .map(
      (p) => `
      <tr data-name="${esc(p.name)}" class="${p.active ? "" : "inactive"}">
        <td class="cell-name">${esc(p.name)}</td>
        <td class="cell-org">${
        esc(p.organisation) || '<span class="muted">—</span>'
      }</td>
        <td class="cell-email">${
        esc(p.email) || '<span class="muted">—</span>'
      }</td>
        <td class="cell-active"><input type="checkbox" class="toggle-active" ${
        p.active ? "checked" : ""
      } aria-label="active"></td>
        <td style="text-align:right;white-space:nowrap">
          <button class="btn-icon edit" title="Edit">&#9998;</button>
          <button class="btn-icon danger del" title="Delete">&#128465;</button>
        </td>
      </tr>`,
    )
    .join("");

  main.innerHTML = `
    <div class="card">
      <h2>People <span class="muted small">(${people.length})</span></h2>
      <table class="grid" id="people-table">
        <thead><tr><th>Name</th><th>Organisation</th><th>Email</th><th>Active</th><th></th></tr></thead>
        <tbody>${rows || ""}</tbody>
      </table>
      ${
    people.length
      ? ""
      : '<p class="empty">No people yet — add your first participant below.</p>'
  }
    </div>
    <div class="card">
      <h3>Add a person</h3>
      <div class="row">
        <input id="new-name" placeholder="Name" style="flex:1;min-width:140px">
        <input id="new-org" placeholder="Organisation" style="flex:1;min-width:140px">
        <input id="new-email" placeholder="Email" style="flex:1;min-width:160px">
        <label class="row small" style="gap:.3rem"><input type="checkbox" id="new-active" checked> active</label>
        <button class="btn primary" id="add-person">Add</button>
      </div>
      <details style="margin-top:1rem">
        <summary>Import several at once</summary>
        <p class="small muted" style="margin:.5rem 0">One per line as <code>name, organisation, email</code> (organisation and email optional). Existing names are skipped — nothing is overwritten.</p>
        <textarea id="bulk-text" rows="6" style="width:100%;font-family:var(--mono)" placeholder="Alice Smith, Engineering, alice@example.com
Bob Jones, Sales
Charlie Day"></textarea>
        <div class="row" style="margin-top:.5rem"><button class="btn primary" id="bulk-add">Import</button></div>
      </details>
    </div>`;

  document.getElementById("add-person").addEventListener(
    "click",
    async (ev) => {
      const name = document.getElementById("new-name").value.trim();
      if (!name) {
        toast("Name is required", true);
        return;
      }
      await withBusy(ev.target, async () => {
        await api("/api/people", {
          method: "POST",
          body: {
            name,
            organisation: document.getElementById("new-org").value,
            email: document.getElementById("new-email").value,
            active: document.getElementById("new-active").checked,
          },
        });
        toast(`Added ${name}`);
        views.people();
      });
    },
  );

  document.getElementById("bulk-add").addEventListener("click", async (ev) => {
    const text = document.getElementById("bulk-text").value;
    if (!text.trim()) {
      toast("Paste at least one person", true);
      return;
    }
    await withBusy(ev.target, async () => {
      const res = await api("/api/people/import", {
        method: "POST",
        body: { text },
      });
      const parts = [`Added ${res.added}`];
      if (res.skipped) parts.push(`skipped ${res.skipped} existing`);
      if (res.errors.length) parts.push(`${res.errors.length} errors`);
      toast(parts.join(", "));
      views.people();
    });
  });

  const tbody = document.querySelector("#people-table tbody");
  tbody?.addEventListener("change", async (e) => {
    if (!e.target.classList.contains("toggle-active")) return;
    const tr = e.target.closest("tr");
    const name = tr.dataset.name;
    try {
      await api(`/api/people/${encodeURIComponent(name)}`, {
        method: "PUT",
        body: { active: e.target.checked },
      });
      tr.classList.toggle("inactive", !e.target.checked);
      toast(`${name} ${e.target.checked ? "activated" : "deactivated"}`);
    } catch (err) {
      toast(err.message, true);
      e.target.checked = !e.target.checked;
    }
  });

  tbody?.addEventListener("click", async (e) => {
    const tr = e.target.closest("tr");
    if (!tr) return;
    const name = tr.dataset.name;
    if (e.target.classList.contains("del")) {
      if (
        !confirm(
          `Delete ${name}? (Only possible if they've never been paired.)`,
        )
      ) return;
      try {
        await api(`/api/people/${encodeURIComponent(name)}`, {
          method: "DELETE",
        });
        toast(`Deleted ${name}`);
        views.people();
      } catch (err) {
        toast(err.message, true);
      }
    } else if (e.target.classList.contains("edit")) {
      const person = people.find((p) => p.name === name);
      if (person) openEditPerson(person);
    }
  });
};

// Edit a person in a modal dialog so the table never reflows (no jumpy rows).
function openEditPerson(person) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true" aria-label="Edit person">
      <h3>Edit person</h3>
      <label class="field"><span>Name</span><input id="m-name" value="${
    esc(person.name)
  }"></label>
      <label class="field"><span>Organisation</span><input id="m-org" value="${
    esc(person.organisation)
  }"></label>
      <label class="field"><span>Email</span><input id="m-email" value="${
    esc(person.email)
  }"></label>
      <label class="row small" style="gap:.4rem;margin:.6rem 0 1rem"><input type="checkbox" id="m-active" ${
    person.active ? "checked" : ""
  }> active</label>
      <div class="row spread">
        <button class="btn" id="m-cancel">Cancel</button>
        <button class="btn primary" id="m-save">Save</button>
      </div>
    </div>`;
  document.body.appendChild(backdrop);

  const onKey = (e) => {
    if (e.key === "Escape") close();
  };
  function close() {
    document.removeEventListener("keydown", onKey);
    globalThis.removeEventListener("hashchange", close);
    backdrop.remove();
  }
  document.addEventListener("keydown", onKey);
  // dismiss the modal if the user navigates away (e.g. browser back/forward)
  globalThis.addEventListener("hashchange", close);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) close();
  });
  backdrop.querySelector("#m-cancel").addEventListener("click", close);
  backdrop.querySelector("#m-name").focus();

  backdrop.querySelector("#m-save").addEventListener("click", async (ev) => {
    const btn = ev.target;
    const old = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>`;
    try {
      const body = {
        name: backdrop.querySelector("#m-name").value.trim(),
        organisation: backdrop.querySelector("#m-org").value,
        email: backdrop.querySelector("#m-email").value,
        active: backdrop.querySelector("#m-active").checked,
      };
      await api(`/api/people/${encodeURIComponent(person.name)}`, {
        method: "PUT",
        body,
      });
      toast(`Updated ${body.name}`);
      close();
      views.people();
    } catch (err) {
      toast(err.message, true);
      btn.disabled = false;
      btn.innerHTML = old;
    }
  });
}

// ================================================================ ROUNDS
views.rounds = async function () {
  loading();
  let rounds, status;
  try {
    [rounds, status] = await Promise.all([
      api("/api/rounds"),
      api("/api/status"),
    ]);
  } catch (e) {
    main.innerHTML = `<div class="card"><p class="muted">${
      esc(e.message)
    }</p></div>`;
    return;
  }

  const cells = rounds
    .slice()
    .reverse()
    .map((r) => {
      const badges = [];
      if (r.has_solution) {
        badges.push(`<span class="badge ok">${r.num_pairs} pairs</span>`);
      } else if (r.has_config) {
        badges.push(`<span class="badge warn">not generated</span>`);
      }
      if (r.num_removed) {
        badges.push(`<span class="badge muted">${r.num_removed} out</span>`);
      }
      if (!r.has_config) {
        badges.push(`<span class="badge muted">no config</span>`);
      }
      return `
        <div class="round-cell" data-round="${r.number}">
          <div class="num">Round ${r.number}</div>
          <div class="date">${r.date ? esc(r.date) : "&nbsp;"}</div>
          <div class="badges">${badges.join("")}</div>
        </div>`;
    })
    .join("");

  let createBtn;
  if (status.people_total === 0) {
    createBtn =
      '<span class="muted small">Add people first (People tab).</span>';
  } else if (status.next_config_exists) {
    createBtn =
      `<button class="btn" data-act="open-next">Set up round ${status.next_round}</button>`;
  } else {
    createBtn =
      `<button class="btn primary" data-act="create-round">Create round ${status.next_round}</button>`;
  }

  main.innerHTML = `
    <div class="card">
      <div class="row spread">
        <h2 style="margin:0">Rounds</h2>
        <div class="row">${createBtn}</div>
      </div>
    </div>
    <div class="card">
      ${
    cells
      ? `<div class="round-list">${cells}</div>`
      : '<p class="empty">No rounds yet.</p>'
  }
    </div>`;

  main.querySelector('[data-act="create-round"]')?.addEventListener(
    "click",
    async (ev) => {
      await withBusy(ev.target, async () => {
        const r = await api("/api/rounds", { method: "POST", body: {} });
        toast(`Created round ${r.number}`);
        gotoRound(r.number);
      });
    },
  );
  main.querySelector('[data-act="open-next"]')?.addEventListener(
    "click",
    () => gotoRound(status.next_round),
  );
  main.querySelectorAll(".round-cell").forEach((c) =>
    c.addEventListener("click", () => gotoRound(Number(c.dataset.round)))
  );
};

// editable config state for the round detail view
let edit = null;
// whether the config editor has unsaved changes (drives the save button)
let editDirty = false;
// how much weight a "discourage" click adds to a pairing override
const DISCOURAGE_STEP = 1000;
// residual cost left on a "may sit out" person so the solver still prefers to
// pair them when it can, but picks them first when someone has to sit out.
// Matches the historical convention (e.g. cost_of_not_pairing 1000 → -900).
const SIT_OUT_RESIDUAL = 100;
// round to auto-preview when the Email tab is opened from a round page
let emailPreviewRound = null;

// Build the JSON config body the API expects from the in-memory edit state.
function currentCfgBody() {
  return {
    date: edit.date,
    notes: edit.notes,
    removes: edit.removes,
    overrides: edit.overrides,
    costs: edit.costs,
  };
}

async function showRound(n, { silent = false } = {}) {
  setActiveTab("rounds");
  const scrollPos = window.scrollY;
  if (!silent) loading();

  let data, people, status;
  try {
    [data, people, status] = await Promise.all([
      api(`/api/rounds/${n}`),
      api("/api/people"),
      api("/api/status"),
    ]);
  } catch (e) {
    main.innerHTML = `<div class="card"><p class="muted">${esc(e.message)}</p>
      <button class="btn" id="back">Back to rounds</button></div>`;
    document.getElementById("back").addEventListener(
      "click",
      () => setView("rounds"),
    );
    return;
  }

  const allNames = people.map((p) => p.name);
  const isNextUnsolved = n === status.next_round && !data.solution;
  const isLatestSolved = !!data.solution && n === status.last_round;

  edit = data.config
    ? {
      date: data.config.date || "",
      notes: data.config.notes || "",
      removes: data.config.removes.map((r) => ({ ...r })),
      overrides: data.config.overrides.map((o) => ({
        pair: [...o.pair],
        weight: o.weight,
      })),
      costs: { ...data.config.costs },
    }
    : null;
  editDirty = false; // fresh load → no unsaved changes

  const generateBtn = isNextUnsolved
    ? `<button class="btn primary" id="solve">Generate pairings</button>`
    : "";

  main.innerHTML = `
    <div class="card">
      <div class="row spread">
        <h2 style="margin:0">Round ${n}</h2>
        <button class="btn small" id="back">All rounds</button>
      </div>
    </div>
    <div id="config-area"></div>
    <div class="card">
      <div class="row spread">
        <h3 style="margin:0">Pairings</h3>
        <div class="row">${generateBtn}
          ${
    data.solution && data.config
      ? `<button class="btn" id="emails">Preview emails</button>`
      : ""
  }
        </div>
      </div>
      <div id="solution-area">${
    renderSolution(data.solution, { canDiscourage: isLatestSolved })
  }</div>
    </div>`;

  if (silent) globalThis.scrollTo(0, scrollPos);

  document.getElementById("back").addEventListener(
    "click",
    () => setView("rounds"),
  );
  renderConfigEditor(n, allNames, { isLatestSolved });

  document.getElementById("solve")?.addEventListener("click", async (ev) => {
    await withSolve(ev.target, "Generating pairings…", async () => {
      const sol = await api("/api/rounds/solve", {
        method: "POST",
        body: {},
        timeoutMs: SOLVE_TIMEOUT_MS,
      });
      toast(`Generated ${sol.pairs.length} pairs${solvedNote(sol)}`);
      showRound(sol.round, { silent: true });
    });
  });

  const refreshSolution = (sol) => {
    document.getElementById("solution-area").innerHTML = renderSolution(sol, {
      canDiscourage: true,
    });
  };

  document.getElementById("solution-area")?.addEventListener(
    "click",
    async (e) => {
      // "Try for longer" → re-solve the same round with a bigger time budget.
      const longBtn = e.target.closest("[data-try-longer]");
      if (longBtn && !busy) {
        await withSolve(
          longBtn,
          "Trying for longer — this can take a couple of minutes…",
          async () => {
            const sol = await api("/api/rounds/solve", {
              method: "POST",
              body: { regenerate: true, max_seconds: 120 },
              timeoutMs: 130000,
            });
            refreshSolution(sol);
            toast(
              sol.optimal === false
                ? `Still time-limited (${sol.pairs.length} pairs) — the round is genuinely hard`
                : `Found an optimal pairing (${sol.pairs.length} pairs)`,
            );
          },
        );
        return;
      }

      // discourage a specific pairing → add/raise an override, save, regenerate.
      // Updates the pairings and config in place so the page doesn't jump.
      const btn = e.target.closest("[data-discourage]");
      if (!btn || !edit || busy) return;
      const a = btn.dataset.a;
      const b = btn.dataset.b;
      await withSolve(btn, "Regenerating…", async () => {
        const existing = edit.overrides.find(
          (o) =>
            o.pair[0] !== o.pair[1] &&
            ((o.pair[0] === a && o.pair[1] === b) ||
              (o.pair[0] === b && o.pair[1] === a)),
        );
        if (existing) existing.weight += DISCOURAGE_STEP;
        else edit.overrides.push({ pair: [a, b], weight: DISCOURAGE_STEP });
        await api(`/api/rounds/${n}/config`, {
          method: "PUT",
          body: currentCfgBody(),
        });
        const sol = await api("/api/rounds/solve", {
          method: "POST",
          body: { regenerate: true },
          timeoutMs: SOLVE_TIMEOUT_MS,
        });
        refreshSolution(sol);
        renderConfigEditor(n, allNames, { isLatestSolved });
        toast(`Pushed ${a} and ${b} apart${solvedNote(sol)}`);
      });
    },
  );

  document.getElementById("emails")?.addEventListener("click", () => {
    emailPreviewRound = n;
    setView("email");
  });
}

function renderSolution(sol, { canDiscourage = false } = {}) {
  if (!sol) return `<p class="muted small">Not generated yet.</p>`;
  if (!sol.pairs.length && !sol.removed.length) {
    return `<p class="muted small">No pairs.</p>`;
  }
  const hasCaviats = sol.pairs.some((p) => p.caviats.length);
  const legendParts = ["Shown as primary &harr; secondary."];
  if (canDiscourage) {
    legendParts.push("Use &times; to push a pair apart and try again.");
  }
  if (hasCaviats) {
    legendParts.push(
      "A note under a pairing explains why it wasn't an ideal match.",
    );
  }
  const legend = `<p class="small muted" style="margin:.2rem 0 .6rem">${
    legendParts.join(" ")
  }</p>`;
  const pairs = sol.pairs
    .map(
      (p) => `
      <div class="pair">
        <span class="who-block"><span class="who">${
        esc(p.primary.name)
      }</span> <span class="org">${esc(p.primary.organisation)}</span></span>
        <span class="arrow">&harr;</span>
        <span class="who-block"><span class="who">${
        esc(p.secondary.name)
      }</span> <span class="org">${esc(p.secondary.organisation)}</span></span>
        ${
        canDiscourage
          ? `<button class="btn-icon discourage" data-discourage data-a="${
            esc(p.primary.name)
          }" data-b="${
            esc(p.secondary.name)
          }" title="Discourage this pairing and try again">&times;</button>`
          : ""
      }
        ${
        p.caviats.length
          ? `<span class="caviats">Not an ideal match: ${
            esc(p.caviats.join(", "))
          }</span>`
          : ""
      }
      </div>`,
    )
    .join("");
  const removed = sol.removed.length
    ? `<p class="small muted" style="margin-top:.6rem">Sitting out this round: ${
      sol.removed
        .map(esc)
        .join(", ")
    }</p>`
    : "";
  const cost = sol.cost && sol.cost > 0
    ? `<p class="small muted">Solution cost: ${sol.cost}</p>`
    : "";
  const note = sol.optimal === false
    ? `<div class="solve-note">
        <p>We had trouble solving this round — we found a good pairing, but it may not be the <em>best</em> one.</p>
        <div class="row">
          ${
      canDiscourage
        ? `<button class="btn small" data-try-longer>Try for longer</button>`
        : ""
    }
          <span class="muted small">Solving again as-is gives the same pairing — to get a different one, adjust the configuration above (remove someone, let someone sit out, or nudge a pair) and save.</span>
        </div>
      </div>`
    : "";
  return legend + pairs + removed + cost + note;
}

// size sandboxed email iframes to their content height
function sizeIframes(area) {
  area.querySelectorAll("iframe").forEach((f) => {
    f.addEventListener("load", () => {
      try {
        f.style.height = f.contentWindow.document.body.scrollHeight + 24 + "px";
      } catch {
        /* ignore */
      }
    });
  });
}

function emailCard(m) {
  const to = m.to.map((r) => `${esc(r.name)} &lt;${esc(r.email)}&gt;`).join(
    ", ",
  );
  return `
    <div class="email">
      <div class="head">
        <div class="subject">${esc(m.subject)}</div>
        <div class="muted">To: ${to}</div>
      </div>
      <iframe sandbox="allow-same-origin" srcdoc="${esc(m.body)}"></iframe>
    </div>`;
}

function renderEmails(messages, area) {
  if (!messages.length) {
    area.innerHTML = `<p class="muted small">No emails to preview.</p>`;
    return;
  }
  area.innerHTML =
    `<p class="small muted">${messages.length} message${
      messages.length === 1 ? "" : "s"
    }.</p>` + messages.map(emailCard).join("");
  sizeIframes(area);
}

// ---- config editor ----
function renderConfigEditor(n, allNames, { isLatestSolved = false } = {}) {
  const area = document.getElementById("config-area");
  if (!edit) {
    area.innerHTML =
      `<div class="card"><p class="muted">No configuration for this round.</p></div>`;
    return;
  }

  const known = new Set(allNames);
  // index overrides so chip "remove" buttons stay correct after splitting
  const sitOuts = [];
  const overrides = [];
  edit.overrides.forEach((o, i) => {
    if (o.pair[0] === o.pair[1]) sitOuts.push({ ...o, i });
    else overrides.push({ ...o, i });
  });

  const datalist = `<datalist id="all-people">${
    allNames
      .map((nm) => `<option value="${esc(nm)}"></option>`)
      .join("")
  }</datalist>`;

  const removeChips = edit.removes
    .map(
      (r, i) => `
      <span class="chip">${esc(r.name)}${
        r.until ? ` <span class="muted">until ${esc(r.until)}</span>` : ""
      }<button data-remove-idx="${i}" title="Remove">&times;</button></span>`,
    )
    .join("");

  const sitOutChips = sitOuts
    .map(
      (o) => `
      <span class="chip">${
        esc(o.pair[0])
      } <span class="muted">may sit out</span>
      <button data-override-idx="${o.i}" title="Remove">&times;</button></span>`,
    )
    .join("");

  const overrideChips = overrides
    .map(
      (o) => `
      <span class="chip">${esc(o.pair[0])} + ${esc(o.pair[1])}
      <span class="muted">${
        o.weight > 0 ? "avoid" : "prefer"
      } (${o.weight})</span>
      <button data-override-idx="${o.i}" title="Remove">&times;</button></span>`,
    )
    .join("");

  const costRows = Object.entries(edit.costs)
    .map(
      ([k, v]) => `
      <label class="field" style="margin-bottom:.5rem">
        <span>${esc(k.replace(/_/g, " "))}</span>
        <input type="number" data-cost="${esc(k)}" value="${v}">
      </label>`,
    )
    .join("");

  const saveLabel = isLatestSolved ? "Save &amp; regenerate" : "Save config";

  area.innerHTML = `
    <div class="card">
      ${datalist}
      <h3 style="margin:0 0 .2rem">Configuration</h3>
      <div class="row" style="margin-top:.6rem;align-items:flex-end">
        <label class="field"><span>Date</span><input type="date" id="cfg-date" value="${
    esc(edit.date)
  }"></label>
        <label class="field" style="flex:1;min-width:200px"><span>Notes</span><input id="cfg-notes" value="${
    esc(edit.notes)
  }"></label>
      </div>

      <div class="config-section">
        <h4>Removed from this round <span class="muted small">(won't be paired at all)</span></h4>
        <div class="chips">${
    removeChips || '<span class="muted small">Nobody removed.</span>'
  }</div>
        <div class="row config-add">
          <input list="all-people" id="rm-name" placeholder="search a person…" style="min-width:180px">
          <select id="rm-until-type">
            <option value="">until further notice</option>
            <option value="date">until a date…</option>
            <option value="round">until a round #…</option>
          </select>
          <input type="date" id="rm-until-date" style="display:none">
          <input type="number" id="rm-until-round" min="1" placeholder="round #" style="display:none;width:110px">
          <button class="btn small" id="rm-add">Remove person</button>
        </div>
      </div>

      <div class="config-section">
        <h4>Allow to sit out <span class="muted small">(stay in the pool, but OK to leave unpaired — handy for odd groups)</span></h4>
        <div class="chips">${
    sitOutChips || '<span class="muted small">Nobody flagged to sit out.</span>'
  }</div>
        <div class="row config-add">
          <input list="all-people" id="sit-name" placeholder="search a person…" style="min-width:180px">
          <button class="btn small" id="sit-add">Allow to sit out</button>
        </div>
      </div>

      <div class="config-section">
        <h4>Overrides <span class="muted small">(nudge a specific pairing together or apart)</span></h4>
        <div class="chips">${
    overrideChips || '<span class="muted small">No overrides.</span>'
  }</div>
        <div class="row config-add">
          <input list="all-people" id="ov-a" placeholder="first person…" style="min-width:150px">
          <input list="all-people" id="ov-b" placeholder="second person…" style="min-width:150px">
          <select id="ov-dir"><option value="avoid">keep apart</option><option value="prefer">pair up</option></select>
          <button class="btn small" id="ov-add">Add override</button>
        </div>
      </div>

      <details style="margin-top:1rem">
        <summary>Advanced: costs</summary>
        <div style="margin-top:.6rem;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.3rem 1rem">${costRows}</div>
      </details>

      <div class="config-footer">
        <span class="dirty-hint"${
    editDirty ? "" : " hidden"
  }>Unsaved changes</span>
        <button class="btn primary" id="save-config"${
    editDirty ? "" : " disabled"
  }>${saveLabel}</button>
      </div>
    </div>`;

  const rerender = () => renderConfigEditor(n, allNames, { isLatestSolved });
  const markDirty = () => {
    editDirty = true;
    const btn = area.querySelector("#save-config");
    if (btn) btn.disabled = false;
    const hint = area.querySelector(".dirty-hint");
    if (hint) hint.hidden = false;
  };

  area.querySelector("#cfg-date").addEventListener("change", (e) => {
    edit.date = e.target.value;
    markDirty();
  });
  area.querySelector("#cfg-notes").addEventListener("input", (e) => {
    edit.notes = e.target.value;
    markDirty();
  });
  area.querySelectorAll("[data-cost]").forEach((inp) =>
    inp.addEventListener("change", (e) => {
      edit.costs[e.target.dataset.cost] = parseInt(e.target.value, 10) || 0;
      markDirty();
    })
  );

  const untilType = area.querySelector("#rm-until-type");
  untilType.addEventListener("change", () => {
    area.querySelector("#rm-until-date").style.display =
      untilType.value === "date" ? "" : "none";
    area.querySelector("#rm-until-round").style.display =
      untilType.value === "round" ? "" : "none";
  });

  area.querySelector("#rm-add").addEventListener("click", () => {
    const name = area.querySelector("#rm-name").value.trim();
    if (!known.has(name)) {
      toast("Pick a person from the list", true);
      return;
    }
    if (edit.removes.some((r) => r.name === name)) {
      toast(`${name} already removed`, true);
      return;
    }
    let until = null;
    if (untilType.value === "date") {
      until = area.querySelector("#rm-until-date").value;
      if (!until) {
        toast("Pick a date", true);
        return;
      }
    } else if (untilType.value === "round") {
      const rv = area.querySelector("#rm-until-round").value;
      if (!rv) {
        toast("Enter a round number", true);
        return;
      }
      until = parseInt(rv, 10);
    }
    edit.removes.push({ name, until });
    editDirty = true;
    rerender();
  });

  area.querySelector("#sit-add").addEventListener("click", () => {
    const name = area.querySelector("#sit-name").value.trim();
    if (!known.has(name)) {
      toast("Pick a person from the list", true);
      return;
    }
    if (edit.overrides.some((o) => o.pair[0] === name && o.pair[1] === name)) {
      toast(`${name} can already sit out`, true);
      return;
    }
    // model "sit out" as a self-pairing override that offsets the cost of
    // leaving them unpaired, leaving a small residual so they're only left
    // out when someone has to be (matches the historical -900/1000 convention).
    const cnp = parseInt(edit.costs.cost_of_not_pairing, 10) || 50;
    const weight = cnp > SIT_OUT_RESIDUAL ? SIT_OUT_RESIDUAL - cnp : -cnp;
    edit.overrides.push({ pair: [name, name], weight });
    editDirty = true;
    rerender();
  });

  area.querySelector("#ov-add").addEventListener("click", () => {
    const a = area.querySelector("#ov-a").value.trim();
    const b = area.querySelector("#ov-b").value.trim();
    if (!known.has(a) || !known.has(b)) {
      toast("Pick both people from the list", true);
      return;
    }
    if (a === b) {
      toast("Same person — use ‘Allow to sit out’ instead", true);
      return;
    }
    const dir = area.querySelector("#ov-dir").value;
    edit.overrides.push({
      pair: [a, b],
      weight: dir === "avoid" ? 1000 : -1000,
    });
    editDirty = true;
    rerender();
  });

  area.querySelectorAll("[data-remove-idx]").forEach((b) =>
    b.addEventListener("click", () => {
      edit.removes.splice(Number(b.dataset.removeIdx), 1);
      editDirty = true;
      rerender();
    })
  );
  area.querySelectorAll("[data-override-idx]").forEach((b) =>
    b.addEventListener("click", () => {
      edit.overrides.splice(Number(b.dataset.overrideIdx), 1);
      editDirty = true;
      rerender();
    })
  );

  area.querySelector("#save-config").addEventListener("click", async (ev) => {
    if (!editDirty || busy) return;
    const message = isLatestSolved ? "Saving & regenerating…" : "Saving…";
    await withSolve(ev.target, message, async () => {
      await api(`/api/rounds/${n}/config`, {
        method: "PUT",
        body: currentCfgBody(),
      });
      if (isLatestSolved) {
        const sol = await api("/api/rounds/solve", {
          method: "POST",
          body: { regenerate: true },
          timeoutMs: SOLVE_TIMEOUT_MS,
        });
        toast(
          `Saved & regenerated (${sol.pairs.length} pairs)${solvedNote(sol)}`,
        );
      } else {
        toast("Configuration saved");
      }
      showRound(n, { silent: true });
    });
  });
}

// ================================================================ HISTORY
views.history = async function () {
  loading();
  let h;
  try {
    h = await api("/api/history");
  } catch (e) {
    main.innerHTML = `<div class="card"><p class="muted">${
      esc(e.message)
    }</p></div>`;
    return;
  }

  const rd = h.round_dates || {};
  const fmtRounds = (rounds) =>
    rounds
      .map((
        n,
      ) => (rd[n] ? `${n} <span class="muted">(${esc(rd[n])})</span>` : `${n}`))
      .join(", ");

  const repeatRows = h.repeats
    .slice(0, 100)
    .map(
      (r) => `
      <tr>
        <td>${esc(r.pair[0])} &amp; ${esc(r.pair[1])}</td>
        <td>${r.count}</td>
        <td class="small">${fmtRounds(r.rounds)}</td>
      </tr>`,
    )
    .join("");

  const personOptions = h.people
    .map((p) => `<option value="${esc(p)}">${esc(p)}</option>`)
    .join("");

  main.innerHTML = `
    <div class="card">
      <h2>History <span class="muted small">(${h.rounds_count} rounds)</span></h2>
    </div>
    <div class="card">
      <h3>Partner lookup</h3>
      <div class="row">
        <select id="person-select"><option value="">— choose a person —</option>${personOptions}</select>
      </div>
      <div id="partner-result"></div>
    </div>
    <div class="card">
      <h3>Repeated pairings <span class="muted small">(paired more than once)</span></h3>
      ${
    repeatRows
      ? `<table class="grid"><thead><tr><th>Pair</th><th>Times</th><th>Rounds</th></tr></thead><tbody>${repeatRows}</tbody></table>`
      : '<p class="muted small">No repeated pairings yet — nice spread!</p>'
  }
    </div>`;

  const sel = document.getElementById("person-select");
  const result = document.getElementById("partner-result");
  sel.addEventListener("change", () => {
    const name = sel.value;
    if (!name) {
      result.innerHTML = "";
      return;
    }
    const list = h.partners[name] || [];
    if (!list.length) {
      result.innerHTML = `<p class="muted small" style="margin-top:.6rem">${
        esc(name)
      } hasn't been paired yet.</p>`;
      return;
    }
    result.innerHTML =
      `<table class="grid" style="margin-top:.6rem"><thead><tr><th>Partner</th><th>Times</th><th>Rounds</th></tr></thead><tbody>` +
      list
        .map(
          (p) =>
            `<tr><td>${
              esc(p.partner)
            }</td><td>${p.count}</td><td class="small">${
              fmtRounds(p.rounds)
            }</td></tr>`,
        )
        .join("") +
      `</tbody></table>`;
  });
};

// ================================================================ EMAIL
const STARTER_SUBJECT =
  "Coffee Roulette ({{ round_config.date.strftime('%b %Y') }})";
const STARTER_BODY = `<html>
  <body>
    <p>Hi {{ primary.name.split()[0] }} and {{ secondary.name.split()[0] }},</p>
    <p>You've been paired for a coffee catch-up this round. Find a time that
       suits you both and enjoy!</p>
    <p>Cheers,<br>The Coffee Robot</p>
  </body>
</html>
`;

views.email = async function () {
  loading();
  let tpl, rounds;
  try {
    [tpl, rounds] = await Promise.all([
      api("/api/templates"),
      api("/api/rounds"),
    ]);
  } catch (e) {
    main.innerHTML = `<div class="card"><p class="muted">${
      esc(e.message)
    }</p></div>`;
    return;
  }

  // only rounds with a config can be rendered (templates need round_config.*)
  const solved = rounds
    .filter((r) => r.has_solution && r.has_config)
    .map((r) => r.number);
  const selected = emailPreviewRound && solved.includes(emailPreviewRound)
    ? emailPreviewRound
    : (solved.length ? solved[solved.length - 1] : "");
  const roundOptions = solved
    .slice()
    .reverse()
    .map((n) =>
      `<option value="${n}" ${
        n === selected ? "selected" : ""
      }>Round ${n}</option>`
    )
    .join("");

  // Default to the starter template when a file doesn't exist yet, so a new
  // directory shows a usable email straight away.
  const initialSubject = tpl.has_subject ? tpl.subject : STARTER_SUBJECT;
  const initialBody = tpl.has_body ? tpl.body : STARTER_BODY;

  main.innerHTML = `
    <div class="card">
      <h2 style="margin:0 0 .3rem">Email templates</h2>
      <p class="small muted">Jinja2 templates shared by every round. Variables you can use:
        <code>primary</code> and <code>secondary</code> (each with <code>.name</code>,
        <code>.email</code>, <code>.organisation</code>), <code>round_config</code>
        (e.g. <code>round_config.date</code>) and <code>caviats</code>.</p>
      <div class="tpl-grid">
        <div class="editor-col">
          <label class="field" style="margin-bottom:.7rem"><span>Subject (subject.txt)</span>
            <input id="tpl-subject" value="${esc(initialSubject)}"></label>
          <label class="field"><span>Body (body.html)</span>
            <textarea id="tpl-body" rows="18" style="font-family:var(--mono);width:100%;resize:vertical">${
    esc(initialBody)
  }</textarea></label>
        </div>
        <div class="preview-col">
          <h4>Preview <span class="muted small">(example participants, live)</span></h4>
          <div id="live-error" class="dirty-hint" style="color:var(--danger)" hidden></div>
          <div id="live-preview"></div>
        </div>
      </div>
      <div class="config-footer">
        <button class="btn primary small" id="save-tpl">Save templates</button>
      </div>
      ${
    solved.length
      ? `<details style="margin-top:1rem">
        <summary>Preview a generated round's real emails (uses saved templates)</summary>
        <div class="row" style="margin:.6rem 0">
          <select id="prev-round">${roundOptions}</select>
          <button class="btn" id="prev-btn">Preview round</button>
        </div>
        <div id="email-area"></div>
      </details>`
      : ""
  }
      <p class="small muted" style="margin-top:1rem">Preview only — Colette never sends mail from the web GUI. Use <code>colette email</code> to send.</p>
    </div>`;

  const subjectEl = document.getElementById("tpl-subject");
  const bodyEl = document.getElementById("tpl-body");
  const liveEl = document.getElementById("live-preview");
  const liveErr = document.getElementById("live-error");

  // Build the preview card once and update its parts in place, so the iframe
  // isn't recreated on every keystroke (which caused a white flash).
  function buildLiveCard() {
    liveEl.innerHTML = `
      <div class="email">
        <div class="head">
          <div class="subject"></div>
          <div class="muted live-to"></div>
        </div>
        <iframe sandbox="allow-same-origin"></iframe>
      </div>`;
    const f = liveEl.querySelector("iframe");
    f.addEventListener("load", () => {
      try {
        f.style.height = f.contentWindow.document.body.scrollHeight + 24 + "px";
      } catch {
        /* ignore */
      }
    });
  }

  let lastBody = null;
  let liveTimer = null;
  async function refreshLivePreview() {
    let res;
    try {
      res = await api("/api/templates/preview", {
        method: "POST",
        body: { subject: subjectEl.value, body: bodyEl.value },
      });
    } catch (e) {
      liveErr.hidden = false;
      liveErr.textContent = e.message;
      return;
    }
    if (res.error) {
      liveErr.hidden = false;
      liveErr.textContent = "Template error: " + res.error;
      return; // keep the last good preview on screen
    }
    liveErr.hidden = true;
    if (!liveEl.querySelector(".email")) buildLiveCard();
    liveEl.querySelector(".subject").textContent = res.subject;
    liveEl.querySelector(".live-to").textContent = "To: " +
      res.to.map((r) => `${r.name} <${r.email}>`).join(", ");
    if (res.body !== lastBody) {
      const f = liveEl.querySelector("iframe");
      if (f.offsetHeight) f.style.height = f.offsetHeight + "px"; // avoid collapse
      f.srcdoc = res.body;
      lastBody = res.body;
    }
  }
  const scheduleLive = () => {
    clearTimeout(liveTimer);
    liveTimer = setTimeout(refreshLivePreview, 250);
  };
  subjectEl.addEventListener("input", scheduleLive);
  bodyEl.addEventListener("input", scheduleLive);
  refreshLivePreview();

  document.getElementById("save-tpl").addEventListener("click", async (ev) => {
    const btn = ev.target;
    const old = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>`;
    try {
      await api("/api/templates", {
        method: "PUT",
        body: { subject: subjectEl.value, body: bodyEl.value },
      });
      toast("Templates saved");
    } catch (e) {
      toast(e.message, true);
    } finally {
      btn.disabled = false;
      btn.innerHTML = old;
    }
  });

  const previewBtn = document.getElementById("prev-btn");
  const doPreview = async (btn) => {
    const n = Number(document.getElementById("prev-round").value);
    const old = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>`;
    try {
      const res = await api(`/api/rounds/${n}/emails`);
      renderEmails(res.messages, document.getElementById("email-area"));
    } catch (e) {
      toast(e.message, true);
    } finally {
      btn.disabled = false;
      btn.innerHTML = old;
    }
  };
  previewBtn?.addEventListener("click", () => doPreview(previewBtn));

  // expand + auto-preview when arriving from a round's "Preview emails" button
  if (emailPreviewRound && solved.includes(emailPreviewRound) && previewBtn) {
    previewBtn.closest("details").open = true;
    doPreview(previewBtn);
  }
  emailPreviewRound = null;
};

// ---------------------------------------------------------------- boot
refreshPath();
handleRoute();
