/* ui.js — shared UI helpers: toasts, loading overlay, nav/view switching */

const UI = (() => {
  const toastContainer = document.getElementById("toast-container");
  const loadingOverlay = document.getElementById("loading-overlay");
  const loadingMessage = document.getElementById("loading-message");

  function toast(message, type = "info", duration = 4500) {
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.innerHTML = `<span>${escapeHtml(message)}</span>`;
    toastContainer.appendChild(el);
    setTimeout(() => el.remove(), duration);
  }

  function showLoading(message = "Processing...") {
    loadingMessage.textContent = message;
    loadingOverlay.classList.remove("hidden");
  }

  function hideLoading() {
    loadingOverlay.classList.add("hidden");
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function formatTime(totalSeconds) {
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = Math.floor(totalSeconds % 60);
    return [h, m, s].map((n) => String(n).padStart(2, "0")).join(":");
  }

  function initNav() {
    const links = document.querySelectorAll(".nav-link");
    const menuBtn = document.getElementById("mobile-menu-btn");
    const nav = document.getElementById("main-nav");
    if (!nav || links.length === 0) return; // not on a page with the dashboard header (e.g. login/signup)

    // Each nav item scrolls to its own section - previously every link
    // scrolled to #history-card, which made every click but the first
    // look broken.
    const targets = {
      dashboard: "dashboard-top",
      meetings: "history-card",
      notes: "summary-card",
      settings: "settings-card",
    };

    function activateView(view) {
      links.forEach((l) => l.classList.toggle("active", l.dataset.view === view));
      nav.classList.remove("open");

      const targetId = targets[view];
      const targetEl = targetId && document.getElementById(targetId);
      if (targetEl) {
        targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
      }

      if (view === "meetings") {
        Notes.loadHistory();
      } else if (view === "settings") {
        Settings.load();
      }
    }

    links.forEach((link) => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        activateView(link.dataset.view);
      });
    });

    // The avatar dropdown also has a "Settings" shortcut - reuse the same logic.
    document.querySelectorAll('.dropdown-item[data-view]').forEach((item) => {
      item.addEventListener("click", (e) => {
        e.preventDefault();
        closeAllDropdowns();
        activateView(item.dataset.view);
      });
    });

    if (menuBtn) menuBtn.addEventListener("click", () => nav.classList.toggle("open"));
  }

  function closeAllDropdowns() {
    document.querySelectorAll(".dropdown-panel").forEach((p) => p.classList.add("hidden"));
  }

  function initHeaderDropdowns() {
    const notifBtn = document.getElementById("notif-btn");
    const notifDropdown = document.getElementById("notif-dropdown");
    const avatarBtn = document.getElementById("avatar-btn");
    const avatarDropdown = document.getElementById("avatar-dropdown");

    function toggle(panel) {
      const willOpen = panel.classList.contains("hidden");
      closeAllDropdowns();
      if (willOpen) panel.classList.remove("hidden");
    }

    // avatar-btn/avatar-dropdown only exist when someone is logged in
    // (see index.html's {% if user.is_authenticated %}) - bind each
    // control independently so anonymous visitors still get a working
    // notification bell even without an account.
    if (notifBtn && notifDropdown) {
      notifBtn.addEventListener("click", (e) => { e.stopPropagation(); toggle(notifDropdown); });
    }
    if (avatarBtn && avatarDropdown) {
      avatarBtn.addEventListener("click", (e) => { e.stopPropagation(); toggle(avatarDropdown); });
    }
    if (notifBtn || avatarBtn) {
      document.addEventListener("click", closeAllDropdowns);
    }
  }

  function showConfigBanner(message) {
    const banner = document.getElementById("config-banner");
    if (!banner) return;
    banner.innerHTML = message;
    banner.classList.remove("hidden");
  }

  return {
    toast, showLoading, hideLoading, escapeHtml, formatTime, initNav,
    initHeaderDropdowns, showConfigBanner,
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  UI.initNav();
  UI.initHeaderDropdowns();
});
