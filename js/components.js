/**
 * LearnMate AI - Reusable Components & Layout Injector
 */

const LearnMateComponents = {
  // Navigation items matching exact specifications
  navItems: [
    { id: "home", label: "Home", href: "app.html", icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>` },
    { id: "profile", label: "My Profile", href: "profile.html", icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>` },
    { id: "history", label: "Learning History", href: "history.html", icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>` },
    { id: "materials", label: "My Materials", href: "materials.html", icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><polyline points="10 2 10 10 13 7 16 10 16 2"/></svg>` },
    { id: "performance", label: "Performance", href: "performance.html", icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>` },
    { id: "recommendations", label: "Recommendations", href: "recommendations.html", icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>` },
    { id: "settings", label: "Settings", href: "settings.html", icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>` }
  ],

  /**
   * Injects the standard LearnMate AI sidebar into the container element
   */
  initSidebar(activePageId) {
    if (typeof LearnMateAPI !== "undefined" && LearnMateAPI.requireAuth) {
      if (!LearnMateAPI.requireAuth()) return;
    }

    const sidebarEl = document.getElementById("app-sidebar");
    if (!sidebarEl) return;

    if (typeof LearnMateAPI !== "undefined" && LearnMateAPI.syncCurrentUser) {
      LearnMateAPI.syncCurrentUser();
    }

    const navLinksHtml = this.navItems.map(item => `
      <a href="${item.href}" class="nav-link ${item.id === activePageId ? 'active' : ''}">
        ${item.icon}
        <span>${item.label}</span>
      </a>
    `).join("");

    sidebarEl.innerHTML = `
      <div class="sidebar-header">
        <div class="brand-logo">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
            <path d="M6 12v5c3 3 9 3 12 0v-5"/>
          </svg>
        </div>
        <div class="brand-info">
          <span class="brand-name">LearnMate AI</span>
          <span class="brand-tagline">Learn Smarter, Not Harder</span>
        </div>
      </div>
      <nav class="sidebar-nav">
        <div class="nav-section-title">Navigation</div>
        ${navLinksHtml}
      </nav>
      <div class="sidebar-footer">
        <a href="profile.html" class="user-snippet">
          <div class="user-avatar">${LearnMateData.currentUser.avatarInitial}</div>
          <div class="user-details">
            <div class="user-name">${LearnMateData.currentUser.fullName}</div>
            <div class="user-pref-tag">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
              <span>${LearnMateData.currentUser.primaryFocus} Style</span>
            </div>
          </div>
        </a>
      </div>
    `;

    // Mobile menu support
    const toggleBtn = document.getElementById("mobile-menu-toggle");
    const overlay = document.getElementById("sidebar-overlay");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        sidebarEl.classList.toggle("open");
        if (overlay) overlay.classList.toggle("open");
      });
    }
    if (overlay) {
      overlay.addEventListener("click", () => {
        sidebarEl.classList.remove("open");
        overlay.classList.remove("open");
      });
    }
  },

  /**
   * Displays an unobtrusive toast notification
   */
  showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    
    let iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
    if (type === "success") {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
    } else if (type === "warning") {
      iconSvg = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2.5"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
    }

    toast.innerHTML = `${iconSvg}<span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(100%)";
      toast.style.transition = "all 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 3200);
  }
};
