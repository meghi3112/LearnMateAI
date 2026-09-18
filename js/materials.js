/**
 * LearnMate AI - My Materials Page Logic
 * Connected to Flask Backend API with real MySQL database persistence.
 */

const LearnMateMaterials = {
  materialsList: [],
  selectedFile: null,

  async init() {
    await this.loadMaterials();
    this.bindSearchAndFilter();
    this.bindUploadModal();
  },

  async loadMaterials() {
    const container = document.getElementById("materials-list-container");
    if (container) {
      container.innerHTML = `
        <div style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
          <p>Loading your study materials...</p>
        </div>
      `;
    }

    try {
      const res = await LearnMateAPI.getMaterials();
      if (res.success && res.data) {
        this.materialsList = res.data.materials || [];
      } else {
        this.materialsList = [];
      }
    } catch (e) {
      console.error("Failed to load materials:", e);
      this.materialsList = [];
    }

    this.renderMaterials();
  },

  renderMaterials(items = this.materialsList) {
    const container = document.getElementById("materials-list-container");
    if (!container) return;

    if (items.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; padding: 3.5rem 2rem; background: #FFFFFF; border-radius: var(--radius-xl); border: 1px dashed var(--border-subtle);">
          <div style="font-size: 2.75rem; margin-bottom: 0.75rem;">📁</div>
          <h3 style="font-size: 1.25rem; margin-bottom: 0.35rem; color: var(--text-primary);">No study materials uploaded yet</h3>
          <p style="color: var(--text-muted); font-size: 0.9rem; max-width: 440px; margin: 0 auto 1.5rem;">
            Upload your lecture slides, notes, or textbooks in PDF, DOCX, or PPT/PPTX format. LearnMate AI will generate personalized summaries, flashcards, and quizzes from your materials.
          </p>
          <button class="btn btn-primary btn-sm" onclick="document.getElementById('btn-open-upload-modal').click()">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Upload Your First Material
          </button>
        </div>
      `;
      return;
    }

    container.innerHTML = items.map(mat => {
      const ext = (mat.type || "pdf").toLowerCase();
      const typeBadge = ext.startsWith("doc") ? "DOCX" : (ext.startsWith("ppt") ? "PPT" : "PDF");

      return `
        <div class="material-card-item" id="material-item-${mat.id}">
          <div class="flex items-center gap-4">
            <div class="file-type-icon ${ext}">
              ${typeBadge}
            </div>
            <div>
              <h4 style="font-size: 1.05rem; margin-bottom: 0.2rem; color: var(--text-primary);">${mat.name}</h4>
              <div class="flex items-center gap-3" style="font-size: 0.8rem; color: var(--text-muted);">
                <span>Topic: <strong>${mat.topic}</strong></span>
                <span>•</span>
                <span>Size: ${mat.size}</span>
                <span>•</span>
                <span>Uploaded: ${mat.uploadDate}</span>
              </div>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <a href="${LearnMateAPI.getMaterialDownloadUrl(mat.id)}" download="${mat.name}" target="_blank" class="btn btn-outline btn-sm btn-download-material" data-id="${mat.id}" style="text-decoration: none;">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              Download
            </a>
            <button class="btn btn-primary btn-sm btn-generate-from-material" data-id="${mat.id}" data-topic="${mat.topic}">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
              Generate Resources
            </button>
            <button class="btn btn-danger btn-sm btn-delete-material" data-id="${mat.id}" data-name="${mat.name}">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
      `;
    }).join("");

    // Bind item actions
    container.querySelectorAll(".btn-view-material").forEach(btn => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.id;
        const viewUrl = LearnMateAPI.getMaterialDownloadUrl(id);
        window.open(viewUrl, "_blank");
      });
    });

    container.querySelectorAll(".btn-generate-from-material").forEach(btn => {
      btn.addEventListener("click", () => {
        const topic = btn.dataset.topic;
        const id = btn.dataset.id;
        sessionStorage.setItem("learnmate_launch_topic", topic);
        sessionStorage.setItem("learnmate_launch_material_id", id);
        window.location.href = "app.html";
      });
    });

    container.querySelectorAll(".btn-delete-material").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const name = btn.dataset.name;
        if (!confirm(`Are you sure you want to delete "${name}"?`)) return;

        btn.disabled = true;
        LearnMateComponents.showToast(`Deleting "${name}"...`, "info");
        try {
          const res = await LearnMateAPI.deleteMaterial(id);
          if (res.success) {
            LearnMateComponents.showToast(`"${name}" removed successfully.`, "success");
            await this.loadMaterials();
          } else {
            LearnMateComponents.showToast(res.message || "Failed to delete material.", "danger");
            btn.disabled = false;
          }
        } catch (e) {
          LearnMateComponents.showToast("Network error deleting material.", "danger");
          btn.disabled = false;
        }
      });
    });
  },

  bindSearchAndFilter() {
    const searchInput = document.getElementById("search-materials-input");
    const filterSelect = document.getElementById("filter-materials-type");

    const filterHandler = () => {
      const query = searchInput ? searchInput.value.toLowerCase().trim() : "";
      const type = filterSelect ? filterSelect.value : "all";

      const filtered = this.materialsList.filter(m => {
        const matchesQuery = m.name.toLowerCase().includes(query) || (m.topic && m.topic.toLowerCase().includes(query));
        const ext = (m.type || "").toLowerCase();
        let matchesType = (type === "all");
        if (type === "pdf") matchesType = ext === "pdf";
        else if (type === "docx") matchesType = ext.startsWith("doc");
        else if (type === "pptx") matchesType = ext.startsWith("ppt");

        return matchesQuery && matchesType;
      });

      this.renderMaterials(filtered);
    };

    if (searchInput) searchInput.addEventListener("input", filterHandler);
    if (filterSelect) filterSelect.addEventListener("change", filterHandler);
  },

  bindUploadModal() {
    const openBtn = document.getElementById("btn-open-upload-modal");
    const modal = document.getElementById("upload-material-modal");
    const closeBtn = document.getElementById("btn-close-upload-modal");
    const cancelBtn = document.getElementById("btn-cancel-upload");
    const submitBtn = document.getElementById("btn-submit-upload");
    const filePicker = document.getElementById("modal-file-picker");
    const titleInput = document.getElementById("modal-material-title");

    const closeModal = () => {
      if (modal) modal.classList.remove("active");
      this.selectedFile = null;
      if (filePicker) filePicker.value = "";
      if (titleInput) titleInput.value = "";
    };

    if (openBtn && modal) {
      openBtn.addEventListener("click", () => modal.classList.add("active"));
    }
    if (closeBtn) closeBtn.addEventListener("click", closeModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);

    if (filePicker) {
      filePicker.addEventListener("change", (e) => {
        if (e.target.files && e.target.files.length > 0) {
          const picked = e.target.files[0];
          if (picked.size === 0) {
            LearnMateComponents.showToast("The selected file is empty (0 bytes). Please choose a valid document.", "warning");
            filePicker.value = "";
            this.selectedFile = null;
            return;
          }
          this.selectedFile = picked;
          if (titleInput && !titleInput.value) {
            titleInput.value = this.selectedFile.name;
          }
          const formattedSize = picked.size < 1024 * 1024 
            ? (picked.size / 1024).toFixed(1) + " KB" 
            : (picked.size / (1024 * 1024)).toFixed(2) + " MB";
          LearnMateComponents.showToast(`Selected "${this.selectedFile.name}" (${formattedSize})`, "info");
        }
      });
    }

    if (submitBtn) {
      submitBtn.addEventListener("click", async () => {
        if (!this.selectedFile && filePicker && filePicker.files.length > 0) {
          this.selectedFile = filePicker.files[0];
        }

        if (!this.selectedFile) {
          LearnMateComponents.showToast("Please select a file to upload.", "warning");
          return;
        }

        if (this.selectedFile.size === 0) {
          LearnMateComponents.showToast("The selected file is empty (0 bytes). Please upload a valid document.", "warning");
          return;
        }

        submitBtn.disabled = true;
        submitBtn.style.opacity = "0.7";
        LearnMateComponents.showToast("Uploading study material...", "info");

        const formData = new FormData();
        formData.append("file", this.selectedFile);

        try {
          const res = await LearnMateAPI.uploadMaterial(formData);
          if (res.success) {
            LearnMateComponents.showToast(res.message || "Material uploaded successfully!", "success");
            closeModal();
            await this.loadMaterials();
          } else {
            LearnMateComponents.showToast(res.message || "Upload failed.", "danger");
          }
        } catch (err) {
          console.error("Upload error:", err);
          LearnMateComponents.showToast("Error communicating with upload server.", "danger");
        } finally {
          submitBtn.disabled = false;
          submitBtn.style.opacity = "1";
        }
      });
    }
  }
};
