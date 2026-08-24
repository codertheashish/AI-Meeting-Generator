/* auth.js — form handling for login.html, signup.html, forgot_password.html, reset_password.html */

(() => {
  function togglePasswordField(toggleBtn, input) {
    if (!toggleBtn || !input) return;
    toggleBtn.addEventListener("click", () => {
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      toggleBtn.innerHTML = showing
        ? '<i class="fa-regular fa-eye"></i>'
        : '<i class="fa-regular fa-eye-slash"></i>';
    });
  }

  async function postJson(url, body) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    let data;
    try {
      data = await res.json();
    } catch {
      data = {};
    }
    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
  }

  function setSubmitting(btn, isSubmitting, idleLabel) {
    btn.disabled = isSubmitting;
    btn.innerHTML = isSubmitting
      ? '<i class="fa-solid fa-spinner fa-spin"></i> Please wait…'
      : idleLabel;
  }

  document.addEventListener("DOMContentLoaded", () => {
    // --- Login form ---
    const loginForm = document.getElementById("login-form");
    if (loginForm) {
      togglePasswordField(document.getElementById("toggle-password"), document.getElementById("password"));
      loginForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = document.getElementById("login-submit");
        setSubmitting(btn, true, "Log In");
        try {
          const data = await postJson("/api/auth/login", {
            email: document.getElementById("email").value.trim(),
            password: document.getElementById("password").value,
          });
          window.location.href = data.redirect || "/";
        } catch (err) {
          UI.toast(err.message, "error");
          setSubmitting(btn, false, "Log In");
        }
      });
    }

    // --- Signup form ---
    const signupForm = document.getElementById("signup-form");
    if (signupForm) {
      togglePasswordField(document.getElementById("toggle-password"), document.getElementById("password"));
      signupForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const password = document.getElementById("password").value;
        if (password.length < 8) {
          UI.toast("Password must be at least 8 characters.", "warning");
          return;
        }
        const btn = document.getElementById("signup-submit");
        setSubmitting(btn, true, "Create Account");
        try {
          const data = await postJson("/api/auth/signup", {
            name: document.getElementById("name").value.trim(),
            email: document.getElementById("email").value.trim(),
            password,
          });
          window.location.href = data.redirect || "/";
        } catch (err) {
          UI.toast(err.message, "error");
          setSubmitting(btn, false, "Create Account");
        }
      });
    }

    // --- Forgot password form ---
    const forgotForm = document.getElementById("forgot-form");
    if (forgotForm) {
      forgotForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = document.getElementById("forgot-submit");
        setSubmitting(btn, true, "Send Reset Link");
        try {
          await postJson("/api/auth/forgot-password", {
            email: document.getElementById("email").value.trim(),
          });
          document.getElementById("forgot-form-wrapper").classList.add("hidden");
          document.getElementById("forgot-success").classList.remove("hidden");
        } catch (err) {
          UI.toast(err.message, "error");
          setSubmitting(btn, false, "Send Reset Link");
        }
      });
    }

    // --- Reset password form ---
    const resetForm = document.getElementById("reset-form");
    if (resetForm) {
      togglePasswordField(document.getElementById("toggle-password"), document.getElementById("password"));
      resetForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const password = document.getElementById("password").value;
        const confirm = document.getElementById("confirm-password").value;
        if (password.length < 8) {
          UI.toast("Password must be at least 8 characters.", "warning");
          return;
        }
        if (password !== confirm) {
          UI.toast("Passwords don't match.", "warning");
          return;
        }
        const btn = document.getElementById("reset-submit");
        setSubmitting(btn, true, "Reset Password");
        try {
          const data = await postJson("/api/auth/reset-password", {
            token: resetForm.dataset.token,
            password,
          });
          UI.toast("Password reset. Redirecting to log in…", "success");
          setTimeout(() => { window.location.href = data.redirect || "/login"; }, 1200);
        } catch (err) {
          UI.toast(err.message, "error");
          setSubmitting(btn, false, "Reset Password");
        }
      });
    }
  });
})();
