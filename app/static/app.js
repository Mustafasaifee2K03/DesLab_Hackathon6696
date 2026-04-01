const state = {
  currentUserId: "demo_user",
  recommendations: [],
};

const domains = ["videos", "music", "podcasts", "movies", "news"];

function $(id) {
  return document.getElementById(id);
}

function csvToList(value) {
  return value
    .split(",")
    .map((v) => v.trim().toLowerCase())
    .filter(Boolean);
}

function selectedLanguages() {
  return Array.from(document.querySelectorAll("#languages input[type='checkbox']:checked")).map(
    (opt) => opt.value
  );
}

function renderMeta(meta) {
  const container = $("metaStats");
  container.innerHTML = "";
  const stats = [
    `Content records: ${meta.content_count}`,
    `Domains: ${meta.domains.join(", ")}`,
    `Feedback actions: ${meta.actions.join(", ")}`,
    `Agent: ${meta.agent_framework || "standard"}`,
  ];

  for (const text of stats) {
    const span = document.createElement("span");
    span.className = "pill";
    span.textContent = text;
    container.appendChild(span);
  }
}

async function saveAndLoad() {
  await upsertProfile();
  await loadRecommendations();
}

function createDomainSliders() {
  const wrapper = $("weightSliders");
  wrapper.innerHTML = "";

  const defaults = {
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
    input.value = String(defaults[domain]);
    input.name = `weight_${domain}`;

    const output = document.createElement("output");
    output.textContent = `${defaults[domain]}%`;

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
  const entries = domains.map((domain) => {
    const input = document.querySelector(`input[name='weight_${domain}']`);
    return [domain, Number(input.value || 0)];
  });
  return Object.fromEntries(entries);
}

async function upsertProfile() {
  const userId = $("userId").value.trim();
  state.currentUserId = userId;

  const payload = {
    name: $("name").value.trim(),
    interests: csvToList($("interests").value),
    moods: csvToList($("moods").value),
    languages: selectedLanguages(),
    domain_weights: readDomainWeights(),
  };

  const resp = await fetch(`/api/users/${encodeURIComponent(userId)}/profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || "Failed to save profile");
  }

  const data = await resp.json();
  $("profileStatus").textContent = "Profile saved successfully. Recommendations are updated below.";
}

function cardActionButton(action, contentId) {
  return async (evt) => {
    evt.preventDefault();
    const resp = await fetch(`/api/users/${encodeURIComponent(state.currentUserId)}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content_id: contentId, action }),
    });

    if (!resp.ok) {
      const err = await resp.json();
      alert(err.detail || "Unable to submit feedback");
      return;
    }

    await loadRecommendations();
  };
}

function renderCards(items) {
  const root = $("cards");
  root.innerHTML = "";

  if (!items.length) {
    root.innerHTML = "<p>No recommendations found with the current combination of filters.</p>";
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
      btn.addEventListener("click", cardActionButton(action, item.id));
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

async function loadFeedbackSummary() {
  const resp = await fetch(`/api/users/${encodeURIComponent(state.currentUserId)}/feedback`);
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

async function loadRecommendations() {
  const domain = $("filterDomain").value;
  const maxDuration = Number($("maxDuration").value || 180);
  const resultLimit = Number($("resultLimit").value || 25);

  const params = new URLSearchParams();
  params.set("limit", String(resultLimit));
  params.set("max_duration", String(maxDuration));
  if (domain) params.set("domain", domain);

  const resp = await fetch(
    `/api/users/${encodeURIComponent(state.currentUserId)}/recommendations?${params.toString()}`
  );

  if (!resp.ok) {
    const err = await resp.json();
    $("feedMessage").textContent = "";
    $("cards").innerHTML = `<p>${err.detail || "No recommendations"}</p>`;
    return;
  }

  const data = await resp.json();
  state.recommendations = data.items || [];

  const selectedLangs = (data.diagnostics?.selected_languages || []).join(", ") || "any";
  const availableLangs = (data.diagnostics?.available_languages || []).join(", ") || "unknown";
  if (data.message) {
    const plan = data.diagnostics?.agent_planning_note || "";
    $("feedMessage").textContent = `${data.message} Selected: ${selectedLangs}. Available: ${availableLangs}. ${plan}`.trim();
  } else {
    const liveAdded = data.diagnostics?.live_items_added || 0;
    const liveText = liveAdded > 0 ? `Agent synced ${liveAdded} live items before ranking.` : "";
    $("feedMessage").textContent = liveText;
  }

  renderCards(state.recommendations);
  await loadFeedbackSummary();
}

async function init() {
  createDomainSliders();

  const metaResp = await fetch("/api/meta");
  const meta = await metaResp.json();
  renderMeta(meta);

  $("profileForm").addEventListener("submit", async (evt) => {
    evt.preventDefault();
    try {
      await saveAndLoad();
    } catch (err) {
      $("profileStatus").textContent = err.message;
    }
  });

  $("refreshBtn").addEventListener("click", async () => {
    try {
      await saveAndLoad();
    } catch (err) {
      $("feedMessage").textContent = err.message;
    }
  });

  await saveAndLoad();
}

init().catch((err) => {
  console.error(err);
  $("cards").innerHTML = `<p>Initialization failed: ${err.message}</p>`;
});
