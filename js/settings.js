/**
 * LearnMate AI - Settings Page Logic
 * Connected to Flask Backend API with real MySQL database persistence.
 */

const LearnMateSettings = {
  async init() {
    this.bindSettingsTabs();
    await this.bindAccountForm();
    await this.bindPreferenceToggles();
    this.bindDangerZone();
  },

  bindSettingsTabs() {
    const navButtons = document.querySelectorAll(".settings-nav-item");
    const panels = document.querySelectorAll(".settings-tab-panel");

    navButtons.forEach(btn => {
      btn.addEventListener("click", () => {
        const target = btn.dataset.tab;

        navButtons.forEach(b => b.classList.toggle("active", b === btn));
        panels.forEach(p => p.classList.toggle("active", p.id === `tab-${target}`));
      });
    });
  },

  async bindAccountForm() {
    const nameInput = document.getElementById("settings-full-name");
    const emailInput = document.getElementById("settings-email");
    const saveAccountBtn = document.getElementById("btn-save-account");
    const savePassBtn = document.getElementById("btn-change-password");

    let user = (typeof LearnMateAPI !== "undefined" && LearnMateAPI.getUser()) || LearnMateData.currentUser;
    if (typeof LearnMateAPI !== "undefined") {
      try {
        const meRes = await LearnMateAPI.getMe();
        if (meRes.success && meRes.data && meRes.data.user) {
          user = meRes.data.user;
        }
      } catch (e) {}
    }

    if (user) {
      if (nameInput) nameInput.value = user.full_name || user.fullName || "";
      if (emailInput) {
        emailInput.value = user.email || "";
        emailInput.readOnly = true; // Email is account identifier
        emailInput.style.backgroundColor = "var(--bg-app)";
      }
    }

    if (saveAccountBtn) {
      saveAccountBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        const newName = nameInput ? nameInput.value.trim() : "";

        if (!newName) {
          LearnMateComponents.showToast("Full name cannot be empty.", "warning");
          return;
        }

        saveAccountBtn.disabled = true;
        LearnMateComponents.showToast("Updating account details...", "info");

        try {
          const res = await LearnMateAPI.updateProfile({ full_name: newName });
          if (res.success) {
            LearnMateComponents.showToast("Account details updated successfully!", "success");
            LearnMateComponents.initSidebar("settings");
          } else {
            LearnMateComponents.showToast(res.message || "Failed to update account.", "danger");
          }
        } catch (err) {
          LearnMateComponents.showToast("Network error updating account.", "danger");
        } finally {
          saveAccountBtn.disabled = false;
        }
      });
    }

    if (savePassBtn) {
      savePassBtn.addEventListener("click", async (e) => {
        e.preventDefault();
        const curPass = document.getElementById("current-pass");
        const newPass = document.getElementById("new-pass");
        const confPass = document.getElementById("conf-new-pass");

        const curVal = curPass ? curPass.value : "";
        const newVal = newPass ? newPass.value : "";
        const confVal = confPass ? confPass.value : "";

        if (!curVal || !newVal || !confVal) {
          LearnMateComponents.showToast("Please fill in all password fields.", "warning");
          return;
        }
        if (newVal !== confVal) {
          LearnMateComponents.showToast("New passwords do not match.", "warning");
          return;
        }
        if (newVal.length < 6) {
          LearnMateComponents.showToast("New password must be at least 6 characters.", "warning");
          return;
        }

        savePassBtn.disabled = true;
        LearnMateComponents.showToast("Verifying and changing password...", "info");

        try {
          const res = await LearnMateAPI.changePassword({
            current_password: curVal,
            new_password: newVal
          });

          if (res.success) {
            curPass.value = "";
            newPass.value = "";
            confPass.value = "";
            LearnMateComponents.showToast("Password changed successfully!", "success");
          } else {
            LearnMateComponents.showToast(res.message || "Failed to update password.", "danger");
          }
        } catch (err) {
          LearnMateComponents.showToast("Network error changing password.", "danger");
        } finally {
          savePassBtn.disabled = false;
        }
      });
    }
  },

  async bindPreferenceToggles() {
    const savePrefBtn = document.getElementById("btn-save-settings-prefs");
    const checkboxes = document.querySelectorAll(".setting-pref-cb");

    // Pre-populate checkboxes from MySQL
    try {
      const res = await LearnMateAPI.getPreferences();
      if (res.success && res.data && res.data.preferences) {
        const saved = res.data.preferences;
        checkboxes.forEach(cb => {
          cb.checked = saved.includes(cb.dataset.pref);
        });
      }
    } catch (e) {}

    if (savePrefBtn) {
      savePrefBtn.addEventListener("click", async () => {
        const selected = [];
        checkboxes.forEach(cb => {
          if (cb.checked) selected.push(cb.dataset.pref);
        });

        if (selected.length === 0) {
          LearnMateComponents.showToast("Please select at least one learning style.", "warning");
          return;
        }

        savePrefBtn.disabled = true;
        LearnMateComponents.showToast("Saving learning preferences...", "info");

        try {
          const res = await LearnMateAPI.savePreferences(selected, selected[0]);
          if (res.success) {
            LearnMateComponents.showToast("Learning preferences updated in database!", "success");
            LearnMateComponents.initSidebar("settings");
          } else {
            LearnMateComponents.showToast(res.message || "Failed to update preferences.", "danger");
          }
        } catch (err) {
          LearnMateComponents.showToast("Network error updating preferences.", "danger");
        } finally {
          savePrefBtn.disabled = false;
        }
      });
    }
  },

  bindDangerZone() {
    const logoutBtn = document.getElementById("btn-logout");
    const deleteBtn = document.getElementById("btn-delete-account");

    if (logoutBtn) {
      logoutBtn.addEventListener("click", () => {
        LearnMateComponents.showToast("Logging out...", "info");
        if (typeof LearnMateAPI !== "undefined") {
          setTimeout(() => LearnMateAPI.logout(), 400);
        } else {
          setTimeout(() => {
            window.location.replace("/");
          }, 400);
        }
      });
    }

    if (deleteBtn) {
      deleteBtn.addEventListener("click", async () => {
        if (confirm("Are you sure you want to delete your account? This action cannot be undone.")) {
          LearnMateComponents.showToast("Deleting account...", "warning");
          try {
            if (typeof LearnMateAPI !== "undefined") {
              const res = await LearnMateAPI.deleteAccount();
              if (res.success) {
                LearnMateComponents.showToast("Account deleted.", "info");
                setTimeout(() => {
                  window.location.replace("/");
                }, 500);
                return;
              }
            }
          } catch (e) {}
          setTimeout(() => {
            window.location.replace("/");
          }, 500);
        }
      });
    }
  }
};
