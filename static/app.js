/* app.js
 * All communication with the backend happens through fetch() calls to the
 * Flask API in app.py. No page reloads -- the dashboard re-renders itself
 * whenever data changes (new resident registered, feedback logged, weight
 * slider moved).
 */

const CATEGORY_COLORS = {
  "Fitness & Movement": "var(--cat-fitness)",
  "Arts & Crafts": "var(--cat-arts)",
  "Social & Games": "var(--cat-social)",
  "Music & Entertainment": "var(--cat-music)",
  "Educational & Cognitive": "var(--cat-cognitive)",
  "Outdoor & Nature": "var(--cat-outdoor)",
  "Spiritual & Reflection": "var(--cat-spiritual)",
  "Culinary": "var(--cat-culinary)",
};

let state = {
  mode: "existing",
  view: "recommended",
  currentResidentId: null,
  selectedTags: new Set(),
  pendingFeedback: null,   // { activity_id, name }
  attended: null,
  rating: 0,
  browseSearch: "",
  browseCategory: "",
};

// ---------------------------------------------------------------------
// INIT
// ---------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
  await loadResidents();
  await loadInterestTags();
  await loadCategories();
  await refreshStats();
  bindEvents();
});

async function loadResidents() {
  const residents = await fetchJSON("/api/residents");
  const select = document.getElementById("resident-select");
  select.innerHTML = residents.map(
    r => `<option value="${r.resident_id}">${r.name} (${r.resident_id})</option>`
  ).join("");
  if (residents.length) {
    state.currentResidentId = residents[0].resident_id;
    updateResidentMeta(residents.find(r => r.resident_id === state.currentResidentId));
    await loadRecommendations(state.currentResidentId);
  }
}

async function loadInterestTags() {
  const tags = await fetchJSON("/api/interest-tags");
  const container = document.getElementById("interest-tags");
  container.innerHTML = tags.map(
    t => `<span class="tag-chip" data-tag="${t}">${t.replace(/-/g, " ")}</span>`
  ).join("");
  container.querySelectorAll(".tag-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const tag = chip.dataset.tag;
      if (state.selectedTags.has(tag)) {
        state.selectedTags.delete(tag);
        chip.classList.remove("selected");
      } else {
        state.selectedTags.add(tag);
        chip.classList.add("selected");
      }
    });
  });
}

// ---------------------------------------------------------------------
// EVENTS
// ---------------------------------------------------------------------
function bindEvents() {
  document.querySelectorAll(".mode-btn").forEach(btn => {
    btn.addEventListener("click", () => switchMode(btn.dataset.mode));
  });

  document.querySelectorAll(".view-tab").forEach(tab => {
    tab.addEventListener("click", () => switchView(tab.dataset.view));
  });

  document.getElementById("browse-search").addEventListener("input", debounce((e) => {
    state.browseSearch = e.target.value;
    loadBrowseActivities();
  }, 250));

  document.getElementById("resident-select").addEventListener("change", async (e) => {
    state.currentResidentId = e.target.value;
    await loadRecommendations(state.currentResidentId);
  });

  document.getElementById("weight-slider").addEventListener("change", async () => {
    if (state.currentResidentId) await loadRecommendations(state.currentResidentId);
  });

  document.getElementById("register-btn").addEventListener("click", registerNewResident);

  // modal
  document.getElementById("cancel-feedback").addEventListener("click", closeModal);
  document.querySelectorAll(".toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => selectAttended(btn.dataset.attended === "true", btn));
  });
  document.querySelectorAll("#star-picker span").forEach(star => {
    star.addEventListener("click", () => selectRating(parseInt(star.dataset.star, 10)));
  });
  document.getElementById("submit-feedback").addEventListener("click", submitFeedback);
}

function switchMode(mode) {
  state.mode = mode;
  document.querySelectorAll(".mode-btn").forEach(b => b.classList.toggle("active", b.dataset.mode === mode));
  document.getElementById("mode-existing").classList.toggle("hidden", mode !== "existing");
  document.getElementById("mode-new").classList.toggle("hidden", mode !== "new");
}

function switchView(view) {
  state.view = view;
  document.querySelectorAll(".view-tab").forEach(t => t.classList.toggle("active", t.dataset.view === view));
  document.getElementById("view-recommended").classList.toggle("hidden", view !== "recommended");
  document.getElementById("view-browse").classList.toggle("hidden", view !== "browse");
  if (view === "browse" && !document.getElementById("browse-grid").childElementCount) {
    loadBrowseActivities();
  }
}

function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// ---------------------------------------------------------------------
// RESIDENT REGISTRATION
// ---------------------------------------------------------------------
async function registerNewResident() {
  const name = document.getElementById("new-name").value.trim();
  const mobility = document.getElementById("new-mobility").value;
  const errorEl = document.getElementById("register-error");
  errorEl.textContent = "";

  if (state.selectedTags.size === 0) {
    errorEl.textContent = "Pick at least one interest.";
    return;
  }

  try {
    const res = await fetchJSON("/api/residents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name, mobility_level: mobility, interests: Array.from(state.selectedTags),
      }),
    });
    state.currentResidentId = res.resident_id;
    await loadResidents();                 // refresh dropdown to include the new resident
    switchMode("existing");
    document.getElementById("resident-select").value = state.currentResidentId;
    await loadRecommendations(state.currentResidentId);
    await refreshStats();
  } catch (err) {
    errorEl.textContent = "Something went wrong -- please try again.";
  }
}

async function loadCategories() {
  const categories = await fetchJSON("/api/categories");
  const container = document.getElementById("category-filters");
  container.innerHTML = `<span class="cat-chip active" data-cat="">All</span>` + categories.map(
    c => `<span class="cat-chip" data-cat="${c}">${c}</span>`
  ).join("");

  container.querySelectorAll(".cat-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      state.browseCategory = chip.dataset.cat;
      container.querySelectorAll(".cat-chip").forEach(c => {
        c.classList.toggle("active", c.dataset.cat === state.browseCategory);
      });
      loadBrowseActivities();
    });
  });
}

async function loadBrowseActivities() {
  const params = new URLSearchParams();
  if (state.browseSearch) params.set("q", state.browseSearch);
  if (state.browseCategory) params.set("category", state.browseCategory);

  const activities = await fetchJSON(`/api/activities?${params.toString()}`);
  const grid = document.getElementById("browse-grid");
  document.getElementById("browse-count").textContent =
    `${activities.length} activit${activities.length === 1 ? "y" : "ies"}`;

  if (!activities.length) {
    grid.innerHTML = `<div class="browse-empty">No activities match your search.</div>`;
    return;
  }

  grid.innerHTML = activities.map(a => {
    const color = CATEGORY_COLORS[a.category] || "var(--sage)";
    const tags = String(a.tags).split(",").slice(0, 3);
    return `
      <div class="browse-card" style="--cat-color:${color}" data-activity-id="${a.activity_id}">
        <span class="b-name">${a.name}</span>
        <span class="b-cat">${a.category}</span>
        <div class="b-tags">${tags.map(t => `<span>${t.replace(/-/g, " ")}</span>`).join("")}</div>
        <div class="b-meta"><span>${a.duration_min} min</span><span>${a.physical_intensity} intensity</span></div>
        <button class="b-log-btn" data-activity-id="${a.activity_id}" data-activity-name="${a.name}">Log feedback</button>
      </div>`;
  }).join("");

  grid.querySelectorAll(".browse-card").forEach(card => {
    card.addEventListener("click", () => {
      if (state.currentResidentId) logImplicitClick(card.dataset.activityId);
    });
  });
  grid.querySelectorAll(".b-log-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (!state.currentResidentId) return;
      openModal(btn.dataset.activityId, btn.dataset.activityName);
    });
  });
}

// ---------------------------------------------------------------------
// RECOMMENDATIONS
// ---------------------------------------------------------------------
async function loadRecommendations(residentId) {
  const weight = document.getElementById("weight-slider").value;
  const data = await fetchJSON(`/api/recommendations/${residentId}?content_weight=${weight}&n=5`);

  document.getElementById("recs-heading").textContent = `Recommended for ${data.resident.name}`;
  updateResidentMeta(data.resident);

  const list = document.getElementById("recs-list");
  if (!data.recommendations.length) {
    list.innerHTML = `<div class="empty-state">No suitable activities found yet -- try adjusting interests.</div>`;
    return;
  }

  list.innerHTML = data.recommendations.map(rec => {
    const color = CATEGORY_COLORS[rec.category] || "var(--sage)";
    return `
      <div class="rec-card" style="--cat-color:${color}" data-activity-id="${rec.activity_id}">
        <div class="rec-main">
          <div class="rec-name-row">
            <span class="rec-name">${rec.name}</span>
            <span class="rec-cat">${rec.category}</span>
          </div>
          <p class="rec-explain">${rec.explanation}</p>
          <div class="rec-tags">
            <span>${rec.duration_min} min</span>
            <span>${rec.physical_intensity} intensity</span>
          </div>
        </div>
        <div class="rec-actions">
          <div class="score-badge">${Math.round(rec.hybrid_score * 100)}%</div>
          <button class="log-btn" data-activity-id="${rec.activity_id}" data-activity-name="${rec.name}">
            Log feedback
          </button>
        </div>
      </div>`;
  }).join("");

  list.querySelectorAll(".rec-card").forEach(card => {
    card.addEventListener("click", (e) => {
      // Log implicit "click" interest whenever the card is engaged with,
      // whether or not they go on to submit explicit feedback.
      logImplicitClick(card.dataset.activityId);
    });
  });

  list.querySelectorAll(".log-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation(); // don't double-trigger the card's own click handler oddly
      openModal(btn.dataset.activityId, btn.dataset.activityName);
    });
  });
}

async function logImplicitClick(activityId) {
  try {
    await fetchJSON("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resident_id: state.currentResidentId,
        activity_id: activityId,
      }),
    });
  } catch (err) {
    // Implicit tracking failing silently is fine -- it shouldn't block the UI.
    console.warn("Could not log click", err);
  }
}

function updateResidentMeta(resident) {
  const el = document.getElementById("resident-meta");
  if (!resident) { el.textContent = ""; return; }
  el.textContent = `Interests: ${resident.interests} · Mobility: ${resident.mobility_level.replace(/_/g, " ")}`;
}

// ---------------------------------------------------------------------
// FEEDBACK MODAL
// ---------------------------------------------------------------------
function openModal(activityId, activityName) {
  state.pendingFeedback = { activity_id: activityId, name: activityName };
  state.attended = null;
  state.rating = 0;

  document.getElementById("feedback-title").textContent = "Log feedback";
  document.getElementById("feedback-sub").textContent = activityName;
  document.querySelectorAll(".toggle-btn").forEach(b => b.classList.remove("selected"));
  document.getElementById("rating-block").classList.add("hidden");
  renderStars(0);
  document.getElementById("submit-feedback").disabled = true;
  document.getElementById("feedback-modal").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("feedback-modal").classList.add("hidden");
}

function selectAttended(attended, btn) {
  state.attended = attended;
  document.querySelectorAll(".toggle-btn").forEach(b => b.classList.remove("selected"));
  btn.classList.add("selected");

  const ratingBlock = document.getElementById("rating-block");
  if (attended) {
    ratingBlock.classList.remove("hidden");
    document.getElementById("submit-feedback").disabled = state.rating === 0;
  } else {
    ratingBlock.classList.add("hidden");
    document.getElementById("submit-feedback").disabled = false;
  }
}

function selectRating(stars) {
  state.rating = stars;
  renderStars(stars);
  if (state.attended) document.getElementById("submit-feedback").disabled = false;
}

function renderStars(count) {
  document.querySelectorAll("#star-picker span").forEach(star => {
    star.classList.toggle("filled", parseInt(star.dataset.star, 10) <= count);
  });
}

async function submitFeedback() {
  if (!state.pendingFeedback || state.attended === null) return;

  await fetchJSON("/api/interactions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      resident_id: state.currentResidentId,
      activity_id: state.pendingFeedback.activity_id,
      attended: state.attended,
      rating: state.attended ? state.rating : null,
    }),
  });

  closeModal();
  await loadRecommendations(state.currentResidentId);  // this resident's feed updates
  await refreshStats();                                  // stats/recent-activity update for everyone
}

// ---------------------------------------------------------------------
// FACILITY INSIGHTS
// ---------------------------------------------------------------------
async function refreshStats() {
  const data = await fetchJSON("/api/stats");

  document.getElementById("topbar-stats").innerHTML = `
    <div class="stat-item"><span class="num">${data.total_residents}</span><span class="label">Residents</span></div>
    <div class="stat-item"><span class="num">${data.total_activities}</span><span class="label">Activities</span></div>
    <div class="stat-item"><span class="num">${data.total_attended}</span><span class="label">Logged visits</span></div>
    <div class="stat-item"><span class="num">${data.total_clicks}</span><span class="label">Clicks tracked</span></div>
  `;

  const entries = Object.entries(data.category_popularity).sort((a, b) => b[1] - a[1]);
  const maxCount = entries.length ? entries[0][1] : 1;
  document.getElementById("category-chart").innerHTML = entries.map(([cat, count]) => {
    const color = CATEGORY_COLORS[cat] || "var(--sage)";
    const pct = Math.round((count / maxCount) * 100);
    return `
      <div class="chart-row">
        <span class="chart-label">${cat}</span>
        <div class="chart-bar-track"><div class="chart-bar-fill" style="width:${pct}%;background:${color}"></div></div>
        <span class="chart-count">${count}</span>
      </div>`;
  }).join("") || `<p class="hint">No attendance logged yet.</p>`;

  const feed = data.recent_activity;
  document.getElementById("recent-feed").innerHTML = feed.length
    ? feed.map(item => `
        <li><b>${item.resident_id}</b> ${item.attended ? `attended <b>${item.activity_id}</b>${item.rating ? ` (${item.rating}★)` : ""}` : `skipped <b>${item.activity_id}</b>`} · ${item.date}</li>
      `).join("")
    : `<li class="hint">No live activity yet -- log some feedback to see it here.</li>`;
}

// ---------------------------------------------------------------------
// UTIL
// ---------------------------------------------------------------------
async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed: ${res.status}`);
  }
  return res.json();
}