/**
 * LearnMate AI - Learning History Page Logic
 * Connected to Flask Backend API with real MySQL database persistence.
 */

const LearnMateHistory = {
  historyList: [],

  async init() {
    await this.loadHistory();
    this.bindSearchAndFilters();
  },

  async loadHistory() {
    const container = document.getElementById("history-list-container");
    if (container) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
          <p>Loading your learning history...</p>
        </div>
      `;
    }

    try {
      const res = await LearnMateAPI.getSessions();
      if (res.success && res.data) {
        this.historyList = res.data.sessions || [];
      } else {
        this.historyList = [];
      }
    } catch (e) {
      console.error("Failed to load history sessions:", e);
      this.historyList = [];
    }

    this.renderHistory();
  },

  renderHistory(items = this.historyList) {
    const container = document.getElementById("history-list-container");
    if (!container) return;

    if (items.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 3.5rem 2rem; background: #FFFFFF; border-radius: var(--radius-xl); border: 1px dashed var(--border-subtle);">
          <div style="font-size: 2.75rem; margin-bottom: 0.75rem;">📚</div>
          <h3 style="font-size: 1.25rem; margin-bottom: 0.35rem; color: var(--text-primary);">No learning sessions yet</h3>
          <p style="color: var(--text-muted); font-size: 0.9rem; max-width: 440px; margin: 0 auto 1.5rem;">
            Start exploring topics or studying uploaded materials from your Home workspace. Your study records, generated content, and quiz scores will appear here.
          </p>
          <a href="app.html" class="btn btn-primary btn-sm">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            Start Your First Session
          </a>
        </div>
      `;
      return;
    }

    container.innerHTML = items.map(session => {
      const resourceBadges = (session.resources || []).map(res => `
        <span class="resource-tag-chip">${res}</span>
      `).join("");

      let scoreBadgeClass = "badge-purple";
      if (session.scoreStatus === "success") scoreBadgeClass = "badge-success";
      else if (session.scoreStatus === "warning") scoreBadgeClass = "badge-danger";

      return `
        <div class="history-item-card" id="history-card-${session.id}">
          <div class="flex items-center justify-between flex-wrap gap-3 mb-3">
            <div>
              <h3 style="font-size: 1.25rem; color: var(--text-primary); margin-bottom: 0.25rem;">
                ${session.topic}
              </h3>
              <div class="flex items-center gap-2" style="font-size: 0.825rem; color: var(--text-muted);">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                <span>Studied on ${session.date} at ${session.time}</span>
                ${session.materialName ? `<span>• Source: ${session.materialName}</span>` : ""}
              </div>
            </div>

            <div class="flex items-center gap-3">
              <div style="text-align: right;">
                <div style="font-size: 0.75rem; color: var(--text-muted); font-weight: 600;">QUIZ SCORE</div>
                <span class="badge ${scoreBadgeClass}" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">
                  ${session.score}
                </span>
              </div>
              <button class="btn btn-primary btn-sm btn-reopen-session" data-topic="${session.topic}" data-id="${session.id}">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                Reopen Session
              </button>
              <button class="btn btn-outline btn-sm btn-delete-history" data-id="${session.id}" data-topic="${session.topic}">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>
              </button>
            </div>
          </div>

          <div style="border-top: 1px solid var(--border-subtle); padding-top: 0.85rem;" class="flex items-center gap-2 flex-wrap">
            <span style="font-size: 0.775rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Generated Resources:</span>
            ${resourceBadges}
          </div>
        </div>
      `;
    }).join("");

    // Bind item actions
    container.querySelectorAll(".btn-reopen-session").forEach(btn => {
      btn.addEventListener("click", () => {
        const topic = btn.dataset.topic;
        const sessionId = btn.dataset.id;
        sessionStorage.setItem("learnmate_launch_topic", topic);
        if (sessionId) sessionStorage.setItem("learnmate_launch_session_id", sessionId);
        window.location.href = "app.html";
      });
    });

    container.querySelectorAll(".btn-delete-history").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const topic = btn.dataset.topic;
        if (!confirm(`Delete learning session for "${topic}"?`)) return;

        btn.disabled = true;
        LearnMateComponents.showToast(`Removing session "${topic}"...`, "info");
        try {
          const res = await LearnMateAPI.deleteSession(id);
          if (res.success) {
            LearnMateComponents.showToast("Session removed from history.", "success");
            await this.loadHistory();
          } else {
            LearnMateComponents.showToast(res.message || "Failed to remove session.", "danger");
            btn.disabled = false;
          }
        } catch (e) {
          LearnMateComponents.showToast("Network error deleting session.", "danger");
          btn.disabled = false;
        }
      });
    });
  },

  bindSearchAndFilters() {
    const searchInput = document.getElementById("search-history-input");
    const filterSelect = document.getElementById("filter-history-score");

    const filterHandler = () => {
      const query = searchInput ? searchInput.value.toLowerCase().trim() : "";
      const filter = filterSelect ? filterSelect.value : "all";

      const filtered = this.historyList.filter(s => {
        const matchesQuery = s.topic.toLowerCase().includes(query);
        let matchesScore = true;
        const scoreVal = parseInt(s.score);
        if (filter === "high") matchesScore = !isNaN(scoreVal) && scoreVal >= 80;
        else if (filter === "review") matchesScore = !isNaN(scoreVal) && scoreVal < 70;
        return matchesQuery && matchesScore;
      });

      this.renderHistory(filtered);
    };

    if (searchInput) searchInput.addEventListener("input", filterHandler);
    if (filterSelect) filterSelect.addEventListener("change", filterHandler);
  }
};
