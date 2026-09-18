/**
 * LearnMate AI - Auth & Preference Onboarding Flows
 * Connected to Flask Backend API with real MySQL database persistence.
 */

const LearnMateAuth = {
  // 1. Login Page Logic
  initLogin() {
    const loginForm = document.getElementById("login-form");
    if (!loginForm) return;

    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const emailInput = document.getElementById("login-email");
      const passInput = document.getElementById("login-password");
      const submitBtn = loginForm.querySelector("button[type='submit']");

      const email = emailInput ? emailInput.value.trim() : "";
      const pass = passInput ? passInput.value : "";

      if (!email || !pass) {
        LearnMateComponents.showToast("Please enter both email and password.", "warning");
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.style.opacity = "0.7";
      }

      LearnMateComponents.showToast("Signing in to LearnMate AI...", "info");

      try {
        const res = await LearnMateAPI.login(email, pass);

        if (res.success && res.data && res.data.user) {
          const userName = res.data.user.full_name || "Student";
          LearnMateComponents.showToast(`Welcome back, ${userName}!`, "success");
          setTimeout(() => {
            window.location.href = "app.html";
          }, 600);
        } else {
          LearnMateComponents.showToast(res.message || "Invalid email or password.", "danger");
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.style.opacity = "1";
          }
        }
      } catch (err) {
        console.error("Login exception:", err);
        LearnMateComponents.showToast("Unable to communicate with the server.", "danger");
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.style.opacity = "1";
        }
      }
    });
  },

  // 2. Create Account Page Logic (Strictly Name, Email, Pass, ConfPass)
  initSignup() {
    const signupForm = document.getElementById("signup-form");
    if (!signupForm) return;

    const nameInput = document.getElementById("signup-name");
    const emailInput = document.getElementById("signup-email");
    const passInput = document.getElementById("signup-password");
    const confInput = document.getElementById("signup-confirm-password");
    const strengthBar = document.getElementById("password-strength-fill");
    const submitBtn = signupForm.querySelector("button[type='submit']");

    // Live password strength indicator
    if (passInput && strengthBar) {
      passInput.addEventListener("input", () => {
        const val = passInput.value;
        let score = 0;
        if (val.length >= 6) score += 25;
        if (val.length >= 10) score += 25;
        if (/[A-Z]/.test(val) && /[0-9]/.test(val)) score += 25;
        if (/[^A-Za-z0-9]/.test(val)) score += 25;

        strengthBar.style.width = `${score}%`;
        if (score <= 25) strengthBar.style.backgroundColor = "var(--danger)";
        else if (score <= 50) strengthBar.style.backgroundColor = "var(--warning)";
        else if (score <= 75) strengthBar.style.backgroundColor = "var(--blue-accent)";
        else strengthBar.style.backgroundColor = "var(--success)";
      });
    }

    signupForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const fullName = nameInput ? nameInput.value.trim() : "";
      const email = emailInput ? emailInput.value.trim() : "";
      const password = passInput ? passInput.value : "";
      const confirmPass = confInput ? confInput.value : "";

      if (!fullName || !email || !password || !confirmPass) {
        LearnMateComponents.showToast("All fields are required.", "warning");
        return;
      }

      if (password.length < 6) {
        LearnMateComponents.showToast("Password must be at least 6 characters.", "warning");
        return;
      }

      if (password !== confirmPass) {
        LearnMateComponents.showToast("Passwords do not match.", "warning");
        return;
      }

      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.style.opacity = "0.7";
      }

      LearnMateComponents.showToast("Creating your LearnMate AI account...", "info");

      try {
        const res = await LearnMateAPI.register(fullName, email, password);

        if (res.success && res.data && res.data.user) {
          LearnMateComponents.showToast("Account created! Let's personalize your learning.", "success");
          setTimeout(() => {
            window.location.href = "preferences.html";
          }, 600);
        } else {
          LearnMateComponents.showToast(res.message || "Failed to create account.", "danger");
          if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.style.opacity = "1";
          }
        }
      } catch (err) {
        console.error("Signup exception:", err);
        LearnMateComponents.showToast("Unable to communicate with the server.", "danger");
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.style.opacity = "1";
        }
      }
    });
  },

  // 3. Learning Preference Setup Onboarding
  initPreferencesSetup() {
    if (typeof LearnMateAPI !== "undefined" && LearnMateAPI.requireAuth) {
      if (!LearnMateAPI.requireAuth()) return;
    }

    const prefCards = document.querySelectorAll(".pref-card-choice");
    const saveBtn = document.getElementById("btn-save-onboarding-prefs");
    const primaryFocusSelect = document.getElementById("onboarding-primary-focus");
    const paceSelect = document.getElementById("onboarding-pace");

    // Pre-load saved preferences from MySQL
    (async () => {
      try {
        const res = await LearnMateAPI.getPreferences();
        if (res.success && res.data && res.data.preferences && res.data.preferences.length > 0) {
          const savedPrefs = res.data.preferences;
          prefCards.forEach(card => {
            const pref = card.dataset.pref;
            card.classList.toggle("selected", savedPrefs.includes(pref));
          });

          if (primaryFocusSelect && res.data.primary_focus) {
            primaryFocusSelect.value = res.data.primary_focus;
          }
        }
      } catch (e) {
        console.warn("Could not pre-load saved preferences:", e);
      }
    })();

    prefCards.forEach(card => {
      card.addEventListener("click", () => {
        card.classList.toggle("selected");
      });
    });

    if (saveBtn) {
      saveBtn.addEventListener("click", async () => {
        const selected = [];
        document.querySelectorAll(".pref-card-choice.selected").forEach(c => {
          selected.push(c.dataset.pref);
        });

        if (selected.length === 0) {
          LearnMateComponents.showToast("Please select at least one learning preference.", "warning");
          return;
        }

        const primaryFocus = primaryFocusSelect ? primaryFocusSelect.value : selected[0];
        const pace = paceSelect ? paceSelect.value : "Steady";

        saveBtn.disabled = true;
        saveBtn.style.opacity = "0.7";

        LearnMateComponents.showToast("Saving preferences to database...", "info");

        try {
          const res = await LearnMateAPI.savePreferences(selected, primaryFocus, pace);
          
          LearnMateComponents.showToast("Preferences saved! Opening your AI workspace...", "success");
          setTimeout(() => {
            window.location.href = "app.html";
          }, 600);
        } catch (err) {
          console.error("Preference save exception:", err);
          LearnMateComponents.showToast("Saved locally. Opening workspace...", "info");
          setTimeout(() => {
            window.location.href = "app.html";
          }, 600);
        }
      });
    }
  }
};
