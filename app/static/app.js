const DRAFT_KEY = "unisphere_profile_draft_v2";
const domains = ["videos", "music", "podcasts", "movies", "news"];

function $(id) {
  return document.getElementById(id);
}

function getPage() {
  return document.body.dataset.page || "";
}

function parseQuery() {
  const params = new URLSearchParams(window.location.search);
  return Object.fromEntries(params.entries());
}

function saveDraft(draft) {
  localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
}

function loadDraft() {
  try {
    return JSON.parse(localStorage.getItem(DRAFT_KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function selectedLanguages() {
  return Array.from(document.querySelectorAll("#languages input[type='checkbox']:checked")).map(
    (opt) => opt.value
  );
}

function createDomainSliders(defaults = null) {
  const wrapper = $("weightSliders");
  if (!wrapper) return;

  wrapper.innerHTML = "";
  const baseline = defaults || {
    videos: 20,
    music: 20,
    podcasts: 20,
    movies: 20,
    news: 20,
  };

  for (const domain of domains) {
    const cell = document.createElement("div");
    cell.className = "slider-wrap";

    const label = document.createElement("label");
    label.textContent = domain;

    const input = document.createElement("input");
    input.type = "range";
    input.min = "0";
    input.max = "100";
    input.step = "1";
    input.value = String(baseline[domain] ?? 20);
    input.name = `weight_${domain}`;

    const output = document.createElement("output");
    output.textContent = `${input.value}%`;

    input.addEventListener("input", () => {
      output.textContent = `${input.value}%`;
    });

    cell.appendChild(label);
    cell.appendChild(input);
    cell.appendChild(output);
    wrapper.appendChild(cell);
  }
}

function readDomainWeights() {
  return Object.fromEntries(
    domains.map((domain) => {
      const input = document.querySelector(`input[name='weight_${domain}']`);
      return [domain, Number(input?.value || 0)];
    })
  );
}

function renderMeta(meta) {
  const container = $("metaStats");
  if (!container) return;

  container.innerHTML = "";
  const stats = [
    `Content records: ${meta.content_count}`,
    `Domains: ${meta.domains.join(", ")}`,
    `Agent: ${meta.agent_framework || "standard"}`,
  ];

  for (const text of stats) {
    const span = document.createElement("span");
    span.className = "pill";
    span.textContent = text;
    container.appendChild(span);
  }
}

async function upsertProfile(payload) {
  const userId = payload.user_id;
  const resp = await fetch(`/api/users/${encodeURIComponent(userId)}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: payload.name,
      interests: payload.interests,
      demand_text: payload.demand_text,
      languages: payload.languages,
      domain_weights: payload.domain_weights,
    }),
  });

  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || "Failed to save profile");
  }

  return resp.json();
}

async function loadFeedbackSummary(userId) {
  const resp = await fetch(`/api/users/${encodeURIComponent(userId)}/feedback`);
  if (!resp.ok) {
    $("feedbackSummary").textContent = "";
    return;
  }
  const data = await resp.json();
  const summary = data.summary || {};
  const chunks = ["like", "save", "dislike", "hide", "view"].map(
    (key) => `${key}: ${summary[key] || 0}`
  );
  $("feedbackSummary").textContent = `Feedback stats -> ${chunks.join(" | ")}`;
}

function cardActionButton(userId, action, contentId, reloadFn) {
  return async (evt) => {
    evt.preventDefault();
    const resp = await fetch(`/api/users/${encodeURIComponent(userId)}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content_id: contentId, action }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      alert(err.detail || "Unable to submit feedback");
      return;
    }

    await reloadFn();
  };
}

function renderCards(userId, items, reloadFn) {
  const root = $("cards");
  root.innerHTML = "";

  if (!items.length) {
    root.innerHTML = "<p>No relevant recommendations found. Try refining interests or demand text.</p>";
    return;
  }

  const tpl = $("cardTemplate");
  for (const item of items) {
    const node = tpl.content.firstElementChild.cloneNode(true);

    node.querySelector(".badge").textContent = item.domain;
    node.querySelector(".score").textContent = `score ${item.score.toFixed(3)}`;
    node.querySelector(".title").textContent = item.title;
    node.querySelector(".desc").textContent = item.description;
    node.querySelector(".reason").textContent = item.reason;
    node.querySelector(".meta").textContent = `${item.source} | ${item.creator} | ${item.duration_minutes} min | ${item.language.toUpperCase()}`;

    const tagsWrap = node.querySelector(".tag-list");
    for (const tag of item.tags.slice(0, 5)) {
      const chip = document.createElement("span");
      chip.textContent = tag;
      tagsWrap.appendChild(chip);
    }

    const openLink = node.querySelector(".open-link");
    openLink.href = item.url;

    for (const btn of node.querySelectorAll("button[data-action]")) {
      const action = btn.dataset.action;
      btn.addEventListener("click", cardActionButton(userId, action, item.id, reloadFn));
    }

    if (item.saved) {
      const saved = document.createElement("span");
      saved.className = "pill";
      saved.textContent = "Saved";
      node.querySelector(".card-top").appendChild(saved);
    }

    root.appendChild(node);
  }
}

async function initOnboardingPage() {
  const form = $("onboardingForm");
  form.addEventListener("submit", (evt) => {
    evt.preventDefault();

    const userId = $("userId").value.trim();
    const name = $("name").value.trim();
    const interests = Array.from(
      document.querySelectorAll("#interestOptions input[name='interests']:checked")
    ).map((it) => it.value.toLowerCase());
    const demandText = $("demandText").value.trim();

    if (interests.length < 1) {
      $("onboardingStatus").textContent = "Select at least one interest to continue.";
      return;
    }

    if (demandText.length < 12) {
      $("onboardingStatus").textContent = "Please provide a more specific demand description.";
      return;
    }

    saveDraft({
      user_id: userId,
      name,
      interests,
      demand_text: demandText,
      languages: ["en"],
      domain_weights: { videos: 20, music: 20, podcasts: 20, movies: 20, news: 20 },
    });

    window.location.href = `/preferences?user_id=${encodeURIComponent(userId)}`;
  });
}

async function initPreferencesPage() {
  const draft = loadDraft();
  if (!draft.user_id) {
    window.location.href = "/";
    return;
  }

  $("profileSummary").textContent = `User ${draft.name} • Interests: ${draft.interests.join(", ")} • Demand: ${draft.demand_text}`;

  createDomainSliders(draft.domain_weights);

  if (Array.isArray(draft.languages)) {
    for (const lang of draft.languages) {
      const checkbox = document.querySelector(`#languages input[value='${lang}']`);
      if (checkbox) checkbox.checked = true;
    }
  }

  $("preferencesForm").addEventListener("submit", async (evt) => {
    evt.preventDefault();
    try {
      const payload = {
        ...draft,
        languages: selectedLanguages(),
        domain_weights: readDomainWeights(),
      };
      saveDraft(payload);
      await upsertProfile(payload);
      $("preferencesStatus").textContent = "Profile saved. Preparing your dynamic recommendations...";
      window.location.href = `/feed?user_id=${encodeURIComponent(payload.user_id)}`;
    } catch (err) {
      $("preferencesStatus").textContent = err.message;
    }
  });
}

async function initFeedPage() {
  const query = parseQuery();
  const draft = loadDraft();
  const userId = (query.user_id || draft.user_id || "").trim();
  if (!userId) {
    window.location.href = "/";
    return;
  }

  if (draft.name) {
    $("feedSubtitle").textContent = `Showing dynamic results for ${draft.name}. Demand focus: ${draft.demand_text || "custom"}.`;
  }

  async function loadRecommendations() {
    const domain = $("filterDomain").value;
    const maxDuration = Number($("maxDuration").value || 180);
    const resultLimit = Number($("resultLimit").value || 25);

    const params = new URLSearchParams();
    params.set("limit", String(resultLimit));
    params.set("max_duration", String(maxDuration));
    if (domain) params.set("domain", domain);

    const resp = await fetch(
      `/api/users/${encodeURIComponent(userId)}/recommendations?${params.toString()}`
    );

    if (!resp.ok) {
      const err = await resp.json();
      $("feedMessage").textContent = "";
      $("cards").innerHTML = `<p>${err.detail || "Unable to fetch recommendations"}</p>`;
      return;
    }

    const data = await resp.json();
    const selectedLangs = (data.diagnostics?.selected_languages || []).join(", ") || "any";
    const availableLangs = (data.diagnostics?.available_languages || []).join(", ") || "unknown";

    if (data.message) {
      $("feedMessage").textContent = `${data.message} Selected: ${selectedLangs}. Available: ${availableLangs}.`;
    } else {
      const plan = data.diagnostics?.agent_planning_note || "";
      const liveAdded = data.diagnostics?.live_items_added || 0;
      const extra = liveAdded > 0 ? ` Agent synced ${liveAdded} fresh items.` : "";
      $("feedMessage").textContent = `${plan}${extra}`.trim();
    }

    renderCards(userId, data.items || [], loadRecommendations);
    await loadFeedbackSummary(userId);
  }

  $("refreshBtn").addEventListener("click", loadRecommendations);

  const metaResp = await fetch("/api/meta");
  const meta = await metaResp.json();
  renderMeta(meta);

  await loadRecommendations();
}

async function init() {
  const page = getPage();
  if (page === "onboarding") {
    await initOnboardingPage();
  } else if (page === "preferences") {
    await initPreferencesPage();
  } else if (page === "feed") {
    await initFeedPage();
  }
}

init().catch((err) => {
  console.error(err);
  const status = $("onboardingStatus") || $("preferencesStatus") || $("feedMessage");
  if (status) status.textContent = `Initialization failed: ${err.message}`;
});
