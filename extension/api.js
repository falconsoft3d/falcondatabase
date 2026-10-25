// Small client for the falcondatabase account API, shared by the popup and the background worker.
import { DEFAULT_SERVER } from "./config.js";

const KEY = "falcondb";

export async function loadState() {
  const { [KEY]: state } = await chrome.storage.local.get(KEY);
  return { server: DEFAULT_SERVER, token: null, user: null, days: 7, project: "", ...(state || {}) };
}

export async function saveState(changes) {
  const state = { ...(await loadState()), ...changes };
  await chrome.storage.local.set({ [KEY]: state });
  return state;
}

// Chrome host patterns have no port; a pattern without one covers every port.
export function originPattern(server) {
  const url = new URL(server);
  return `${url.protocol}//${url.hostname}/*`;
}

export function normalizeServer(url) {
  const value = (url || "").trim().replace(/\/+$/, "");
  return /^https?:\/\//.test(value) ? value : value ? `https://${value}` : "";
}

async function call(server, path, { method = "GET", token, body } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body) headers["Content-Type"] = "application/json";
  try {
    const response = await fetch(`${server}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
    const data = await response.json().catch(() => ({}));
    return response.ok ? { data, error: null } : { data, error: { status: response.status, message: data.error || response.statusText } };
  } catch (err) {
    return { data: null, error: { status: 0, message: err.message } };
  }
}

export const signIn = (server, username, password, code) =>
  call(server, "/api/account/token", { method: "POST", body: { username, password, code } });

export const fetchAnalytics = (state) => {
  const query = new URLSearchParams({ days: state.days });
  if (state.project) query.set("p", state.project);
  return call(state.server, `/api/account/analytics?${query}`, { token: state.token });
};
