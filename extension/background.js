// Keeps today's pageviews on the toolbar badge, refreshed every 30 minutes.
import { fetchAnalytics, loadState } from "./api.js";

const ALARM = "refresh-badge";

async function refreshBadge() {
  const state = await loadState();
  if (!state.token || !state.server) return chrome.action.setBadgeText({ text: "" });
  const { data, error } = await fetchAnalytics({ ...state, days: 7 });
  if (error) return chrome.action.setBadgeText({ text: error.status === 401 ? "!" : "" });
  const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
  chrome.action.setBadgeBackgroundColor({ color: "#2fa9a3" });
  chrome.action.setBadgeText({ text: data.today ? compact.format(data.today) : "" });
}

chrome.runtime.onInstalled.addListener(() => chrome.alarms.create(ALARM, { periodInMinutes: 30 }));
chrome.runtime.onStartup.addListener(refreshBadge);
chrome.alarms.onAlarm.addListener((alarm) => { if (alarm.name === ALARM) refreshBadge(); });
