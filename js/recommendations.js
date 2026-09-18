/**
 * LearnMate AI - Recommendations Page Logic
 * Connected to Flask Backend API with real MySQL database persistence.
 */

const LearnMateRecommendations = {
  recommendationsList: [],

  async init() {
    await this.loadRecommendations();
  },

  async loadRecommendations() {
    const container = document.getElementById("recommendations-grid-container");
    if (container) {
      container.innerHTML = `
        <div style="text-align: center; padding: 3rem; color: var(--text-muted); grid-column: 1 / -1;">
          <p>Analyzing your study patterns and preferences...</p>
        </div>
      `;
    }

    try {
      const res = await LearnMateAPI.getRecommendations();
      if (res.success && res.data && res.data.recommendations) {
        this.recommendationsList = res.data.recommendations;
      } else {
        this.recommendationsList = [];
      }
    } catch (e) {
      console.error("Failed to load recommendations:", e);
      this.recommendationsList = [];
    }

    this.renderRecommendations();
  },

  renderRecommendations() {
    const container = document.getElementById("recommendations-grid-container");
    if (!container) return;

    if (this.recommendationsList.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 4rem 2rem; background: #FFFFFF; border-radius: var(--radius-xl); border: 1px dashed var(--border-subtle); grid-column: 1 / -1;">
          <div style="font-size: 2.75rem; margin-bottom: 0.75rem;">💡</div>
          <h3 style="font-size: 1.25rem; margin-bottom: 0.35rem; color: var(--text-primary);">No recommendations yet</h3>
          <p style="color: var(--text-muted); font-size: 0.9rem; max-width: 460px; margin: 0 auto 1.5rem;">
            As you explore study topics, upload course notes, and attempt quizzes, LearnMate AI will generate personalized study plans and revision prompts here based on your learning style.
          </p>
          <a href="app.html" class="btn btn-primary btn-sm">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
            Open Learning Workspace
          </a>
        </div>
      `;
      return;
    }

    container.innerHTML = this.recommendationsList.map(rec => {
      let badgeColor = rec.badgeType || "purple";
      if (badgeColor === "danger") badgeColor = "badge-danger";
      else if (badgeColor === "blue") badgeColor = "badge-blue";
      else badgeColor = "badge-purple";

      return `
        <div class="rec-card" id="rec-card-${rec.id}">
          <div>
            <div class="flex items-center justify-between mb-3">
              <span class="badge ${badgeColor}">${rec.category}</span>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--primary)" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
            </div>
            <h3 style="font-size: 1.25rem; color: var(--text-primary); margin-bottom: 0.5rem;">${rec.title}</h3>
            <div class="rec-reason">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              <span>${rec.reason}</span>
            </div>
          </div>

          <div class="flex items-center justify-between pt-4" style="border-top: 1px solid var(--border-subtle);">
            <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 500;">Adaptive Suggestion</span>
            <button class="btn btn-primary btn-sm btn-action-rec" data-topic="${rec.topic || ''}">
              ${rec.actionText || 'Explore'}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
            </button>
          </div>
        </div>
      `;
    }).join("");

    container.querySelectorAll(".btn-action-rec").forEach(btn => {
      btn.addEventListener("click", () => {
        const topic = btn.dataset.topic;
        if (topic) {
          sessionStorage.setItem("learnmate_launch_topic", topic);
        }
        window.location.href = "app.html";
      });
    });
  }
};
