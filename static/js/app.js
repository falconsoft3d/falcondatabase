// Small UI helpers for the falcondatabase dashboard.
// Translated strings come from data-i18n-* attributes on <body>.
const i18n = document.body.dataset;

// Copy buttons: <button data-copy="#input-id"> or <button data-copy-text="...">
document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy], [data-copy-text]");
  if (!button) return;
  const target = button.dataset.copy && document.querySelector(button.dataset.copy);
  const text = button.dataset.copyText ?? (target ? (target.value ?? target.textContent) : "");
  try {
    await navigator.clipboard.writeText(text.trim());
    const original = button.innerHTML;
    button.textContent = i18n.i18nCopied;
    setTimeout(() => (button.innerHTML = original), 1200);
  } catch {
    if (target && target.select) target.select();
  }
});

// Show / hide secret inputs: <button data-toggle-secret="#input-id">
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-toggle-secret]");
  if (!button) return;
  const input = document.querySelector(button.dataset.toggleSecret);
  input.type = input.type === "password" ? "text" : "password";
  button.textContent = input.type === "password" ? i18n.i18nShow : i18n.i18nHide;
});

// Forms that need a confirmation: <form data-confirm="¿Seguro?">
document.addEventListener("submit", (event) => {
  const message = event.target.dataset.confirm;
  if (message && !window.confirm(message)) event.preventDefault();
});

// New table: dynamic column rows.
const columnList = document.querySelector("[data-columns]");
if (columnList) {
  const template = document.querySelector("#column-template");
  let next = Number(columnList.dataset.next || 0);

  const addColumn = () => {
    const html = template.innerHTML.replaceAll("__i__", String(next++));
    columnList.insertAdjacentHTML("beforeend", html);
    columnList.lastElementChild.querySelector("input").focus();
  };

  document.querySelector("[data-add-column]").addEventListener("click", addColumn);
  columnList.addEventListener("click", (event) => {
    const remove = event.target.closest("[data-remove-column]");
    if (remove) remove.closest(".col-editor").remove();
  });
  if (!columnList.children.length) addColumn();
}

// Lowercase + underscore identifiers while typing.
document.addEventListener("input", (event) => {
  if (!event.target.matches("[data-identifier]")) return;
  const input = event.target;
  const position = input.selectionStart;
  input.value = input.value.toLowerCase().replace(/[\s-]+/g, "_").replace(/[^a-z0-9_]/g, "");
  input.setSelectionRange(position, position);
});

// Light / dark theme. "system" (no stored value) follows the OS preference.
const THEME_KEY = "falcondb-theme";
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

const storedTheme = () => {
  try {
    return localStorage.getItem(THEME_KEY) || "system";
  } catch {
    return "system";
  }
};

const applyTheme = (choice) => {
  try {
    if (choice === "system") localStorage.removeItem(THEME_KEY);
    else localStorage.setItem(THEME_KEY, choice);
  } catch {
    // Storage unavailable: the choice lasts until the page is reloaded.
  }
  if (choice === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = choice;
  document.querySelectorAll('[data-theme-options] input[name="theme"]').forEach((input) => {
    input.checked = input.value === choice;
  });
};

const effectiveTheme = () => document.documentElement.dataset.theme || (systemDark.matches ? "dark" : "light");

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-theme-toggle]")) applyTheme(effectiveTheme() === "dark" ? "light" : "dark");
});
document.addEventListener("change", (event) => {
  if (event.target.matches('[data-theme-options] input[name="theme"]')) applyTheme(event.target.value);
});
applyTheme(storedTheme());

// Cookie consent: the choice ("all" or "essential") is kept for a year.
const CONSENT_COOKIE = "falcondb_cookie_consent";
const cookieBanner = document.querySelector("[data-cookie-banner]");

const setConsent = (choice) => {
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${CONSENT_COOKIE}=${choice}; Max-Age=31536000; Path=/; SameSite=Lax${secure}`;
  if (cookieBanner) cookieBanner.hidden = true;
};

document.addEventListener("click", (event) => {
  const choice = event.target.closest("[data-cookie-choice]");
  if (choice) setConsent(choice.dataset.cookieChoice);
  if (event.target.closest("[data-cookie-reset]")) {
    document.cookie = `${CONSENT_COOKIE}=; Max-Age=0; Path=/`;
    if (cookieBanner) cookieBanner.hidden = false;
  }
});
