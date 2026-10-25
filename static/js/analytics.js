// Analytics dashboard: daily area charts with a crosshair tooltip, and localized
// country names. Data comes from <script id="analytics-series" type="application/json">.
(() => {
  const dataNode = document.getElementById("analytics-series");
  const root = document.querySelector(".analytics");
  if (!dataNode || !root) return;

  const series = JSON.parse(dataNode.textContent);
  const lang = root.dataset.lang || document.documentElement.lang || "en";
  const SVG = "http://www.w3.org/2000/svg";
  const PLOT_HEIGHT = 160;
  const AXIS_BAND = 24;
  const PAD = { top: 12, right: 12, left: 40 };

  const dayLabel = new Intl.DateTimeFormat(lang, { month: "short", day: "numeric", timeZone: "UTC" });
  const longDay = new Intl.DateTimeFormat(lang, { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });
  const number = new Intl.NumberFormat(lang);
  const compact = new Intl.NumberFormat(lang, { notation: "compact", maximumFractionDigits: 1 });
  const asDate = (iso) => new Date(`${iso}T00:00:00Z`);

  // Country codes -> names in the interface language.
  try {
    const regions = new Intl.DisplayNames([lang], { type: "region" });
    document.querySelectorAll("[data-country-code]").forEach((node) => {
      node.textContent = regions.of(node.dataset.countryCode) || node.dataset.countryCode;
    });
  } catch {
    // Older browsers keep the ISO code.
  }

  const niceMax = (value) => {
    if (value <= 4) return 4;
    const magnitude = 10 ** Math.floor(Math.log10(value));
    const step = [1, 2, 2.5, 5, 10].find((s) => s * magnitude * 4 >= value) * magnitude;
    return step * 4;
  };

  const el = (name, attrs = {}) => {
    const node = document.createElementNS(SVG, name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };

  function draw(card) {
    const metric = card.dataset.areaChart;
    const title = card.querySelector("figcaption strong").textContent;
    const plot = card.querySelector(".chart-plot");
    const width = plot.clientWidth;
    if (!width) return;

    const values = series.map((point) => point[metric]);
    const max = niceMax(Math.max(...values, 0));
    const innerW = width - PAD.left - PAD.right;
    const x = (i) => PAD.left + (series.length === 1 ? innerW / 2 : (i * innerW) / (series.length - 1));
    const y = (v) => PAD.top + PLOT_HEIGHT - (v / max) * PLOT_HEIGHT;
    const height = PAD.top + PLOT_HEIGHT + AXIS_BAND;

    const svg = el("svg", { width, height, viewBox: `0 0 ${width} ${height}`, class: "area-chart", tabindex: "0",
                            "aria-label": `${title}: ${values.map((v, i) => `${series[i].date} ${v}`).join(", ")}` });

    // Gridlines + y ticks (0, ¼, ½, ¾, max): solid hairlines, recessive.
    for (let i = 0; i <= 4; i++) {
      const value = (max / 4) * i;
      const gy = y(value);
      svg.append(el("line", { x1: PAD.left, x2: width - PAD.right, y1: gy, y2: gy, class: i === 0 ? "axis" : "grid" }));
      const label = el("text", { x: PAD.left - 8, y: gy + 4, class: "tick", "text-anchor": "end" });
      label.textContent = compact.format(value);
      svg.append(label);
    }

    // X labels: first, last and a few in between, never closer than MIN_LABEL_GAP px.
    const MIN_LABEL_GAP = 64;
    const every = Math.max(1, Math.ceil(series.length / 6));
    series.forEach((point, i) => {
      if (i % every && i !== series.length - 1) return;
      if (i !== series.length - 1 && x(series.length - 1) - x(i) < MIN_LABEL_GAP) return;
      const anchor = i === 0 ? "start" : i === series.length - 1 ? "end" : "middle";
      const label = el("text", { x: x(i), y: PAD.top + PLOT_HEIGHT + 17, class: "tick", "text-anchor": anchor });
      label.textContent = dayLabel.format(asDate(point.date));
      svg.append(label);
    });

    const points = values.map((v, i) => `${x(i)},${y(v)}`);
    svg.append(el("path", { d: `M${x(0)},${y(0)} L${points.join(" L")} L${x(values.length - 1)},${y(0)} Z`, class: "area" }));
    svg.append(el("path", { d: `M${points.join(" L")}`, class: "line" }));

    // End marker with a surface ring, plus a direct label for the latest value.
    const last = values.length - 1;
    svg.append(el("circle", { cx: x(last), cy: y(values[last]), r: 4, class: "marker" }));

    // Crosshair layer.
    const cross = el("line", { y1: PAD.top, y2: PAD.top + PLOT_HEIGHT, class: "crosshair", visibility: "hidden" });
    const dot = el("circle", { r: 4, class: "marker", visibility: "hidden" });
    svg.append(cross, dot);

    const tooltip = document.createElement("div");
    tooltip.className = "chart-tooltip";
    tooltip.hidden = true;
    const strong = document.createElement("strong");
    const sub = document.createElement("span");
    tooltip.append(strong, sub);

    let active = last;
    const show = (i) => {
      active = Math.max(0, Math.min(last, i));
      const cx = x(active);
      const cy = y(values[active]);
      cross.setAttribute("x1", cx);
      cross.setAttribute("x2", cx);
      dot.setAttribute("cx", cx);
      dot.setAttribute("cy", cy);
      cross.setAttribute("visibility", "visible");
      dot.setAttribute("visibility", "visible");
      strong.textContent = number.format(values[active]);
      sub.textContent = `${title} · ${longDay.format(asDate(series[active].date))}`;
      tooltip.hidden = false;
      const left = Math.min(Math.max(cx - tooltip.offsetWidth / 2, 0), width - tooltip.offsetWidth);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${Math.max(cy - tooltip.offsetHeight - 12, 0)}px`;
    };
    const hide = () => {
      cross.setAttribute("visibility", "hidden");
      dot.setAttribute("visibility", "hidden");
      tooltip.hidden = true;
    };

    svg.addEventListener("pointermove", (event) => {
      const box = svg.getBoundingClientRect();
      const px = event.clientX - box.left - PAD.left;
      show(Math.round((px / innerW) * last));
    });
    svg.addEventListener("pointerleave", hide);
    svg.addEventListener("focus", () => show(active));
    svg.addEventListener("blur", hide);
    svg.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        show(active + (event.key === "ArrowRight" ? 1 : -1));
      }
    });

    plot.replaceChildren(svg, tooltip);
  }

  const cards = [...document.querySelectorAll("[data-area-chart]")];
  const redraw = () => cards.forEach(draw);
  redraw();
  if ("ResizeObserver" in window) {
    let frame;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(redraw);
    });
    cards.forEach((card) => observer.observe(card.querySelector(".chart-plot")));
  }
})();

// Filter forms that apply on change (project checkboxes).
document.querySelectorAll("form[data-auto-submit]").forEach((form) => {
  form.addEventListener("change", () => form.requestSubmit());
});
