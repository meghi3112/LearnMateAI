/**
 * LearnMate AI - Performance Analytics Logic & SVG Chart Rendering
 * Connected to Flask Backend API with real MySQL database persistence.
 */

const LearnMatePerformance = {
  performanceData: null,

  async init() {
    await this.loadPerformance();
  },

  async loadPerformance() {
    try {
      const res = await LearnMateAPI.getPerformance();
      if (res.success && res.data) {
        this.performanceData = res.data;
      } else {
        this.performanceData = { has_data: false };
      }
    } catch (e) {
      console.error("Failed to load performance metrics:", e);
      this.performanceData = { has_data: false };
    }

    this.renderKPIs();
    this.renderScoreTrendChart();
    this.renderTopicBreakdown();
  },

  renderKPIs() {
    const data = this.performanceData || {};
    const kpis = data.kpis || {
      topicsStudied: "0 Topics",
      quizzesAttempted: "0 Quizzes",
      averageScore: "0%",
      overallProgress: "0%"
    };

    const elTopics = document.getElementById("kpi-topics-count");
    const elQuizzes = document.getElementById("kpi-quizzes-count");
    const elAvgScore = document.getElementById("kpi-avg-score");
    const elProgress = document.getElementById("kpi-overall-progress");

    if (elTopics) elTopics.textContent = kpis.topicsStudied;
    if (elQuizzes) elQuizzes.textContent = kpis.quizzesAttempted;
    if (elAvgScore) elAvgScore.textContent = kpis.averageScore;
    if (elProgress) elProgress.textContent = kpis.overallProgress;
  },

  renderScoreTrendChart() {
    const container = document.getElementById("chart-score-trend");
    if (!container) return;

    const data = (this.performanceData && this.performanceData.scoreTrend) || [];

    if (!this.performanceData || !this.performanceData.has_data || data.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 3rem 1.5rem; color: var(--text-muted);">
          <div style="font-size: 2.25rem; margin-bottom: 0.5rem;">📈</div>
          <p style="font-weight: 600; color: var(--text-primary); margin-bottom: 0.35rem;">No quiz data yet</p>
          <p style="font-size: 0.85rem; max-width: 360px; margin: 0 auto 1rem;">
            Take adaptive quizzes from your AI Learning workspace to see your score trajectory plotted over time.
          </p>
          <a href="app.html" class="btn btn-outline btn-sm">Take a Quiz</a>
        </div>
      `;
      return;
    }

    const width = 500;
    const height = 220;
    const padding = 40;

    const xStep = data.length > 1 ? (width - padding * 2) / (data.length - 1) : 0;
    const points = data.map((d, i) => {
      const x = data.length > 1 ? padding + i * xStep : width / 2;
      const y = height - padding - ((d.score / 100) * (height - padding * 2));
      return { x, y, score: d.score, label: d.date };
    });

    const pathD = points.reduce((acc, pt, i) => `${acc} ${i === 0 ? "M" : "L"} ${pt.x} ${pt.y}`, "");
    const areaD = points.length > 1 
      ? `${pathD} L ${points[points.length - 1].x} ${height - padding} L ${points[0].x} ${height - padding} Z`
      : "";

    const dotsSvg = points.map(pt => `
      <circle cx="${pt.x}" cy="${pt.y}" r="5" fill="#6C5CE7" stroke="#FFFFFF" stroke-width="2"/>
      <text x="${pt.x}" y="${pt.y - 12}" text-anchor="middle" font-size="11" font-weight="700" fill="#6C5CE7">${pt.score}%</text>
      <text x="${pt.x}" y="${height - padding + 20}" text-anchor="middle" font-size="10" fill="#586079">${pt.label}</text>
    `).join("");

    container.innerHTML = `
      <svg width="100%" height="100%" viewBox="0 0 ${width} ${height}">
        <defs>
          <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#6C5CE7" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#6C5CE7" stop-opacity="0.0"/>
          </linearGradient>
        </defs>

        <!-- Horizontal Grid Lines -->
        <line x1="${padding}" y1="${padding}" x2="${width - padding}" y2="${padding}" stroke="#E8EBF2" stroke-dasharray="3,3"/>
        <line x1="${padding}" y1="${(height - padding * 2) / 2 + padding}" x2="${width - padding}" y2="${(height - padding * 2) / 2 + padding}" stroke="#E8EBF2" stroke-dasharray="3,3"/>
        <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#CBD5E1"/>

        <!-- Area & Line -->
        ${areaD ? `<path d="${areaD}" fill="url(#trendGradient)"/>` : ""}
        ${points.length > 1 ? `<path d="${pathD}" fill="none" stroke="#6C5CE7" stroke-width="3" stroke-linecap="round"/>` : ""}

        <!-- Dots & Labels -->
        ${dotsSvg}
      </svg>
    `;
  },

  renderTopicBreakdown() {
    const container = document.getElementById("chart-topic-bars");
    const strongListContainer = document.getElementById("strong-topics-list");
    const weakListContainer = document.getElementById("weak-topics-list");

    const topics = (this.performanceData && this.performanceData.topicBreakdown) || [];
    const strongTopics = (this.performanceData && this.performanceData.strongTopics) || [];
    const weakTopics = (this.performanceData && this.performanceData.weakTopics) || [];

    if (container) {
      if (topics.length === 0) {
        container.innerHTML = `
          <div style="text-align: center; padding: 2.5rem 1rem; color: var(--text-muted);">
            <p style="font-size: 0.9rem;">No topic breakdown available yet.</p>
          </div>
        `;
      } else {
        container.innerHTML = topics.map(t => {
          let barColor = "var(--primary)";
          if (t.status === "strong") barColor = "var(--success)";
          else if (t.status === "needs-improvement") barColor = "var(--danger)";

          return `
            <div style="margin-bottom: 1.25rem;">
              <div class="flex justify-between items-center mb-1" style="font-size: 0.875rem;">
                <span style="font-weight: 600; color: var(--text-primary);">${t.topic}</span>
                <span style="font-weight: 700; color: ${barColor};">${t.score}%</span>
              </div>
              <div class="progress-track" style="height: 10px;">
                <div class="progress-fill" style="width: ${t.score}%; background: ${barColor};"></div>
              </div>
            </div>
          `;
        }).join("");
      }
    }

    if (strongListContainer) {
      if (strongTopics.length === 0) {
        strongListContainer.innerHTML = `
          <p style="color: var(--text-muted); font-size: 0.85rem; font-style: italic;">
            Complete quizzes with 80%+ scores to highlight your mastery here.
          </p>
        `;
      } else {
        strongListContainer.innerHTML = strongTopics.map(t => `
          <div class="flex items-center justify-between py-2" style="border-bottom: 1px solid var(--border-subtle); font-size: 0.875rem;">
            <span style="font-weight: 500;">${t.topic}</span>
            <span class="badge badge-success">${t.score}%</span>
          </div>
        `).join("");
      }
    }

    if (weakListContainer) {
      if (weakTopics.length === 0) {
        weakListContainer.innerHTML = `
          <p style="color: var(--text-muted); font-size: 0.85rem; font-style: italic;">
            No critical weak spots detected. Keep up the consistent study pace!
          </p>
        `;
      } else {
        weakListContainer.innerHTML = weakTopics.map(t => `
          <div class="flex items-center justify-between py-2" style="border-bottom: 1px solid var(--border-subtle); font-size: 0.875rem;">
            <span style="font-weight: 500;">${t.topic}</span>
            <span class="badge badge-danger">${t.score}%</span>
          </div>
        `).join("");
      }
    }
  }
};
