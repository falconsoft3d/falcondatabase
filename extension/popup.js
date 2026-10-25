import { DEFAULT_SERVER } from "./config.js";
import { fetchAnalytics, loadState, normalizeServer, originPattern, saveState, signIn } from "./api.js";

const $ = (id) => document.getElementById(id);
const t = (key, ...subs) => chrome.i18n.getMessage(key, subs) || key;
const lang = chrome.i18n.getUILanguage();
const number = new Intl.NumberFormat(lang, { notation: "compact", maximumFractionDigits: 1 });
const dayLabel = new Intl.DateTimeFormat(lang, { month: "short", day: "numeric", timeZone: "UTC" });
let regions = null;
try { regions = new Intl.DisplayNames([lang], { type: "region" }); } catch { /* keep codes */ }

document.querySelectorAll("[data-i18n]").forEach((node) => { node.textContent = t(node.dataset.i18n); });
document.querySelectorAll("[data-i18n-title]").forEach((node) => { node.title = node.ariaLabel = t(node.dataset.i18nTitle); });

function showLogin(message) {
  $("stats").hidden = true;
  $("sign-out").hidden = true;
  $("who").textContent = "";
  $("login").hidden = false;
  $("login-error").hidden = !message;
  $("login-error").textContent = message || "";
}

// --- sign in ----------------------------------------------------------------
$("login").addEventListener("submit", async (event) => {
  event.preventDefault();
  const server = normalizeServer($("server").value);
  // Ask for access to the server inside the click (Chrome requires a user gesture).
  const granted = await chrome.permissions.request({ origins: [originPattern(server)] }).catch(() => false);
  if (!granted) return showLogin(t("permissionDenied"));
  const { data, error } = await signIn(server, $("username").value, $("password").value, $("code").value);
  if (error) {
    $("code-field").hidden = !(data && data.two_factor_required);
    if (data && data.two_factor_required) $("code").focus();
    return showLogin(error.message);
  }
  $("password").value = "";
  $("code").value = "";
  await saveState({ server, token: data.token, user: data.user, project: "" });
  render();
});

$("sign-out").addEventListener("click", async () => {
  await saveState({ token: null, user: null });
  chrome.action.setBadgeText({ text: "" });
  showLogin();
});

// --- statistics ------------------------------------------------------------
function delta(change, higherIsBetter) {
  const span = document.createElement("span");
  if (change === null || change === undefined) {
    span.className = "muted";
    span.textContent = "—";
  } else {
    const good = change === 0 ? null : (change > 0) === higherIsBetter;
    span.className = good === null ? "muted" : good ? "good" : "bad";
    span.textContent = `${change > 0 ? "↑" : change < 0 ? "↓" : ""} ${Math.abs(change)}%`;
  }
  return span;
}

function renderKpis(report) {
  const labels = { visitors: "visitors", sessions: "sessions", pageviews: "pageviews", bounce_rate: "bounceRate" };
  const box = $("kpis");
  box.replaceChildren();
  for (const kpi of report.kpis.filter((k) => k.key in labels)) {
    const tile = document.createElement("div");
    tile.className = "kpi";
    const label = document.createElement("div");
    label.className = "label";
    label.textContent = t(labels[kpi.key]);
    const value = document.createElement("div");
    value.className = "value";
    value.textContent = kpi.value === null ? "—" : kpi.key === "bounce_rate" ? `${kpi.value}%` : number.format(kpi.value);
    const deltaRow = document.createElement("div");
    deltaRow.className = "delta muted";
    deltaRow.append(delta(kpi.change, kpi.higher_is_better), ` ${t("vsPrevious")}`);
    tile.append(label, value, deltaRow);
    box.append(tile);
  }
}

function renderChart(series) {
  const svg = $("chart");
  const width = svg.clientWidth || 340;
  const height = 110;
  const pad = { top: 8, bottom: 18, left: 4, right: 6 };
  const values = series.map((p) => p.pageviews);
  const max = Math.max(4, ...values);
  const x = (i) => pad.left + (series.length > 1 ? (i * (width - pad.left - pad.right)) / (series.length - 1) : 0);
  const y = (v) => pad.top + (height - pad.top - pad.bottom) * (1 - v / max);
  const ns = "http://www.w3.org/2000/svg";
  const el = (name, attrs) => {
    const node = document.createElementNS(ns, name);
    Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
    return node;
  };
  svg.replaceChildren();
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.append(el("line", { x1: pad.left, x2: width - pad.right, y1: y(0), y2: y(0), class: "grid" }));
  const points = values.map((v, i) => `${x(i)},${y(v)}`).join(" L");
  svg.append(el("path", { d: `M${x(0)},${y(0)} L${points} L${x(values.length - 1)},${y(0)} Z`, class: "area" }));
  svg.append(el("path", { d: `M${points}`, class: "line" }));
  const last = values.length - 1;
  for (const [i, anchor] of [[0, "start"], [last, "end"]]) {
    const tick = el("text", { x: x(i), y: height - 4, class: "tick", "text-anchor": anchor });
    tick.textContent = dayLabel.format(new Date(`${series[i].date}T00:00:00Z`));
    svg.append(tick);
  }
  const cross = el("line", { y1: pad.top, y2: y(0), class: "cross", visibility: "hidden" });
  const dot = el("circle", { r: 4, class: "dot", cx: x(last), cy: y(values[last]) });
  svg.append(cross, dot);
  const readout = (i) => {
    $("readout").textContent = `${dayLabel.format(new Date(`${series[i].date}T00:00:00Z`))} · ${values[i].toLocaleString(lang)}`;
  };
  readout(last);
  svg.onpointermove = (event) => {
    const box = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(last, Math.round(((event.clientX - box.left - pad.left) / (box.width - pad.left - pad.right)) * last)));
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", x(i)); dot.setAttribute("cy", y(values[i]));
    readout(i);
  };
  svg.onpointerleave = () => {
    cross.setAttribute("visibility", "hidden");
    dot.setAttribute("cx", x(last)); dot.setAttribute("cy", y(values[last]));
    readout(last);
  };
}

function renderBars(list, rows, labelOf) {
  list.replaceChildren();
  if (!rows.length) {
    const empty = document.createElement("li");
    empty.className = "muted small";
    empty.textContent = t("noData");
    return list.append(empty);
  }
  for (const row of rows.slice(0, 5)) {
    const item = document.createElement("li");
    const line = document.createElement("div");
    line.className = "row";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = labelOf(row);
    const num = document.createElement("span");
    num.className = "num muted";
    num.textContent = `${number.format(row.value)} · ${row.share}%`;
    line.append(name, num);
    const track = document.createElement("div");
    track.className = "track";
    const fill = document.createElement("span");
    fill.className = "fill";
    fill.style.width = `${row.width}%`;
    track.append(fill);
    item.append(line, track);
    list.append(item);
  }
}

const flag = (code) => (code && code.length === 2 ? String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1f1a5 + c.charCodeAt(0))) : "");
const countryName = (code) => (code ? `${flag(code)} ${(regions && regions.of(code)) || code}` : "—");

function fillSelect(select, options, selected) {
  select.replaceChildren(...options.map(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    option.selected = String(value) === String(selected);
    return option;
  }));
}

let lastRequest = 0;

function clearReport() {
  $("kpis").replaceChildren();
  $("chart").replaceChildren();
  $("readout").textContent = "";
  ["pages", "sources", "countries"].forEach((id) => $(id).replaceChildren());
  $("today").textContent = "";
}

async function render() {
  const request = ++lastRequest;
  const state = await loadState();
  if (!state.token) {
    $("server").value = state.server || DEFAULT_SERVER;
    return showLogin();
  }
  $("login").hidden = true;
  $("stats").hidden = false;
  $("sign-out").hidden = false;
  $("who").textContent = state.user ? state.user.username : "";
  $("status").textContent = t("loading");
  $("stats").style.opacity = ".6";   // keep the previous render while loading
  $("refresh").disabled = true;
  $("refresh").classList.add("spinning");

  const { data, error } = await fetchAnalytics(state);
  if (request !== lastRequest) return;   // a newer request (another filter or a refresh) is on its way
  $("stats").style.opacity = "";
  $("refresh").disabled = false;
  $("refresh").classList.remove("spinning");
  if (error) {
    if (error.status === 401) {
      await saveState({ token: null });
      return showLogin(t("sessionExpired"));
    }
    clearReport();   // don't leave another project's numbers on screen
    $("status").textContent = error.message;
    return;
  }
  // The server falls back to all projects when the selected one no longer exists.
  if (state.project && data.selected !== state.project) await saveState({ project: "" });
  $("status").textContent = data.report.totals.pageviews ? "" : t("noData");
  fillSelect($("project"), [["", t("allProjects")], ...data.projects.map((p) => [p.ref, p.name])], data.selected);
  fillSelect($("days"), [7, 14, 30, 90].map((d) => [d, t("days", String(d))]), state.days);
  renderKpis(data.report);
  renderChart(data.report.series);
  renderBars($("pages"), data.report.pages, (r) => `${r.hostname}${r.path}`);
  renderBars($("sources"), data.report.sources, (r) => r.source || "—");
  renderBars($("countries"), data.report.countries, (r) => countryName(r.country));
  $("today").textContent = t("today", number.format(data.today));
  $("open").href = data.links.analytics + (state.project ? `?p=${encodeURIComponent(state.project)}` : "");
  chrome.action.setBadgeBackgroundColor({ color: "#2fa9a3" });
  chrome.action.setBadgeText({ text: data.today ? number.format(data.today) : "" });
}

$("project").addEventListener("change", async (e) => { await saveState({ project: e.target.value }); render(); });
$("days").addEventListener("change", async (e) => { await saveState({ days: Number(e.target.value) }); render(); });
$("refresh").addEventListener("click", () => render());

render();
