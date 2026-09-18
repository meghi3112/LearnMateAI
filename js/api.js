/**
 * LearnMate AI - Frontend API Client
 * Manages communication between the frontend and Flask backend API.
 */

const LearnMateAPI = {
  // Configurable base URL with fallback to localhost:5000
  baseUrl: (function() {
    if (typeof window !== "undefined" && window.location) {
      if (window.location.origin && window.location.origin.startsWith("http")) {
        return window.location.origin;
      }
      const host = window.location.hostname || "127.0.0.1";
      const resolvedHost = (host === "localhost" || host === "127.0.0.1") ? "127.0.0.1" : host;
      return `http://${resolvedHost}:5000`;
    }
    return "http://127.0.0.1:5000";
  })(),

  /**
   * Internal generic request handler with JSON serialization, FormData support, and token management.
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = { ...(options.headers || {}) };

    const isFormData = options.body instanceof FormData;
    if (!isFormData && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }

    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const user = this.getUser();
    if (user && user.user_id) {
      headers["X-User-Id"] = String(user.user_id);
    }

    const config = {
      ...options,
      headers
    };

    if (config.body && typeof config.body === "object" && !isFormData) {
      config.body = JSON.stringify(config.body);
    }

    try {
      const response = await fetch(url, config);
      const contentType = response.headers.get("content-type");
      const isJson = contentType && contentType.includes("application/json");
      const data = isJson ? await response.json() : await response.text();

      if (!response.ok) {
        if (response.status === 401) {
          // Check if not already on login/signup/landing
          if (typeof window !== "undefined" && window.location) {
            const path = window.location.pathname;
            if (!path.endsWith("login.html") && !path.endsWith("signup.html") && !path.endsWith("index.html")) {
              this.clearUserSession();
              window.location.replace("login.html");
            }
          }
        }
        const errorMsg = (data && data.message) || response.statusText || "Request failed";
        return {
          success: false,
          status: response.status,
          message: errorMsg,
          data
        };
      }

      return {
        success: true,
        status: response.status,
        data
      };
    } catch (err) {
      console.error(`[LearnMateAPI] Network error requesting ${endpoint}:`, err);
      return {
        success: false,
        status: 0,
        message: "Unable to connect to LearnMate AI server. Ensure the Flask backend is running.",
        error: err
      };
    }
  },

  // ==========================================
  // 1. Core Health Check
  // ==========================================
  async checkHealth() {
    return await this.request("/api/health", { method: "GET" });
  },

  // ==========================================
  // 2. Authentication & Profile
  // ==========================================
  async register(fullName, email, password) {
    const res = await this.request("/api/auth/register", {
      method: "POST",
      body: {
        full_name: fullName,
        email: email,
        password: password
      }
    });

    if (res.success && res.data && res.data.user) {
      this.setUserSession(res.data.user, res.data.token);
    }
    return res;
  },

  async login(email, password) {
    const res = await this.request("/api/auth/login", {
      method: "POST",
      body: {
        email: email,
        password: password
      }
    });

    if (res.success && res.data && res.data.user) {
      this.setUserSession(res.data.user, res.data.token);
    }
    return res;
  },

  async getMe() {
    const res = await this.request("/api/auth/me", { method: "GET" });
    if (res.success && res.data && res.data.user) {
      this.setUserSession(res.data.user, this.getToken());
    }
    return res;
  },

  async updateProfile(profileData) {
    const res = await this.request("/api/auth/profile", {
      method: "PUT",
      body: profileData
    });
    if (res.success && res.data && res.data.user) {
      this.setUserSession(res.data.user, this.getToken());
    }
    return res;
  },

  async changePassword(passwordData) {
    return await this.request("/api/auth/password", {
      method: "PUT",
      body: passwordData
    });
  },

  async deleteAccount() {
    const res = await this.request("/api/auth/account", { method: "DELETE" });
    if (res.success) {
      this.clearUserSession();
    }
    return res;
  },

  async logout() {
    try {
      await this.request("/api/auth/logout", { method: "POST" });
    } catch (e) {
      // Ignore network errors on logout
    }
    this.clearUserSession();
    window.location.replace("/");
  },

  // ==========================================
  // 3. Learning Preferences
  // ==========================================
  async savePreferences(preferences, primaryFocus, pace = "Intermediate") {
    const user = this.getUser();
    const userId = user ? user.user_id : null;

    const res = await this.request("/api/preferences", {
      method: "POST",
      body: {
        user_id: userId,
        preferences: preferences,
        primary_focus: primaryFocus,
        pace: pace
      }
    });

    if (res.success && user) {
      user.preferences = preferences;
      user.primary_focus = primaryFocus;
      user.pace = pace;
      this.setUserSession(user, this.getToken());
    }
    return res;
  },

  async getPreferences() {
    const user = this.getUser();
    const userId = user ? user.user_id : null;
    const query = userId ? `?user_id=${userId}` : "";
    return await this.request(`/api/preferences${query}`, { method: "GET" });
  },

  // ==========================================
  // 4. Study Materials
  // ==========================================
  async getMaterials() {
    return await this.request("/api/materials", { method: "GET" });
  },

  async uploadMaterial(formData) {
    return await this.request("/api/materials/upload", {
      method: "POST",
      body: formData
    });
  },

  async deleteMaterial(materialId) {
    return await this.request(`/api/materials/${materialId}`, {
      method: "DELETE"
    });
  },

  getMaterialDownloadUrl(materialId) {
    const token = this.getToken();
    const user = this.getUser();
    const tokenQuery = token ? `?token=${encodeURIComponent(token)}` : (user && user.user_id ? `?user_id=${user.user_id}` : "");
    return `${this.baseUrl}/api/materials/${materialId}/download${tokenQuery}`;
  },

  // ==========================================
  // 5. Learning Sessions & History
  // ==========================================
  async getSessions() {
    return await this.request("/api/sessions", { method: "GET" });
  },

  async createSession(sessionData) {
    return await this.request("/api/sessions", {
      method: "POST",
      body: sessionData
    });
  },

  async deleteSession(sessionId) {
    return await this.request(`/api/sessions/${sessionId}`, {
      method: "DELETE"
    });
  },

  // ==========================================
  // 6. Performance & Quiz Analytics
  // ==========================================
  async getPerformance() {
    return await this.request("/api/performance", { method: "GET" });
  },

  async recordQuizAttempt(attemptData) {
    return await this.request("/api/performance/quiz-attempt", {
      method: "POST",
      body: attemptData
    });
  },

  // ==========================================
  // 7. Recommendations
  // ==========================================
  async getRecommendations() {
    return await this.request("/api/recommendations", { method: "GET" });
  },

  // ==========================================
  // 8. AI / RAG Learning Content Generation
  // ==========================================
  async generateContent(payload) {
    return await this.request("/api/learning/generate", {
      method: "POST",
      body: payload
    });
  },

  async generateDynamicQuiz(payload) {
    return await this.request("/api/learning/quiz/generate", {
      method: "POST",
      body: payload
    });
  },

  async generateDiagram(payload) {
    return await this.request("/api/learning/diagram/generate", {
      method: "POST",
      body: payload
    });
  },

  async getDiagramReferences(topic, concept = "", diagramType = "") {
    const qTopic = encodeURIComponent(topic || "");
    const qConcept = encodeURIComponent(concept || "");
    const qType = encodeURIComponent(diagramType || "");
    return await this.request(`/api/learning/diagram/references?topic=${qTopic}&concept=${qConcept}&diagram_type=${qType}`, {
      method: "GET"
    });
  },

  async getDiagramConcepts(topic, materialId = null) {
    const qTopic = encodeURIComponent(topic || "");
    const qMat = materialId ? `&material_id=${encodeURIComponent(materialId)}` : "";
    return await this.request(`/api/learning/diagram/concepts?topic=${qTopic}${qMat}`, {
      method: "GET"
    });
  },

  async sendChatMessage(payload) {
    return await this.request("/api/learning/chat", {
      method: "POST",
      body: payload
    });
  },

  async getLearningSession(sessionId) {
    return await this.request(`/api/learning/sessions/${sessionId}`, {
      method: "GET"
    });
  },

  async submitQuizAnswers(arg1, arg2, arg3) {
    let quizId = null;
    let sessionId = null;
    let answers = {};

    if (typeof arg1 === "object" && arg1 !== null) {
      quizId = arg1.quiz_id || arg1.quizId;
      sessionId = arg1.session_id || arg1.sessionId;
      answers = arg1.answers || {};
    } else if (typeof arg2 === "object" && arg2 !== null) {
      // Called as (sessionId, answers, quizId)
      sessionId = arg1;
      answers = arg2;
      quizId = arg3;
    } else {
      // Called as (quizId, sessionId, answers)
      quizId = arg1;
      sessionId = arg2;
      answers = arg3 || {};
    }

    return await this.request("/api/learning/quiz-submit", {
      method: "POST",
      body: {
        quiz_id: quizId,
        session_id: sessionId,
        answers: answers
      }
    });
  },

  // ==========================================
  // Session & Local Storage Management
  // ==========================================
  setUserSession(user, token) {
    if (user) {
      localStorage.setItem("learnmate_user", JSON.stringify(user));
    }
    if (token) {
      localStorage.setItem("learnmate_token", token);
    }
    this.syncCurrentUser();
  },

  getUser() {
    try {
      const raw = localStorage.getItem("learnmate_user");
      return raw ? JSON.parse(raw) : null;
    } catch (e) {
      return null;
    }
  },

  getToken() {
    return localStorage.getItem("learnmate_token") || null;
  },

  isAuthenticated() {
    return !!(this.getToken() && this.getUser());
  },

  requireAuth() {
    if (!this.isAuthenticated()) {
      window.location.replace("/");
      return false;
    }
    return true;
  },

  clearUserSession() {
    localStorage.removeItem("learnmate_user");
    localStorage.removeItem("learnmate_token");
    try {
      sessionStorage.clear();
    } catch (e) {}
    if (typeof LearnMateData !== "undefined" && LearnMateData.currentUser) {
      LearnMateData.currentUser.fullName = "Student";
      LearnMateData.currentUser.email = "";
      LearnMateData.currentUser.avatarInitial = "ST";
      LearnMateData.currentUser.preferences = [];
      LearnMateData.currentUser.primaryFocus = "Visual";
    }
  },

  /**
   * Synchronizes LearnMateData.currentUser with actual logged-in user in localStorage
   */
  syncCurrentUser() {
    const user = this.getUser();
    if (!user) {
      if (typeof LearnMateData !== "undefined" && LearnMateData.currentUser) {
        LearnMateData.currentUser.fullName = "Student";
        LearnMateData.currentUser.email = "";
        LearnMateData.currentUser.avatarInitial = "ST";
      }
      return;
    }

    if (typeof LearnMateData !== "undefined" && LearnMateData.currentUser) {
      if (user.full_name) LearnMateData.currentUser.fullName = user.full_name;
      if (user.email) LearnMateData.currentUser.email = user.email;
      if (user.avatar_initial) LearnMateData.currentUser.avatarInitial = user.avatar_initial;
      if (user.preferences && user.preferences.length) LearnMateData.currentUser.preferences = user.preferences;
      if (user.primary_focus) LearnMateData.currentUser.primaryFocus = user.primary_focus;
      if (user.pace) LearnMateData.currentUser.pace = user.pace;
    }
  }
};

// Automatically synchronize user on script load
if (typeof window !== "undefined") {
  window.LearnMateAPI = LearnMateAPI;
  LearnMateAPI.syncCurrentUser();

  // Browser back-button protection: verify auth on bfcache restore
  window.addEventListener("pageshow", (event) => {
    const path = window.location.pathname.toLowerCase();
    const isPublic = path.endsWith("/") || path.endsWith("/index.html") || path.endsWith("/login.html") || path.endsWith("/signup.html") || path === "";
    if (!isPublic && !LearnMateAPI.isAuthenticated()) {
      window.location.replace("/");
    }
  });
}
