/**
 * LearnMate AI - AI Learning Assistant Workspace Engine
 * Connected to Flask Backend API with RAG & Gemini Learning Content Generation.
 * Renders all 8 interactive resources:
 * Simplified Notes, Detailed Explanations, Step-by-Step, Summary,
 * Interactive 3D Flashcards, Q&A Accordion, Mermaid Flowcharts, and 10-Question Adaptive Quiz.
 */

const LearnMateWorkspace = {
  currentSessionId: null,
  currentQuizId: null,
  activeMaterialId: null,
  activeMaterialName: null,
  currentFlashcardIndex: 0,
  flashcardsList: [],
  mermaidCounter: 0,

  init() {
    this.bindChatForm();
    this.bindSuggestedPrompts();
    this.bindPrimaryActions();
    this.bindTopicModal();
    this.bindRecentTopics();
    this.bindClearChat();

    // Initialize Mermaid if available
    if (typeof mermaid !== "undefined") {
      try {
        mermaid.initialize({
          startOnLoad: false,
          theme: 'default',
          securityLevel: 'loose'
        });
      } catch (e) {
        console.warn("Mermaid init warning:", e);
      }
    }

    this.checkLaunchContext();
  },

  // Check if routed from another page with a target topic or saved session
  checkLaunchContext() {
    const launchSessionId = sessionStorage.getItem("learnmate_launch_session_id");
    const launchTopic = sessionStorage.getItem("learnmate_launch_topic");
    const launchMatId = sessionStorage.getItem("learnmate_launch_material_id");

    if (launchSessionId) {
      sessionStorage.removeItem("learnmate_launch_session_id");
      sessionStorage.removeItem("learnmate_launch_topic");
      setTimeout(() => {
        this.loadSavedSession(launchSessionId);
      }, 300);
      return;
    }

    if (launchTopic) {
      sessionStorage.removeItem("learnmate_launch_topic");
      sessionStorage.removeItem("learnmate_launch_material_id");
      setTimeout(() => {
        this.sendUserMessage(`I'd like to study "${launchTopic}"`, launchMatId);
      }, 400);
    }
  },

  // 1. Chat Form Handling
  bindChatForm() {
    const form = document.getElementById("home-chat-form");
    const input = document.getElementById("home-chat-input");
    const attachBtn = document.getElementById("btn-chat-attach");
    const fileInput = document.getElementById("hidden-file-input");

    if (form) {
      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const text = input ? input.value.trim() : "";
        if (!text) return;

        this.sendUserMessage(text);
        input.value = "";
      });
    }

    if (attachBtn && fileInput) {
      attachBtn.addEventListener("click", () => fileInput.click());
    }
  },

  // 2. Suggested Prompts Handler
  bindSuggestedPrompts() {
    const promptButtons = document.querySelectorAll(".prompt-pill-btn");
    const chatInput = document.getElementById("home-chat-input");

    promptButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const promptText = btn.dataset.prompt;
        if (chatInput) {
          chatInput.value = promptText;
          chatInput.focus();
        }
      });
    });
  },

  // 3. Primary Action Cards Handler (Upload & Enter Topic)
  bindPrimaryActions() {
    const uploadCard = document.getElementById("btn-action-upload");
    const topicCard = document.getElementById("btn-action-topic");
    const fileInput = document.getElementById("hidden-file-input");
    const topicModal = document.getElementById("topic-input-modal");

    if (uploadCard && fileInput) {
      uploadCard.addEventListener("click", () => fileInput.click());
    }

    if (fileInput) {
      fileInput.addEventListener("change", async (e) => {
        if (e.target.files && e.target.files.length > 0) {
          const file = e.target.files[0];
          await this.handleFileUpload(file);
        }
      });
    }

    if (topicCard && topicModal) {
      topicCard.addEventListener("click", () => {
        topicModal.classList.add("active");
        const modalInput = document.getElementById("modal-topic-input");
        if (modalInput) modalInput.focus();
      });
    }
  },

  // 4. Topic Entry Modal Handler
  bindTopicModal() {
    const modal = document.getElementById("topic-input-modal");
    const closeBtn = document.getElementById("btn-close-topic-modal");
    const cancelBtn = document.getElementById("btn-cancel-topic-modal");
    const startBtn = document.getElementById("btn-start-topic-session");
    const modalInput = document.getElementById("modal-topic-input");

    const closeModal = () => {
      if (modal) modal.classList.remove("active");
    };

    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

    // Suggestion chips in modal
    document.querySelectorAll(".modal-suggestion").forEach(chip => {
      chip.addEventListener("click", () => {
        if (modalInput) modalInput.value = chip.dataset.topic;
      });
    });

    if (startBtn && modalInput) {
      startBtn.addEventListener("click", () => {
        const topic = modalInput.value.trim() || "Operating Systems: CPU Scheduling";
        closeModal();
        modalInput.value = "";
        this.sendUserMessage(`I'd like to study "${topic}"`);
      });
    }
  },

  // 5. Recent Topics Click
  bindRecentTopics() {
    document.querySelectorAll(".recent-topic-item").forEach(item => {
      item.addEventListener("click", () => {
        const topic = item.dataset.topic;
        this.sendUserMessage(`Let's revisit "${topic}"`);
      });
    });
  },

  // 6. Clear Chat Handler
  bindClearChat() {
    const clearBtn = document.getElementById("btn-clear-chat");
    const container = document.getElementById("chat-messages-stream");

    if (clearBtn && container) {
      clearBtn.addEventListener("click", () => {
        container.innerHTML = `
          <div class="chat-message-row assistant">
            <div class="chat-ai-avatar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
                <path d="M6 12v5c3 3 9 3 12 0v-5"/>
              </svg>
            </div>
            <div class="chat-bubble-content">
              <p style="margin-bottom: 0.65rem;">Hi! I'm LearnMate AI. 😊</p>
              <p>Upload a study material or enter a topic, and I'll create personalized learning resources for you. What would you like to do?</p>
            </div>
          </div>
        `;
        this.currentSessionId = null;
        this.currentQuizId = null;
        this.activeMaterialId = null;
        this.activeMaterialName = null;
        LearnMateComponents.showToast("Chat conversation reset.", "info");
      });
    }
  },

  // Send message and trigger real learning generation or follow-up answer
  async sendUserMessage(text, materialId = null) {
    const container = document.getElementById("chat-messages-stream");
    if (!container) return;

    if (materialId) {
      this.activeMaterialId = materialId;
    }

    const user = (typeof LearnMateAPI !== "undefined" && LearnMateAPI.getUser()) || LearnMateData.currentUser;
    const initial = (user && (user.avatar_initial || user.avatarInitial)) || "M";

    // Append User message
    const userRow = document.createElement("div");
    userRow.className = "chat-message-row user";
    userRow.innerHTML = `
      <div class="chat-user-avatar">${initial}</div>
      <div class="chat-bubble-content">
        <p>${this.escapeHtml(text)}</p>
      </div>
    `;
    container.appendChild(userRow);
    container.scrollTop = container.scrollHeight;

    // Check if this is an explicit command to start a new learning topic session
    const isNewStudySessionCmd = /^(I'd like to study|Let's revisit)\s+["']/i.test(text);

    // If an active material or session is present and it's not an explicit new session command
    if ((this.activeMaterialId || this.currentSessionId) && !isNewStudySessionCmd) {
      await this.sendFollowUpQuery(text);
    } else {
      // If student is explicitly starting a new study topic session without an uploaded material, clear active material
      if (isNewStudySessionCmd && !materialId) {
        this.activeMaterialId = null;
        this.activeMaterialName = null;
        this.currentSessionId = null;
        this.currentQuizId = null;
      }

      // Clean topic string
      const cleanTopic = text
        .replace(/^I'd like to study ["']?/i, '')
        .replace(/^Let's revisit ["']?/i, '')
        .replace(/^Explain this topic in simple terms/i, 'Core Concepts')
        .replace(/^Give me a summary/i, 'Summary Review')
        .replace(/^Create flashcards/i, 'Key Definitions & Terms')
        .replace(/^Generate a quiz/i, 'Knowledge Check')
        .replace(/^Draw a flowchart/i, 'Process Architecture')
        .replace(/^Suggest important questions/i, 'Exam Preparation')
        .replace(/["']?$/g, '')
        .trim() || "Computer Science Fundamentals";

      await this.generateContentForTopic(cleanTopic, materialId || this.activeMaterialId);
    }
  },

  // Handle conversational follow-up questions grounded in active material / session
  async sendFollowUpQuery(text) {
    const container = document.getElementById("chat-messages-stream");
    if (!container) return;

    // Add loader
    const loaderRow = document.createElement("div");
    loaderRow.className = "chat-message-row assistant";
    loaderRow.id = "chat-followup-loader";
    loaderRow.innerHTML = `
      <div class="chat-ai-avatar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
          <path d="M6 12v5c3 3 9 3 12 0v-5"/>
        </svg>
      </div>
      <div class="chat-bubble-content">
        <div class="chat-loading-row">
          <div class="chat-loading-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span>Reviewing ${this.activeMaterialName ? `<strong>${this.escapeHtml(this.activeMaterialName)}</strong>` : 'active material'}...</span>
        </div>
      </div>
    `;
    container.appendChild(loaderRow);
    container.scrollTop = container.scrollHeight;

    try {
      const res = await LearnMateAPI.sendChatMessage({
        message: text,
        material_id: this.activeMaterialId,
        session_id: this.currentSessionId
      });

      loaderRow.remove();

      const data = res.data || res;
      if (res.status === "success" || data.status === "success") {
        const replyText = data.reply || res.reply || "";
        const botRow = document.createElement("div");
        botRow.className = "chat-message-row assistant";
        botRow.innerHTML = `
          <div class="chat-ai-avatar">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
              <path d="M6 12v5c3 3 9 3 12 0v-5"/>
            </svg>
          </div>
          <div class="chat-bubble-content" style="max-width: 820px; width: 100%;">
            <div class="resource-markdown chat-reply-markdown">${this.renderMarkdown(replyText)}</div>
          </div>
        `;

        if (data.is_quiz && Array.isArray(data.quiz_questions) && data.quiz_questions.length > 0) {
          const quizWrapper = document.createElement("div");
          quizWrapper.className = "chat-embedded-quiz";
          quizWrapper.style.marginTop = "1rem";
          quizWrapper.innerHTML = this.buildQuizRunnerHtml(data.quiz_questions, data.session_id, data.quiz_id);
          botRow.querySelector(".chat-bubble-content").appendChild(quizWrapper);

          this.bindViewerInteractions(quizWrapper, {}, data.quiz_questions, data.session_id, data.quiz_id);

          this.currentQuizId = data.quiz_id;
          if (data.session_id) this.currentSessionId = data.session_id;

          const quizTabPane = document.querySelector('.resource-pane[data-pane="quiz"]');
          if (quizTabPane) {
            quizTabPane.innerHTML = this.buildQuizRunnerHtml(data.quiz_questions, data.session_id, data.quiz_id);
            this.bindViewerInteractions(quizTabPane, {}, data.quiz_questions, data.session_id, data.quiz_id);
          }
          const quizTabBtn = document.querySelector('.resource-tab-btn[data-tab="quiz"] span');
          if (quizTabBtn) {
            quizTabBtn.textContent = `🎯 Adaptive Quiz (${data.quiz_questions.length} Qs)`;
          }

          LearnMateComponents.showToast(`Adaptive Quiz (${data.quiz_questions.length} questions) generated!`, "success");
        }

        container.appendChild(botRow);
        container.scrollTop = container.scrollHeight;
      } else {
        this.renderErrorMessage(res.message || data.message || "Could not answer follow-up question.");
      }
    } catch (err) {
      loaderRow.remove();
      console.error("Chat followup error:", err);
      this.renderErrorMessage("Failed to send chat message to backend.");
    }
  },

  // Display educational loader and request content generation from Flask
  async generateContentForTopic(topic, materialId = null) {
    const container = document.getElementById("chat-messages-stream");
    if (!container) return;

    // Add loader
    const loaderRow = document.createElement("div");
    loaderRow.className = "chat-message-row assistant";
    loaderRow.id = "learning-pack-loader";
    loaderRow.innerHTML = `
      <div class="chat-ai-avatar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
          <path d="M6 12v5c3 3 9 3 12 0v-5"/>
        </svg>
      </div>
      <div class="chat-bubble-content">
        <div class="chat-loading-row">
          <div class="chat-loading-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <span>Generating personalized learning pack for <strong>${this.escapeHtml(topic)}</strong>...</span>
        </div>
      </div>
    `;
    container.appendChild(loaderRow);
    container.scrollTop = container.scrollHeight;

    try {
      const res = await LearnMateAPI.generateContent({
        topic: topic,
        material_id: materialId
      });

      // Remove loader
      loaderRow.remove();

      const data = res.data || res;
      if (res.status === "success" || res.success || data.status === "success") {
        this.currentSessionId = data.session_id || res.session_id;
        this.currentQuizId = data.quiz_id || res.quiz_id;
        if (materialId) {
          this.activeMaterialId = materialId;
        }

        const resources = data.resources || res.resources || {};
        const quizQuestions = data.quiz_questions || res.quiz_questions || [];

        this.renderAssistantPackage(topic, resources, quizQuestions, this.currentSessionId, this.currentQuizId, materialId != null);
        LearnMateComponents.showToast(`Personalized learning pack ready for "${topic}"!`, "success");
      } else {
        this.renderErrorMessage(res.message || data.message || "Could not generate learning resources.");
      }
    } catch (err) {
      loaderRow.remove();
      console.error("Learning generation error:", err);
      this.renderErrorMessage("Network connection error. Please make sure the Flask backend is running.");
    }
  },

  // Load a previously saved learning session from history
  async loadSavedSession(sessionId) {
    const container = document.getElementById("chat-messages-stream");
    if (!container) return;

    // Add loader
    const loaderRow = document.createElement("div");
    loaderRow.className = "chat-message-row assistant";
    loaderRow.innerHTML = `
      <div class="chat-ai-avatar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
      </div>
      <div class="chat-bubble-content">
        <div class="chat-loading-row">
          <div class="chat-loading-dots"><span></span><span></span><span></span></div>
          <span>Restoring learning session #${sessionId} from database...</span>
        </div>
      </div>
    `;
    container.appendChild(loaderRow);
    container.scrollTop = container.scrollHeight;

    try {
      const res = await LearnMateAPI.getLearningSession(sessionId);
      loaderRow.remove();

      const data = res.data || res;
      if (res.status === "success" || res.success || data.status === "success") {
        const session = data.session || res.session || {};
        const topic = session.topic || `Session #${sessionId}`;
        const resources = data.resources || res.resources || {};
        const quizQuestions = data.quiz_questions || res.quiz_questions || [];
        const quizId = data.quiz_id || res.quiz_id;

        this.currentSessionId = sessionId;
        this.currentQuizId = quizId;
        this.activeMaterialId = session.material_id || null;
        this.activeMaterialName = session.material_name || null;

        this.renderAssistantPackage(topic, resources, quizQuestions, sessionId, quizId, session.source_type === "material", true);
        LearnMateComponents.showToast(`Restored session "${topic}"!`, "info");
      } else {
        this.renderErrorMessage(res.message || data.message || "Failed to load session from history.");
      }
    } catch (e) {
      loaderRow.remove();
      console.error(e);
      this.renderErrorMessage("Could not load session from backend database.");
    }
  },

  // Render assistant message row containing the complete 8-in-1 resource viewer
  renderAssistantPackage(topic, resources, quizQuestions, sessionId, quizId, isMaterial = false, isReopened = false) {
    const container = document.getElementById("chat-messages-stream");
    if (!container) return;

    const botRow = document.createElement("div");
    botRow.className = "chat-message-row assistant";

    const introText = isReopened
      ? `Welcome back! I have reloaded your study session for <strong>${this.escapeHtml(topic)}</strong> from your <a href="history.html" style="color: var(--primary); font-weight: 600;">Learning History</a>.`
      : `Here is your complete personalized learning pack for <strong>${this.escapeHtml(topic)}</strong>! 🎓 Based on your learning preferences, I've generated all 8 multi-format resources below:`;

    const viewerId = `viewer-${Date.now()}`;
    const viewerHtml = this.buildResourceViewerHtml(viewerId, topic, resources, quizQuestions, sessionId, quizId, isMaterial);

    botRow.innerHTML = `
      <div class="chat-ai-avatar">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
          <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
          <path d="M6 12v5c3 3 9 3 12 0v-5"/>
        </svg>
      </div>
      <div class="chat-bubble-content" style="width: 100%; max-width: 820px;">
        <p>${introText}</p>
        ${viewerHtml}
      </div>
    `;

    container.appendChild(botRow);
    container.scrollTop = container.scrollHeight;

    // Attach interactive event listeners for tabs, flashcards, Q&A, diagram, and quiz
    const viewerEl = document.getElementById(viewerId);
    if (viewerEl) {
      this.bindViewerInteractions(viewerEl, resources, quizQuestions, sessionId, quizId, topic, isMaterial);
    }
  },

  // Build the complete HTML structure for the 8 resource tabs and panes
  buildResourceViewerHtml(viewerId, topic, resources, quizQuestions, sessionId, quizId, isMaterial) {
    const flashcards = Array.isArray(resources.flashcards) ? resources.flashcards : [];
    const qaList = Array.isArray(resources.questions_answers) ? resources.questions_answers : [];
    const totalQuiz = quizQuestions ? quizQuestions.length : 10;

    return `
      <div class="resource-viewer-card" id="${viewerId}">
        <div class="resource-viewer-header">
          <div class="resource-viewer-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>
            <span>${this.escapeHtml(topic)}</span>
          </div>
          <div class="flex items-center gap-2">
            ${isMaterial ? '<span class="badge badge-purple" style="font-size: 0.725rem;">📄 Material Grounded (RAG)</span>' : '<span class="badge badge-blue" style="font-size: 0.725rem;">✨ AI Generated</span>'}
            <span class="badge badge-success" style="font-size: 0.725rem;">All 8 Formats Ready</span>
          </div>
        </div>

        <!-- 8 Navigation Tabs -->
        <div class="resource-tabs-nav">
          <button type="button" class="resource-tab-btn active" data-tab="notes">
            <span>📝 Notes</span>
          </button>
          <button type="button" class="resource-tab-btn" data-tab="details">
            <span>📖 Detailed</span>
          </button>
          <button type="button" class="resource-tab-btn" data-tab="steps">
            <span>🪜 Step-by-Step</span>
          </button>
          <button type="button" class="resource-tab-btn" data-tab="summary">
            <span>📌 Summary</span>
          </button>
          <button type="button" class="resource-tab-btn" data-tab="flashcards">
            <span>🗂️ Flashcards (${flashcards.length})</span>
          </button>
          <button type="button" class="resource-tab-btn" data-tab="qa">
            <span>❓ Q&A (${qaList.length})</span>
          </button>
          <button type="button" class="resource-tab-btn" data-tab="diagram">
            <span>📊 Visual Learning</span>
          </button>
          <button type="button" class="resource-tab-btn" data-tab="quiz">
            <span>🎯 Adaptive Quiz (${totalQuiz} Qs)</span>
          </button>
        </div>

        <div class="resource-tab-content">
          <!-- 1. Notes Pane -->
          <div class="resource-pane active" data-pane="notes">
            <div class="resource-markdown">${this.renderMarkdown(resources.simplified_notes || "No notes available.")}</div>
          </div>

          <!-- 2. Detailed Explanation Pane -->
          <div class="resource-pane" data-pane="details">
            <div class="resource-markdown">${this.renderMarkdown(resources.detailed_explanation || "No detailed explanation available.")}</div>
          </div>

          <!-- 3. Step-by-Step Pane -->
          <div class="resource-pane" data-pane="steps">
            <div class="resource-markdown">${this.renderMarkdown(resources.step_by_step || "No step-by-step breakdown available.")}</div>
          </div>

          <!-- 4. Summary Pane -->
          <div class="resource-pane" data-pane="summary">
            <div class="resource-markdown">${this.renderMarkdown(resources.summary || "No summary available.")}</div>
          </div>

          <!-- 5. Flashcards Pane -->
          <div class="resource-pane" data-pane="flashcards">
            ${this.buildFlashcardsHtml(flashcards)}
          </div>

          <!-- 6. Questions & Answers Pane -->
          <div class="resource-pane" data-pane="qa">
            ${this.buildQaAccordionHtml(qaList)}
          </div>

          <!-- 7. Visual Learning Pane -->
          <div class="resource-pane" data-pane="diagram">
            <div class="visual-learning-container" id="${viewerId}-visual-learning">
              <!-- Visual Learning Toolbar -->
              <div class="visual-learning-toolbar">
                <div class="visual-learning-tabs">
                  <button type="button" class="vl-subtab-btn active" data-vl-tab="ai-generated">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v4m0 12v4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M2 12h4m12 0h4M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/></svg>
                    <span>AI Generated</span>
                  </button>
                  <button type="button" class="vl-subtab-btn" data-vl-tab="reference-diagrams">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
                    <span>Reference Diagrams</span>
                  </button>
                </div>

                <div class="vl-controls" id="${viewerId}-vl-controls">
                  <label for="${viewerId}-diag-type-select" class="vl-control-label">Diagram Type:</label>
                  <select class="vl-type-select" id="${viewerId}-diag-type-select">
                    <option value="auto">Auto (Dynamic)</option>
                    <option value="flowchart">Flowchart</option>
                    <option value="concept_map">Concept Map</option>
                    <option value="hierarchy">Hierarchy / Classification</option>
                    <option value="architecture">Architecture / Block Diagram</option>
                    <option value="comparison">Comparison Diagram</option>
                    <option value="relationship">Relationship Diagram</option>
                    <option value="process">Process Diagram</option>
                  </select>
                </div>
              </div>

              <!-- Concept Selector Strip (Interactive Student Concept Chips) -->
              <div class="vl-concept-strip" id="${viewerId}-concept-strip">
                <div class="vl-concept-strip-label">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>
                  <span>Important Concepts:</span>
                </div>
                <div class="vl-concept-chips-container" id="${viewerId}-concept-chips">
                  <!-- Injected concept chips -->
                </div>
              </div>

              <!-- Sub-pane 1: AI Generated Diagrams -->
              <div class="vl-subpane active" data-vl-pane="ai-generated">
                <div class="vl-ungrounded-banner" id="${viewerId}-ungrounded-banner" style="display: none;">
                  <span class="vl-alert-icon">⚠️</span>
                  <span class="vl-alert-text">Not enough information in the current material to generate a grounded diagram.</span>
                </div>

                <div class="vl-diagram-meta" id="${viewerId}-diagram-meta">
                  <div class="vl-diagram-title-row">
                    <span class="vl-type-badge badge badge-purple" id="${viewerId}-type-badge">Diagram</span>
                    <h4 class="vl-diagram-title" id="${viewerId}-diag-title">Visual Architecture</h4>
                  </div>
                  <p class="vl-diagram-desc" id="${viewerId}-diag-desc"></p>
                </div>

                <div class="diagram-render-box" id="${viewerId}-diagram-box">
                  <div class="flex items-center gap-2" style="color: var(--text-muted); font-size: 0.85rem;">
                    <div class="chat-loading-dots"><span></span><span></span><span></span></div>
                    <span>Initializing Visual Learning...</span>
                  </div>
                </div>
              </div>

              <!-- Sub-pane 2: Reference Diagrams -->
              <div class="vl-subpane" data-vl-pane="reference-diagrams" style="display: none;">
                <div class="vl-ref-header">
                  <div class="flex items-center gap-2" style="flex-wrap: wrap;">
                    <span class="badge badge-purple" style="font-size: 0.725rem;">Reference Diagrams</span>
                    <span class="badge badge-outline" style="font-size: 0.725rem;">Open Educational Repositories</span>
                    <span style="font-size: 0.8rem; color: var(--text-secondary);">Curated diagrams strictly verified against the selected concept (Wikimedia Commons & Wikipedia)</span>
                  </div>
                </div>
                <div class="vl-reference-grid" id="${viewerId}-reference-grid">
                  <!-- Injected reference diagram cards -->
                </div>
              </div>
            </div>
          </div>

          <!-- 8. Adaptive Quiz Pane -->
          <div class="resource-pane" data-pane="quiz">
            ${this.buildQuizRunnerHtml(quizQuestions, sessionId, quizId)}
          </div>
        </div>
      </div>
    `;
  },

  // Build Interactive 3D Flashcard HTML
  buildFlashcardsHtml(flashcards) {
    if (!flashcards || flashcards.length === 0) {
      return `<p style="color: var(--text-muted); text-align: center; padding: 2rem;">No flashcards available for this topic.</p>`;
    }

    const firstCard = flashcards[0];
    return `
      <div class="flashcard-wrapper">
        <div class="flashcard-card-3d" id="fc-card" title="Click anywhere on the card to flip">
          <div class="flashcard-inner">
            <div class="flashcard-front">
              <div class="flex items-center justify-between" style="font-size: 0.8rem; color: var(--text-muted);">
                <span class="badge badge-purple">Question / Term</span>
                <span class="fc-counter">Card 1 of ${flashcards.length}</span>
              </div>
              <div class="flashcard-text" id="fc-front-text">${this.escapeHtml(firstCard.question || "Term")}</div>
              <div class="flashcard-hint">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><line x1="3" y1="3" x2="3" y2="8"/><line x1="8" y1="8" x2="3" y2="8"/></svg>
                <span>Click to reveal answer</span>
              </div>
            </div>
            <div class="flashcard-back">
              <div class="flex items-center justify-between" style="font-size: 0.8rem; color: var(--text-muted);">
                <span class="badge badge-success">Definition / Answer</span>
                <span class="fc-counter">Card 1 of ${flashcards.length}</span>
              </div>
              <div class="flashcard-text" id="fc-back-text">${this.escapeHtml(firstCard.answer || "Answer")}</div>
              <div class="flashcard-hint">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/></svg>
                <span>Click to flip back</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Controls -->
        <div class="flashcard-controls">
          <button type="button" class="btn btn-outline btn-sm" id="btn-fc-prev">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
            Previous
          </button>
          <button type="button" class="btn btn-secondary btn-sm" id="btn-fc-flip">
            Flip Card
          </button>
          <button type="button" class="btn btn-outline btn-sm" id="btn-fc-next">
            Next
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
          </button>
        </div>
      </div>
    `;
  },

  // Build Q&A Accordion HTML
  buildQaAccordionHtml(qaList) {
    if (!qaList || qaList.length === 0) {
      return `<p style="color: var(--text-muted); text-align: center; padding: 2rem;">No questions available.</p>`;
    }

    return `
      <div class="qa-accordion-container">
        ${qaList.map((item, idx) => `
          <div class="qa-item ${idx === 0 ? 'open' : ''}">
            <div class="qa-question-header">
              <span>${idx + 1}. ${this.escapeHtml(item.question)}</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
            <div class="qa-answer-body">
              ${this.escapeHtml(item.answer)}
            </div>
          </div>
        `).join("")}
      </div>
    `;
  },

  // Build Interactive 10-MCQ Adaptive Quiz Runner HTML
  buildQuizRunnerHtml(quizQuestions, sessionId, quizId) {
    if (!quizQuestions || quizQuestions.length === 0) {
      return `<p style="color: var(--text-muted); text-align: center; padding: 2rem;">No quiz questions available.</p>`;
    }

    return `
      <div class="quiz-runner-container">
        <div id="quiz-results-banner-slot"></div>

        ${quizQuestions.map((q, idx) => `
          <div class="quiz-runner-card" data-qid="${q.id}">
            <div class="quiz-question-header">
              <span class="quiz-q-num">Q${idx + 1}</span>
              <div class="quiz-q-text">${this.escapeHtml(q.question)}</div>
            </div>

            <div class="quiz-options-list">
              <label class="quiz-option-item" data-opt="A">
                <input type="radio" name="q_${q.id}" value="A" style="accent-color: var(--primary);">
                <span>A) ${this.escapeHtml(q.option_a)}</span>
              </label>
              <label class="quiz-option-item" data-opt="B">
                <input type="radio" name="q_${q.id}" value="B" style="accent-color: var(--primary);">
                <span>B) ${this.escapeHtml(q.option_b)}</span>
              </label>
              <label class="quiz-option-item" data-opt="C">
                <input type="radio" name="q_${q.id}" value="C" style="accent-color: var(--primary);">
                <span>C) ${this.escapeHtml(q.option_c)}</span>
              </label>
              <label class="quiz-option-item" data-opt="D">
                <input type="radio" name="q_${q.id}" value="D" style="accent-color: var(--primary);">
                <span>D) ${this.escapeHtml(q.option_d)}</span>
              </label>
            </div>

            <div class="quiz-feedback-box" style="display: none;">
              <strong>Explanation:</strong> ${this.escapeHtml(q.explanation || "Correct answer explanation.")}
            </div>
          </div>
        `).join("")}

        <div style="display: flex; justify-content: flex-end; padding: 1rem 0;">
          <button type="button" class="btn btn-primary btn-submit-adaptive-quiz" style="padding: 0.75rem 1.75rem; font-size: 0.95rem;">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><polyline points="20 6 9 17 4 12"/></svg>
            Submit Quiz & Record Score
          </button>
        </div>
      </div>
    `;
  },

  // Attach tab switching, flashcard flipping, Q&A toggles, diagram rendering, and quiz grading
  bindViewerInteractions(viewerEl, resources, quizQuestions, sessionId, quizId, topic, isMaterial) {
    // 1. Tab switching
    const tabBtns = viewerEl.querySelectorAll(".resource-tab-btn");
    const panes = viewerEl.querySelectorAll(".resource-pane");

    tabBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        const tabKey = btn.dataset.tab;
        tabBtns.forEach(b => b.classList.remove("active"));
        panes.forEach(p => p.classList.remove("active"));

        btn.classList.add("active");
        const targetPane = viewerEl.querySelector(`.resource-pane[data-pane="${tabKey}"]`);
        if (targetPane) targetPane.classList.add("active");

        // If visual learning diagram tab is clicked, trigger render
        if (tabKey === "diagram") {
          this.renderVisualLearning(viewerEl, resources.diagrams, topic, this.activeMaterialId);
        }
      });
    });

    // 2. Flashcard interactions
    const flashcards = Array.isArray(resources.flashcards) ? resources.flashcards : [];
    if (flashcards.length > 0) {
      let currentIndex = 0;
      const cardEl = viewerEl.querySelector("#fc-card");
      const frontText = viewerEl.querySelector("#fc-front-text");
      const backText = viewerEl.querySelector("#fc-back-text");
      const counters = viewerEl.querySelectorAll(".fc-counter");
      const prevBtn = viewerEl.querySelector("#btn-fc-prev");
      const nextBtn = viewerEl.querySelector("#btn-fc-next");
      const flipBtn = viewerEl.querySelector("#btn-fc-flip");

      const updateCard = () => {
        if (cardEl) cardEl.classList.remove("flipped");
        setTimeout(() => {
          if (frontText) frontText.textContent = flashcards[currentIndex].question || "";
          if (backText) backText.textContent = flashcards[currentIndex].answer || "";
          counters.forEach(c => c.textContent = `Card ${currentIndex + 1} of ${flashcards.length}`);
        }, 150);
      };

      if (cardEl) {
        cardEl.addEventListener("click", () => cardEl.classList.toggle("flipped"));
      }
      if (flipBtn && cardEl) {
        flipBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          cardEl.classList.toggle("flipped");
        });
      }
      if (prevBtn) {
        prevBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          if (currentIndex > 0) {
            currentIndex--;
            updateCard();
          }
        });
      }
      if (nextBtn) {
        nextBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          if (currentIndex < flashcards.length - 1) {
            currentIndex++;
            updateCard();
          }
        });
      }
    }

    // 3. Q&A Accordion interactions
    viewerEl.querySelectorAll(".qa-question-header").forEach(hdr => {
      hdr.addEventListener("click", () => {
        const item = hdr.closest(".qa-item");
        if (item) item.classList.toggle("open");
      });
    });

    // 4. Visual Learning diagram lazy render on initial display
    this.renderVisualLearning(viewerEl, resources.diagrams, topic, this.activeMaterialId);

    // 5. Quiz radio interactions and submission
    viewerEl.querySelectorAll(".quiz-option-item").forEach(item => {
      item.addEventListener("click", () => {
        const radio = item.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
          const parentCard = item.closest(".quiz-runner-card");
          if (parentCard) {
            parentCard.querySelectorAll(".quiz-option-item").forEach(opt => opt.classList.remove("selected"));
            item.classList.add("selected");
          }
        }
      });
    });

    const submitQuizBtn = viewerEl.querySelector(".btn-submit-adaptive-quiz");
    if (submitQuizBtn) {
      submitQuizBtn.addEventListener("click", async () => {
        // Collect answers
        const answers = {};
        const qCards = viewerEl.querySelectorAll(".quiz-runner-card");
        let answeredCount = 0;

        qCards.forEach(card => {
          const qid = card.dataset.qid;
          const selected = card.querySelector('input[type="radio"]:checked');
          if (selected) {
            answers[qid] = selected.value;
            answeredCount++;
          }
        });

        if (answeredCount < qCards.length) {
          if (!confirm(`You have answered ${answeredCount} of ${qCards.length} questions. Submit anyway?`)) {
            return;
          }
        }

        submitQuizBtn.disabled = true;
        submitQuizBtn.innerHTML = `
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
          Grading Quiz...
        `;

        try {
          const evalRes = await LearnMateAPI.submitQuizAnswers(sessionId, answers, quizId);
          const evalData = evalRes.data || evalRes;
          if (evalRes.status === "success" || evalRes.success || evalData.status === "success") {
            const score = evalData.score != null ? evalData.score : (evalRes.score != null ? evalRes.score : 80);
            const correctCount = evalData.correct_count != null ? evalData.correct_count : (evalRes.correct_count != null ? evalRes.correct_count : answeredCount);
            const total = evalData.total_questions || evalRes.total_questions || qCards.length;
            const level = evalData.performance_level || evalRes.performance_level || (score >= 80 ? "Mastery" : score >= 60 ? "Proficient" : "Developing");
            const results = evalData.results || evalRes.results || [];

            // Display Score Banner
            const bannerSlot = viewerEl.querySelector("#quiz-results-banner-slot");
            if (bannerSlot) {
              bannerSlot.innerHTML = `
                <div class="quiz-score-banner">
                  <div>
                    <div style="font-size: 0.825rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase;">Performance Analytics</div>
                    <div style="font-size: 1.6rem; font-weight: 800; color: var(--primary); margin: 0.2rem 0;">
                      Score: ${score.toFixed(0)}%
                    </div>
                    <div style="font-size: 0.875rem; color: var(--text-secondary);">
                      You answered <strong>${correctCount}</strong> out of <strong>${total}</strong> questions correctly.
                    </div>
                  </div>
                  <div style="text-align: right;">
                    <span class="badge ${score >= 80 ? 'badge-success' : score >= 60 ? 'badge-blue' : 'badge-warning'}" style="font-size: 0.95rem; padding: 0.5rem 1rem;">
                      Level: ${this.escapeHtml(level)}
                    </span>
                    <div style="margin-top: 0.45rem;">
                      <a href="performance.html" class="btn btn-outline btn-sm">View Analytics</a>
                    </div>
                  </div>
                </div>
              `;
            }

            // Highlight answers on each card
            results.forEach(res => {
              const card = viewerEl.querySelector(`.quiz-runner-card[data-qid="${res.question_id}"]`);
              if (card) {
                const optItems = card.querySelectorAll(".quiz-option-item");
                optItems.forEach(opt => {
                  const optVal = opt.dataset.opt;
                  if (optVal === res.correct_answer) {
                    opt.classList.add("result-correct");
                  } else if (optVal === res.student_answer && res.student_answer !== res.correct_answer) {
                    opt.classList.add("result-incorrect");
                  }
                });

                // Show feedback
                const feedback = card.querySelector(".quiz-feedback-box");
                if (feedback) feedback.style.display = "block";
              }
            });

            submitQuizBtn.style.display = "none";
            LearnMateComponents.showToast(`Quiz completed! Score: ${score.toFixed(0)}% recorded to database.`, "success");
          } else {
            submitQuizBtn.disabled = false;
            submitQuizBtn.textContent = "Retry Submit";
            LearnMateComponents.showToast(evalRes.message || "Could not grade quiz.", "danger");
          }
        } catch (e) {
          console.error(e);
          submitQuizBtn.disabled = false;
          submitQuizBtn.textContent = "Submit Quiz";
          LearnMateComponents.showToast("Network error submitting quiz.", "danger");
        }
      });
    }
  },

  // -------------------------------------------------------------
  // Visual Learning & Dynamic Multi-Format Diagram Engine
  // -------------------------------------------------------------

  // Normalize raw diagrams (bundle object, JSON string, or legacy mermaid code)
  normalizeDiagramBundle(rawDiagrams, topic) {
    if (!rawDiagrams) {
      return this.createFallbackBundle(topic, "flowchart");
    }

    if (typeof rawDiagrams === "string") {
      try {
        const parsed = JSON.parse(rawDiagrams);
        if (parsed && typeof parsed === "object" && (parsed.all_diagram_types || parsed.diagram_type || parsed.concepts)) {
          return this.enrichDiagramBundle(parsed, topic);
        }
      } catch (e) {
        // Not a JSON string, likely legacy raw mermaid code
      }

      const t = topic || "Study Concept";
      return this.enrichDiagramBundle({
        diagram_type: "flowchart",
        selected_type: "flowchart",
        auto_selected_type: "flowchart",
        title: `${t} Flowchart`,
        description: "Sequential execution logic flow.",
        active_diagram: {
          title: `${t} Flowchart`,
          description: "Sequential execution logic flow.",
          mermaid_code: rawDiagrams
        },
        all_diagram_types: {
          flowchart: {
            title: `${t} Flowchart`,
            description: "Sequential execution logic flow.",
            mermaid_code: rawDiagrams
          }
        },
        reference_diagrams: []
      }, topic);
    }

    if (typeof rawDiagrams === "object") {
      return this.enrichDiagramBundle(rawDiagrams, topic);
    }

    return this.createFallbackBundle(topic, "flowchart");
  },

  enrichDiagramBundle(bundle, topic) {
    const t = topic || "Study Concept";
    if (!bundle.all_diagram_types) bundle.all_diagram_types = {};
    if (!bundle.all_concept_diagrams) bundle.all_concept_diagrams = {};
    if (!bundle.reference_diagrams) bundle.reference_diagrams = [];

    if (!bundle.concepts || bundle.concepts.length === 0) {
      bundle.concepts = this.generateClientFallbackConcepts(topic);
    }

    if (!bundle.selected_concept && bundle.concepts.length > 0) {
      bundle.selected_concept = bundle.concepts[0].id;
      bundle.selected_concept_name = bundle.concepts[0].name;
    }

    return bundle;
  },

  generateClientFallbackConcepts(topic) {
    const t = topic || "Study Topic";
    const low = t.toLowerCase();
    if (low.includes("design pattern") || low.includes("ooadp")) {
      return [
        { id: "creational_patterns", name: "Creational Design Patterns", diagram_type: "hierarchy", description: "Taxonomy of Factory, Singleton, Builder, Prototype." },
        { id: "factory_method", name: "Factory Method Pattern", diagram_type: "process", description: "Object creation pipeline via Creator and Concrete Product." },
        { id: "observer_pattern", name: "Observer Pattern", diagram_type: "relationship", description: "Subject-Observer state synchronization network." },
        { id: "singleton_pattern", name: "Singleton Pattern", diagram_type: "flowchart", description: "Single instance verification and mutex locking." },
        { id: "design_patterns_overview", name: "Core Design Principles", diagram_type: "concept_map", description: "GoF architectural principles and pillars." }
      ];
    }
    if (low.includes("8086") || low.includes("instruction set") || low.includes("mpi")) {
      return [
        { id: "arch_8086", name: "8086 CPU Architecture", diagram_type: "architecture", description: "BIU, EU, register sets, and 20-bit system bus." },
        { id: "instruction_taxonomy", name: "Instruction Classification", diagram_type: "hierarchy", description: "Data Transfer, Arithmetic, Logic, String, Branch." },
        { id: "data_transfer_flow", name: "Data Transfer (MOV, PUSH, POP)", diagram_type: "flowchart", description: "Stack pointer SP adjustment and register transfer." },
        { id: "flag_register_effects", name: "Flag Register Status Effects", diagram_type: "relationship", description: "ALU operation modifications to status flags." },
        { id: "instruction_pipeline", name: "Instruction Fetch & Execution Cycle", diagram_type: "process", description: "Prefetch queue, decode, execute, write-back." }
      ];
    }
    if (low.includes("random forest") || low.includes("regression") || low.includes("ba-02")) {
      return [
        { id: "rf_architecture", name: "Random Forest Architecture", diagram_type: "architecture", description: "Ensemble architecture coordinating trees and aggregator." },
        { id: "tree_splitting", name: "Decision Tree Node Splitting", diagram_type: "flowchart", description: "Variance reduction and optimal split search." },
        { id: "bagging_pipeline", name: "Bagging & Bootstrap Training", diagram_type: "process", description: "Bootstrap resampling, parallel fitting, averaging." },
        { id: "rf_vs_decision_tree", name: "Random Forest vs Single Tree", diagram_type: "comparison", description: "Variance vs bias trade-off matrix." },
        { id: "rf_concept_map", name: "Ensemble Learning Foundations", diagram_type: "concept_map", description: "Ensemble regression principles." }
      ];
    }
    if (low.includes("normalization") || low.includes("normal form")) {
      return [
        { id: "functional_dependencies", name: "Functional Dependencies & Keys", diagram_type: "relationship", description: "Determinants, candidate keys, and dependencies." },
        { id: "normal_forms_hierarchy", name: "Normal Forms Evolution (1NF to BCNF)", diagram_type: "hierarchy", description: "Cumulative normalization constraints." },
        { id: "normalization_comparison", name: "Normal Forms Comparison Matrix", diagram_type: "comparison", description: "Trade-offs across anomalies, redundancy, joins." },
        { id: "decomposition_process", name: "Lossless Decomposition Process", diagram_type: "flowchart", description: "Dependency preservation verification." },
        { id: "normalization_concept_map", name: "Normalization Core Principles", diagram_type: "concept_map", description: "Relational schema integrity principles." }
      ];
    }
    return [
      { id: "core_overview", name: `${t} Architecture`, diagram_type: "architecture", description: `Structural framework of ${t}.` },
      { id: "structural_taxonomy", name: `${t} Taxonomy`, diagram_type: "hierarchy", description: `Classification of subtypes in ${t}.` },
      { id: "execution_process", name: `${t} Execution Flow`, diagram_type: "flowchart", description: `Step-by-step logic flow.` },
      { id: "component_relations", name: `${t} Relationships`, diagram_type: "relationship", description: `Component interactions and associations.` }
    ];
  },

  getDiagramTypeIcon(type) {
    switch (type) {
      case "architecture": return "🏗️";
      case "hierarchy": return "🌳";
      case "flowchart": return "🔀";
      case "relationship": return "🔗";
      case "comparison": return "⚖️";
      case "process": return "🔄";
      case "concept_map":
      default: return "🗺️";
    }
  },

  createFallbackBundle(topic, defaultType = "flowchart") {
    const t = topic || "Learning Concept";
    const concepts = this.generateClientFallbackConcepts(topic);
    return {
      concepts: concepts,
      selected_concept: concepts[0]?.id || "overview",
      selected_concept_name: concepts[0]?.name || t,
      diagram_type: defaultType,
      selected_type: defaultType,
      auto_selected_type: defaultType,
      title: `${t} Visual Model`,
      description: "Dynamic visual representation of topic concepts.",
      all_diagram_types: {},
      all_concept_diagrams: {},
      reference_diagrams: [],
      grounded: true,
      grounding_message: ""
    };
  },

  formatDiagramType(type) {
    switch (type) {
      case "flowchart": return "Flowchart";
      case "concept_map": return "Concept Map";
      case "hierarchy": return "Hierarchy / Classification";
      case "architecture": return "Architecture / Block Diagram";
      case "comparison": return "Comparison Diagram";
      case "relationship": return "Relationship Diagram";
      case "process": return "Process Diagram";
      default: return type ? type.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()) : "Visual Diagram";
    }
  },

  // Main coordinator for Visual Learning section (AI Generated & Reference tabs, Concept Selector, Type select, Renderers)
  renderVisualLearning(viewerEl, rawDiagrams, topic, materialId) {
    const bundle = this.normalizeDiagramBundle(rawDiagrams, topic);
    const container = viewerEl.querySelector(".visual-learning-container");
    if (!container) return;

    const subtabBtns = container.querySelectorAll(".vl-subtab-btn");
    const subpanes = container.querySelectorAll(".vl-subpane");
    const typeSelect = container.querySelector(".vl-type-select");
    const diagBox = container.querySelector(".diagram-render-box");
    const refGrid = container.querySelector(".vl-reference-grid");
    const controls = container.querySelector(".vl-controls");
    const chipsContainer = container.querySelector(".vl-concept-chips-container");
    const ungroundedBanner = container.querySelector(".vl-ungrounded-banner");

    // Helper to refresh grounding alert
    const updateGroundingAlert = (diagramObj) => {
      if (ungroundedBanner) {
        if (diagramObj && diagramObj.grounded === false) {
          ungroundedBanner.style.display = "flex";
          const txtEl = ungroundedBanner.querySelector(".vl-alert-text");
          if (txtEl) txtEl.textContent = diagramObj.grounding_message || "Not enough information in the current material to generate a grounded diagram.";
        } else {
          ungroundedBanner.style.display = "none";
        }
      }
    };

    // Render interactive concept chips
    const renderConceptChips = () => {
      if (!chipsContainer || !bundle.concepts || bundle.concepts.length === 0) return;
      chipsContainer.innerHTML = bundle.concepts.map(c => {
        const isAct = (bundle.selected_concept === c.id) ? "active" : "";
        const icon = this.getDiagramTypeIcon(c.diagram_type);
        const typeLabel = this.formatDiagramType(c.diagram_type);
        return `
          <button type="button" class="vl-concept-chip ${isAct}" data-concept-id="${c.id}" data-diagram-type="${c.diagram_type}" title="${this.escapeHtml(c.description || c.name)}">
            <span>${icon}</span>
            <span>${this.escapeHtml(c.name)}</span>
            <span class="vl-chip-type-tag">${typeLabel}</span>
          </button>
        `;
      }).join("");

      // Bind chip click events
      chipsContainer.querySelectorAll(".vl-concept-chip").forEach(chip => {
        chip.addEventListener("click", async () => {
          const cId = chip.dataset.conceptId;
          const cType = chip.dataset.diagramType;
          if (bundle.selected_concept === cId && bundle.selected_type === cType && bundle.active_diagram) return;

          chipsContainer.querySelectorAll(".vl-concept-chip").forEach(ch => ch.classList.remove("active"));
          chip.classList.add("active");

          bundle.selected_concept = cId;
          const targetConcept = bundle.concepts.find(x => x.id === cId) || { id: cId, name: chip.innerText.trim(), diagram_type: cType };
          bundle.selected_concept_name = targetConcept.name;
          bundle.selected_type = cType;

          if (typeSelect) typeSelect.value = cType;

          // Check if diagram is already cached
          let diagData = bundle.all_concept_diagrams?.[cId];
          if (!diagData) {
            diagBox.innerHTML = `
              <div class="vl-loading-box">
                <div class="chat-loading-dots"><span></span><span></span><span></span></div>
                <p style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.5rem;">Generating ${this.escapeHtml(targetConcept.name)}...</p>
              </div>
            `;
            try {
              const resp = await LearnMateAPI.generateDiagram({
                topic: topic,
                concept: targetConcept.name,
                diagram_type: cType,
                material_id: materialId || null
              });
              if (resp.status === "success" && resp.diagram_bundle) {
                const newB = resp.diagram_bundle;
                if (!bundle.all_concept_diagrams) bundle.all_concept_diagrams = {};
                bundle.all_concept_diagrams = { ...bundle.all_concept_diagrams, ...newB.all_concept_diagrams };
                diagData = newB.active_diagram || bundle.all_concept_diagrams[cId];
                if (newB.reference_diagrams) {
                  bundle.reference_diagrams = newB.reference_diagrams;
                }
              }
            } catch (err) {
              console.warn("Concept diagram fetch error:", err);
            }
          }

          bundle.active_diagram = diagData || {};
          updateGroundingAlert(bundle.active_diagram);
          this.updateDiagramMeta(container, cType, bundle);
          await this.renderDiagramByType(diagBox, cType, bundle.active_diagram, topic);

          // Update reference diagrams for this concept
          try {
            const refResp = await LearnMateAPI.getDiagramReferences(topic, targetConcept.name, cType);
            if (refResp && refResp.status === "success") {
              bundle.reference_diagrams = refResp.reference_diagrams || [];
              this.renderReferenceDiagrams(refGrid, bundle.reference_diagrams, topic, targetConcept.name);
            }
          } catch (e) {
            console.warn("Reference diagrams fetch failed:", e);
          }
        });
      });
    };

    renderConceptChips();

    // 1. Sub-tab switching [ AI Generated ] vs [ Reference Diagrams ]
    if (!container.dataset.vlBound) {
      container.dataset.vlBound = "true";

      subtabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
          const tab = btn.dataset.vlTab;
          subtabBtns.forEach(b => b.classList.remove("active"));
          subpanes.forEach(p => {
            if (p.dataset.vlPane === tab) {
              p.style.display = "block";
              p.classList.add("active");
            } else {
              p.style.display = "none";
              p.classList.remove("active");
            }
          });
          btn.classList.add("active");

          if (tab === "ai-generated") {
            if (controls) controls.style.display = "flex";
          } else if (tab === "reference-diagrams") {
            if (controls) controls.style.display = "none";
            this.renderReferenceDiagrams(refGrid, bundle.reference_diagrams, topic, bundle.selected_concept_name || topic);
          }
        });
      });

      // 2. Diagram type selector change event
      if (typeSelect) {
        typeSelect.addEventListener("change", async (e) => {
          const val = e.target.value;
          const targetType = val === "auto" ? (bundle.auto_selected_type || "flowchart") : val;

          bundle.selected_type = targetType;
          this.updateDiagramMeta(container, targetType, bundle);

          if (bundle.all_diagram_types && bundle.all_diagram_types[targetType]) {
            bundle.active_diagram = bundle.all_diagram_types[targetType];
            updateGroundingAlert(bundle.active_diagram);
            await this.renderDiagramByType(diagBox, targetType, bundle.active_diagram, topic);
          } else {
            diagBox.innerHTML = `
              <div class="vl-loading-box">
                <div class="chat-loading-dots"><span></span><span></span><span></span></div>
                <p style="font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.5rem;">Generating ${this.formatDiagramType(targetType)}...</p>
              </div>
            `;
            try {
              const resp = await LearnMateAPI.generateDiagram({
                topic: topic,
                concept: bundle.selected_concept_name || topic,
                diagram_type: targetType,
                material_id: materialId || null
              });
              if (resp.status === "success" && resp.diagram_bundle) {
                const newB = resp.diagram_bundle;
                bundle.all_diagram_types = { ...bundle.all_diagram_types, ...newB.all_diagram_types };
                bundle.active_diagram = newB.active_diagram || bundle.all_diagram_types[targetType];
                updateGroundingAlert(bundle.active_diagram);
                await this.renderDiagramByType(diagBox, targetType, bundle.active_diagram, topic);
              } else {
                await this.renderDiagramByType(diagBox, targetType, bundle.all_diagram_types?.[targetType] || {}, topic);
              }
            } catch (err) {
              console.warn("Diagram generation failed, falling back:", err);
              await this.renderDiagramByType(diagBox, targetType, bundle.all_diagram_types?.[targetType] || {}, topic);
            }
          }
        });
      }
    }

    // Determine initial diagram type (auto selected or saved)
    const initialType = bundle.selected_type || bundle.diagram_type || bundle.auto_selected_type || "flowchart";
    if (typeSelect && !typeSelect.dataset.userSelected) {
      typeSelect.value = bundle.auto_selected_type ? "auto" : initialType;
    }

    this.updateDiagramMeta(container, initialType, bundle);

    // Initial render of AI diagram
    const activeData = bundle.active_diagram || (bundle.all_concept_diagrams && bundle.all_concept_diagrams[bundle.selected_concept]) || (bundle.all_diagram_types && bundle.all_diagram_types[initialType]) || {};
    updateGroundingAlert(activeData);
    this.renderDiagramByType(diagBox, initialType, activeData, topic);

    // Also populate Reference Diagrams
    this.renderReferenceDiagrams(refGrid, bundle.reference_diagrams, topic, bundle.selected_concept_name || topic);
  },

  updateDiagramMeta(container, type, bundle) {
    const typeBadge = container.querySelector(".vl-type-badge");
    const titleEl = container.querySelector(".vl-diagram-title");
    const descEl = container.querySelector(".vl-diagram-desc");

    const activeObj = bundle.all_diagram_types?.[type] || bundle.active_diagram || {};
    const typeName = this.formatDiagramType(type);

    if (typeBadge) {
      typeBadge.textContent = typeName;
    }
    if (titleEl) {
      titleEl.textContent = activeObj.title || `${bundle.title || "Visual Learning"} - ${typeName}`;
    }
    if (descEl) {
      descEl.textContent = activeObj.description || bundle.description || `Dynamic visual model depicting structured relationships and principles.`;
    }
  },

  // Render diagram layout matching the specific semantic type (distinct visual design for each!)
  async renderDiagramByType(box, type, data, topic) {
    if (!box) return;
    box.innerHTML = "";

    switch (type) {
      case "concept_map":
        this.renderConceptMap(box, data, topic);
        break;
      case "hierarchy":
        this.renderHierarchy(box, data, topic);
        break;
      case "architecture":
        this.renderArchitecture(box, data, topic);
        break;
      case "comparison":
        this.renderComparison(box, data, topic);
        break;
      case "relationship":
        this.renderRelationship(box, data, topic);
        break;
      case "process":
        this.renderProcess(box, data, topic);
        break;
      case "flowchart":
      default:
        await this.renderFlowchart(box, data, topic);
        break;
    }
  },

  // 1. Flowchart Renderer (Process steps, branches, decisions, start/end)
  async renderFlowchart(box, data, topic) {
    const code = data?.mermaid_code || `flowchart TD\n  START([Start: ${this.escapeHtml(topic)}]) --> STEP1[Examine Concepts] --> DEC{Parameters Valid?} -->|Yes| STEP2[Process Execution] --> END([Verified Complete])\n  DEC -->|No| ERR[Revise Parameters] --> STEP1`;

    if (typeof mermaid === "undefined") {
      box.innerHTML = `
        <div class="flowchart-fallback-canvas">
          <div class="fc-flow-node fc-node-start">Start: ${this.escapeHtml(topic)}</div>
          <div class="fc-flow-arrow">↓</div>
          <div class="fc-flow-node fc-node-step">${this.escapeHtml(data?.nodes?.[1]?.label || "Core Execution Step")}</div>
          <div class="fc-flow-arrow">↓</div>
          <div class="fc-flow-node fc-node-dec">◇ ${this.escapeHtml(data?.nodes?.[2]?.label || "Parameters Valid?")}</div>
          <div class="fc-flow-arrow">↓</div>
          <div class="fc-flow-node fc-node-end">Verified Result</div>
        </div>
      `;
      return;
    }

    try {
      this.mermaidCounter++;
      const svgId = `mermaid-flowchart-${this.mermaidCounter}`;
      const cleanCode = code.trim().replace(/^```(?:mermaid)?/i, '').replace(/```$/, '').trim();
      const { svg } = await mermaid.render(svgId, cleanCode);
      box.innerHTML = `<div class="mermaid-svg-wrapper">${svg}</div>`;
    } catch (e) {
      console.warn("Flowchart mermaid render warning:", e);
      box.innerHTML = `
        <div class="flowchart-fallback-canvas">
          <div class="fc-flow-node fc-node-start">Start: ${this.escapeHtml(topic)}</div>
          <div class="fc-flow-arrow">↓</div>
          <div class="fc-flow-node fc-node-step">${this.escapeHtml(data?.nodes?.[1]?.label || "Processing Routine")}</div>
          <div class="fc-flow-arrow">↓</div>
          <div class="fc-flow-node fc-node-dec">◇ Decision & Verification</div>
          <div class="fc-flow-arrow">↓</div>
          <div class="fc-flow-node fc-node-end">Result Complete</div>
        </div>
      `;
    }
  },

  // 2. Concept Map Renderer (Central Hub with radiating conceptual clusters and labeled links)
  renderConceptMap(box, data, topic) {
    const central = data?.central_concept || topic || "Central Core Concept";
    const clusters = data?.clusters || [
      { cluster_name: "Theoretical Foundations", concepts: ["Governing Rules", "Mathematical Basis", "Core Axioms"] },
      { cluster_name: "Functional Operations", concepts: ["Processing Pipeline", "State Transitions", "Transformations"] },
      { cluster_name: "System Constraints", concepts: ["Validation Bounds", "Edge Case Handling", "Performance Limits"] }
    ];

    const clustersHtml = clusters.map((c, i) => `
      <div class="cm-cluster-card cm-cluster-${(i % 3) + 1}">
        <div class="cm-cluster-header">
          <span class="cm-cluster-dot"></span>
          <h5>${this.escapeHtml(c.cluster_name)}</h5>
        </div>
        <div class="cm-concepts-grid">
          ${(c.concepts || []).map(item => `
            <div class="cm-concept-pill">
              <span class="cm-pill-icon">✦</span>
              <span>${this.escapeHtml(item)}</span>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');

    box.innerHTML = `
      <div class="concept-map-canvas">
        <div class="cm-hub-row">
          <div class="cm-central-hub">
            <div class="cm-hub-badge">Core Concept</div>
            <h3 class="cm-hub-title">🌟 ${this.escapeHtml(central)}</h3>
            <div class="cm-radial-radiance"></div>
          </div>
        </div>
        <div class="cm-connectors-row">
          <div class="cm-spoke-line cm-spoke-left"></div>
          <div class="cm-spoke-line cm-spoke-center"></div>
          <div class="cm-spoke-line cm-spoke-right"></div>
        </div>
        <div class="cm-clusters-grid">
          ${clustersHtml}
        </div>
      </div>
    `;
  },

  // 3. Hierarchy / Classification Renderer (Inverted tree structure, root -> categories -> subclasses/leaves)
  renderHierarchy(box, data, topic) {
    const root = data?.root || topic || "System Taxonomy";
    const categories = data?.categories || [
      { name: "Primary Classification", items: ["Core Primitive", "Direct Sub-type", "Concrete Implementation"] },
      { name: "Extended Categories", items: ["Optimized Model", "Specialized Variant", "Secondary Pattern"] },
      { name: "System Utilities", items: ["Control Protocol", "Interface Adaptor", "Auxiliary Utility"] }
    ];

    const categoriesHtml = categories.map((cat, i) => `
      <div class="hier-category-col">
        <div class="hier-vertical-lead"></div>
        <div class="hier-category-card hier-cat-card-${(i % 3) + 1}">
          <div class="hier-cat-header">
            <span class="hier-cat-level">Classification Group</span>
            <h5>${this.escapeHtml(cat.name)}</h5>
          </div>
          <div class="hier-leaves-list">
            ${(cat.items || []).map(item => `
              <div class="hier-leaf-item">
                <span class="hier-leaf-stem">↳</span>
                <span class="hier-leaf-text">${this.escapeHtml(item)}</span>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `).join('');

    box.innerHTML = `
      <div class="hierarchy-canvas">
        <div class="hier-root-row">
          <div class="hier-root-card">
            <span class="badge badge-purple" style="font-size: 0.65rem; margin-bottom: 0.25rem;">ROOT TAXONOMY</span>
            <h4 class="hier-root-name">🏷️ ${this.escapeHtml(root)}</h4>
          </div>
        </div>
        <div class="hier-trunk-stem"></div>
        <div class="hier-horizontal-bar"></div>
        <div class="hier-categories-row">
          ${categoriesHtml}
        </div>
      </div>
    `;
  },

  // 4. Architecture / Block Diagram Renderer (Modular components, functional units, interconnecting buses)
  renderArchitecture(box, data, topic) {
    const blocks = data?.blocks || [
      { name: "Input & Interface Unit", elements: ["Data Buffer", "Control Register", "Status Flags"] },
      { name: "Core Processing Engine", elements: ["ALU Unit", "Execution Pipeline", "Instruction Decoder"] },
      { name: "Storage & Memory Subsystem", elements: ["Cache / Registers", "Address Generator", "Memory Bus"] }
    ];

    const b1 = blocks[0] || { name: "Input Unit", elements: ["Buffer", "Flags"] };
    const b2 = blocks[1] || { name: "Core Processing", elements: ["ALU", "Decoder"] };
    const b3 = blocks[2] || { name: "Memory Unit", elements: ["Cache", "Bus"] };

    box.innerHTML = `
      <div class="architecture-canvas">
        <div class="arch-subsystems-grid">
          <!-- Block 1: Input / Interface -->
          <div class="arch-block-card arch-in">
            <div class="arch-block-header">
              <span class="arch-icon">📥</span>
              <div>
                <h5>${this.escapeHtml(b1.name)}</h5>
                <span class="arch-sub-badge">Interface Subsystem</span>
              </div>
            </div>
            <div class="arch-elements-list">
              ${(b1.elements || []).map(e => `
                <div class="arch-element-item">
                  <span class="arch-pin">▸</span>
                  <span>${this.escapeHtml(e)}</span>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- Bus Connector 1 -->
          <div class="arch-bus-connector">
            <span class="arch-bus-badge">Control Bus</span>
            <div class="arch-bus-arrows">⇄</div>
            <div class="arch-bus-track"></div>
          </div>

          <!-- Block 2: Core Processing Unit -->
          <div class="arch-block-card arch-core">
            <div class="arch-block-header">
              <span class="arch-icon">⚡</span>
              <div>
                <h5>${this.escapeHtml(b2.name)}</h5>
                <span class="arch-sub-badge badge-purple-sub">Execution Core</span>
              </div>
            </div>
            <div class="arch-elements-list">
              ${(b2.elements || []).map(e => `
                <div class="arch-element-item arch-core-item">
                  <span class="arch-pin core-pin">⚡</span>
                  <span>${this.escapeHtml(e)}</span>
                </div>
              `).join('')}
            </div>
          </div>

          <!-- Bus Connector 2 -->
          <div class="arch-bus-connector">
            <span class="arch-bus-badge">16/20-bit Data Bus</span>
            <div class="arch-bus-arrows">⇆</div>
            <div class="arch-bus-track"></div>
          </div>

          <!-- Block 3: Storage & Memory Subsystem -->
          <div class="arch-block-card arch-out">
            <div class="arch-block-header">
              <span class="arch-icon">💾</span>
              <div>
                <h5>${this.escapeHtml(b3.name)}</h5>
                <span class="arch-sub-badge">Storage & Interconnect</span>
              </div>
            </div>
            <div class="arch-elements-list">
              ${(b3.elements || []).map(e => `
                <div class="arch-element-item">
                  <span class="arch-pin">▸</span>
                  <span>${this.escapeHtml(e)}</span>
                </div>
              `).join('')}
            </div>
          </div>
        </div>

        <!-- System Bus Interconnect Rail -->
        <div class="arch-bus-rail-wrapper">
          <div class="arch-bus-rail">
            <span class="arch-rail-line"></span>
            <span class="arch-rail-text">═ ═ ═ SYSTEM INTERCONNECT & INTERNAL PERIPHERAL BUS ═ ═ ═</span>
            <span class="arch-rail-line"></span>
          </div>
        </div>
      </div>
    `;
  },

  // 5. Comparison Diagram Renderer (Side-by-side comparative analysis matrix)
  renderComparison(box, data, topic) {
    const cols = data?.columns || ["Standard Paradigm A", "Optimized Paradigm B"];
    const criteria = data?.criteria || [
      { dimension: "Primary Objective", val_a: "Structural Normalization", val_b: "Throughput Optimization" },
      { dimension: "System Complexity", val_a: "Low to Moderate", val_b: "High Concurrency" },
      { dimension: "Overhead & Redundancy", val_a: "Zero Anomalies", val_b: "Controlled Redundancy" },
      { dimension: "Optimal Workload", val_a: "Transactional Updates (OLTP)", val_b: "Analytical Reads (OLAP)" }
    ];

    box.innerHTML = `
      <div class="comparison-canvas">
        <div class="comp-matrix-wrapper">
          <table class="comp-matrix-table">
            <thead>
              <tr>
                <th class="comp-th comp-th-metric">Evaluation Dimension</th>
                <th class="comp-th comp-th-a">
                  <span class="comp-col-badge">Option A</span>
                  <div class="comp-col-title">${this.escapeHtml(cols[0] || 'Paradigm A')}</div>
                </th>
                <th class="comp-th comp-th-b">
                  <span class="comp-col-badge comp-badge-accent">Option B</span>
                  <div class="comp-col-title">${this.escapeHtml(cols[1] || 'Paradigm B')}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              ${criteria.map((c, idx) => `
                <tr class="comp-tr ${idx % 2 === 1 ? 'comp-tr-alt' : ''}">
                  <td class="comp-td comp-td-metric">
                    <strong>${this.escapeHtml(c.dimension)}</strong>
                  </td>
                  <td class="comp-td comp-td-a">
                    <span class="comp-val-chip">${this.escapeHtml(c.val_a)}</span>
                  </td>
                  <td class="comp-td comp-td-b">
                    <span class="comp-val-chip comp-chip-accent">${this.escapeHtml(c.val_b)}</span>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  },

  // 6. Relationship Diagram Renderer (Entities, cardinalities, dependencies)
  renderRelationship(box, data, topic) {
    const relationships = data?.relationships || [
      { source: topic || "Core Entity", relation: "defines & configures", target: "Subsystem Component" },
      { source: "Subsystem Component", relation: "requires & binds", target: "Execution Pipeline" },
      { source: "Execution Pipeline", relation: "coordinates with", target: "State Controller" },
      { source: "State Controller", relation: "persists to", target: "Data Repository" }
    ];

    box.innerHTML = `
      <div class="relationship-canvas">
        <div class="rel-links-stack">
          ${relationships.map((rel, idx) => `
            <div class="rel-link-row">
              <div class="rel-entity-card rel-source">
                <span class="rel-role-badge">Entity</span>
                <div class="rel-entity-name">${this.escapeHtml(rel.source)}</div>
              </div>
              <div class="rel-edge-bar">
                <span class="rel-cardinality-tag">1..1</span>
                <div class="rel-verb-pill">
                  <span>${this.escapeHtml(rel.relation)}</span>
                  <span class="rel-arrow-symbol">➔</span>
                </div>
                <span class="rel-cardinality-tag">1..*</span>
              </div>
              <div class="rel-entity-card rel-target">
                <span class="rel-role-badge rel-role-target">Target</span>
                <div class="rel-entity-name">${this.escapeHtml(rel.target)}</div>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  },

  // 7. Process Diagram Renderer (Phased pipeline, ordered milestone stages)
  renderProcess(box, data, topic) {
    const stages = data?.stages || [
      { step: 1, name: "Stage 1: Initialization", desc: `Prepare datasets and initialize baseline parameters for ${topic}.` },
      { step: 2, name: "Stage 2: Transformation", desc: "Execute core computational logic and apply feature transforms." },
      { step: 3, name: "Stage 3: Optimization", desc: "Iteratively evaluate objective criteria and refine parameters." },
      { step: 4, name: "Stage 4: Verification", desc: "Validate deliverable outputs against accuracy benchmarks." }
    ];

    box.innerHTML = `
      <div class="process-canvas">
        <div class="proc-pipeline-track">
          ${stages.map((stage, idx) => `
            <div class="proc-step-card">
              <div class="proc-step-top">
                <span class="proc-badge-num">0${stage.step || (idx + 1)}</span>
                <span class="proc-step-phase">Phase ${stage.step || (idx + 1)}</span>
              </div>
              <h5 class="proc-step-name">${this.escapeHtml(stage.name)}</h5>
              <p class="proc-step-desc">${this.escapeHtml(stage.desc)}</p>
              <div class="proc-step-bottom">
                <span class="proc-checkpoint-icon">✓</span>
                <span class="proc-checkpoint-label">Verified Deliverable</span>
              </div>
            </div>
            ${idx < stages.length - 1 ? '<div class="proc-track-arrow">➔</div>' : ''}
          `).join('')}
        </div>
      </div>
    `;
  },

  // Reference Diagrams Renderer (Trusted educational web repositories: Wikimedia Commons / Wikipedia)
  renderReferenceDiagrams(grid, refDiagrams, topic, conceptName = "") {
    if (!grid) return;

    if (!refDiagrams || refDiagrams.length === 0) {
      grid.innerHTML = `
        <div class="vl-ref-none">
          <div class="vl-ref-none-icon">🔍</div>
          <h4>No relevant reference diagram found for this concept.</h4>
          <p>We strictly validate reference diagrams against <strong>${this.escapeHtml(conceptName || topic)}</strong> to prevent displaying irrelevant images.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = `
      <div class="vl-cards-grid">
        ${refDiagrams.map((ref, idx) => `
          <div class="vl-ref-card" data-ref-index="${idx}">
            <div class="vl-ref-badge-strip">
              <span class="badge badge-purple" style="font-size: 0.68rem;">Reference Diagram</span>
              <span class="badge badge-outline" style="font-size: 0.68rem;">${this.escapeHtml(ref.license || 'CC BY-SA')}</span>
            </div>
            <div class="vl-ref-img-wrapper" title="Click to open full resolution image">
              <img src="${this.escapeHtml(ref.image_url)}" alt="${this.escapeHtml(ref.title)}" class="vl-ref-image" loading="lazy" onerror="this.onerror=null; this.parentElement.innerHTML='<div class=\\'vl-ref-fallback\\'>📊<br><span style=\\'font-size:0.75rem;\\'>Educational Schematic</span></div>';">
            </div>
            <div class="vl-ref-content">
              <h5 class="vl-ref-card-title">${this.escapeHtml(ref.title)}</h5>
              <p class="vl-ref-card-desc">${this.escapeHtml(ref.description || '')}</p>
              <div class="vl-ref-footer">
                <span class="vl-ref-source-tag">🏛️ ${this.escapeHtml(ref.source_website || 'Wikimedia Commons')}</span>
                <a href="${this.escapeHtml(ref.source_url || '#')}" target="_blank" rel="noopener noreferrer" class="vl-ref-source-link">
                  <span>View Source</span>
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                </a>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;

    // Click wrapper to view full image in a new tab
    grid.querySelectorAll(".vl-ref-img-wrapper").forEach(wrapper => {
      wrapper.addEventListener("click", () => {
        const img = wrapper.querySelector("img");
        if (img && img.src && !img.src.startsWith("data:")) {
          window.open(img.src, "_blank");
        }
      });
    });
  },

  // Legacy mermaid renderer fallback (kept for compatibility)
  async renderMermaidDiagram(viewerEl, diagramCode) {
    const box = viewerEl.querySelector(".diagram-render-box");
    if (!box || !diagramCode) return;
    await this.renderFlowchart(box, { mermaid_code: diagramCode }, "Diagram");
  },

  // Handle file uploads (PDF, DOCX, PPT)
  async handleFileUpload(file) {
    const hiddenInput = document.getElementById("hidden-file-input");
    if (hiddenInput) hiddenInput.value = "";

    if (!file) return;

    // Guard against empty 0-byte files
    if (file.size === 0) {
      LearnMateComponents.showToast("The selected file is empty (0 bytes). Please select a valid document.", "warning");
      return;
    }

    const container = document.getElementById("chat-messages-stream");
    if (!container) return;

    const user = (typeof LearnMateAPI !== "undefined" && LearnMateAPI.getUser()) || LearnMateData.currentUser;
    const initial = (user && (user.avatar_initial || user.avatarInitial)) || "M";
    const fileSizeFormatted = file.size < 1024 * 1024 
      ? (file.size / 1024).toFixed(1) + " KB" 
      : (file.size / (1024 * 1024)).toFixed(2) + " MB";

    // User upload bubble
    const userRow = document.createElement("div");
    userRow.className = "chat-message-row user";
    userRow.innerHTML = `
      <div class="chat-user-avatar">${initial}</div>
      <div class="chat-bubble-content">
        <p>📎 Uploaded study material: <strong>${this.escapeHtml(file.name)}</strong> (${fileSizeFormatted})</p>
      </div>
    `;
    container.appendChild(userRow);
    container.scrollTop = container.scrollHeight;

    LearnMateComponents.showToast(`Uploading "${file.name}" (${fileSizeFormatted})...`, "info");

    try {
      const formData = new FormData();
      formData.append("file", file);
      const uploadRes = await LearnMateAPI.uploadMaterial(formData);

      if (uploadRes.status === "success" || uploadRes.success) {
        const mat = uploadRes.material || (uploadRes.data && uploadRes.data.material) || {};
        const matId = mat.id || mat.material_id;
        const topicName = file.name.replace(/\.[^/.]+$/, "").replace(/[_-]/g, ' ').trim();

        // Reset previous session state and establish active material context
        this.currentSessionId = null;
        this.currentQuizId = null;
        this.activeMaterialId = matId;
        this.activeMaterialName = file.name;

        LearnMateComponents.showToast(`"${file.name}" saved! Extracting knowledge chunks with PyMuPDF/Docx & FAISS...`, "info");

        // Immediately trigger RAG learning generation for the uploaded material
        await this.generateContentForTopic(topicName, matId);
      } else {
        this.renderErrorMessage(uploadRes.message || "Failed to upload study material.");
      }
    } catch (e) {
      console.error(e);
      this.renderErrorMessage("Failed to upload study material to backend.");
    }
  },

  renderErrorMessage(msg) {
    const container = document.getElementById("chat-messages-stream");
    if (!container) return;

    const botRow = document.createElement("div");
    botRow.className = "chat-message-row assistant";
    botRow.innerHTML = `
      <div class="chat-ai-avatar" style="background: var(--danger);">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      </div>
      <div class="chat-bubble-content">
        <p style="color: var(--danger); font-weight: 600;">⚠️ ${this.escapeHtml(msg)}</p>
        <p style="margin-top: 0.5rem; font-size: 0.85rem; color: var(--text-secondary);">
          Please try again or select another study topic.
        </p>
      </div>
    `;
    container.appendChild(botRow);
    container.scrollTop = container.scrollHeight;
  },

  // Lightweight markdown converter for rich educational presentation
  renderMarkdown(text) {
    if (!text) return "";
    let html = this.escapeHtml(text);

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');

    // Bold & italic
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Blockquotes
    html = html.replace(/^&gt; (.*$)/gim, '<blockquote>$1</blockquote>');

    // Bullet lists
    html = html.replace(/^- (.*$)/gim, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Paragraph breaks
    html = html.replace(/\n\n+/g, '<br><br>');

    return html;
  },

  escapeHtml(text) {
    if (text == null) return "";
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
  }
};
