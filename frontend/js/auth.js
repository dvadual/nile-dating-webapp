const authCard = document.querySelector("#auth-card");
const loginForm = document.querySelector("#login-form");
const signupForm = document.querySelector("#signup-form");
const loginWelcome = document.querySelector("#welcome-login");
const signupWelcome = document.querySelector("#welcome-signup");
const signupPassword = document.querySelector("#signup-password");
const confirmPassword = document.querySelector("#signup-confirm-password");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
let isAnimating = false;
let isSignup = new URLSearchParams(window.location.search).get("mode") === "signup";

function getPanelTransitionDuration() {
  if (reducedMotion.matches) {
    return 0;
  }

  const duration = getComputedStyle(authCard)
    .getPropertyValue("--transition-panel")
    .trim();
  const value = Number.parseFloat(duration);

  if (duration.endsWith("ms")) {
    return value;
  }

  return duration.endsWith("s") ? value * 1000 : 0;
}

function showState(showSignup) {
  isSignup = showSignup;
  authCard.classList.toggle("is-signup", isSignup);
  loginForm.hidden = isSignup;
  signupForm.hidden = !isSignup;
  loginWelcome.hidden = isSignup;
  signupWelcome.hidden = !isSignup;
  loginForm.querySelector(".form-status").hidden = true;
  signupForm.querySelector(".form-status").hidden = true;
}

function waitForPanelTransition() {
  return new Promise((resolve) => {
    window.setTimeout(resolve, getPanelTransitionDuration());
  });
}

async function switchState(showSignup) {
  if (isAnimating || showSignup === isSignup) {
    return;
  }

  isAnimating = true;
  authCard.classList.add("is-expanding");
  await waitForPanelTransition();

  showState(showSignup);
  authCard.classList.remove("is-expanding");
  await waitForPanelTransition();

  isAnimating = false;
}

document.querySelectorAll("[data-switch-state]").forEach((button) => {
  button.addEventListener("click", () => {
    switchState(button.dataset.switchState === "signup");
  });
});

document.querySelectorAll("[data-placeholder-link]").forEach((link) => {
  link.addEventListener("click", (event) => event.preventDefault());
});

[loginForm, signupForm].forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const status = form.querySelector(".form-status");
    status.textContent =
      "Authentication is not connected yet. Your information has not been submitted.";
    status.hidden = false;
  });
});

function validatePasswordConfirmation() {
  confirmPassword.setCustomValidity(
    confirmPassword.value === signupPassword.value ? "" : "Passwords must match.",
  );
}

signupPassword.addEventListener("input", validatePasswordConfirmation);
confirmPassword.addEventListener("input", validatePasswordConfirmation);

showState(isSignup);
window.requestAnimationFrame(() => authCard.classList.add("is-ready"));
