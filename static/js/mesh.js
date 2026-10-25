// Animated triangle mesh behind the home hero. The vertices drift slowly and
// open up around the pointer. Colors come from the CSS palette, so it follows
// the light/dark theme. Respects prefers-reduced-motion (drawn once, static).
(() => {
  const hero = document.querySelector("[data-mesh]");
  if (!hero) return;
  const canvas = document.createElement("canvas");
  canvas.className = "hero-mesh";
  canvas.setAttribute("aria-hidden", "true");
  hero.prepend(canvas);
  const ctx = canvas.getContext("2d");

  const CELL = 78;            // average triangle size (px)
  const OPEN_RADIUS = 220;    // how far the mesh opens around the pointer
  const OPEN_FORCE = 120;     // how much the vertices are pushed away
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  let width = 0, height = 0, cols = 0, rows = 0, points = [];
  let colors = {};
  const pointer = { x: 0, y: 0, inside: false, strength: 0 };
  let visible = true, frame = null;

  function readColors() {
    const style = getComputedStyle(document.documentElement);
    const light = document.documentElement.dataset.theme === "light" ||
      (!document.documentElement.dataset.theme && window.matchMedia("(prefers-color-scheme: light)").matches);
    colors = {
      a: style.getPropertyValue("--pink").trim() || "#ED637D",
      b: style.getPropertyValue("--turquoise").trim() || "#66D7D1",
      line: light ? "rgba(17, 122, 116, 0.22)" : "rgba(102, 215, 209, 0.22)",
      fill: light ? 0.10 : 0.09,
    };
  }

  function hexToRgb(hex) {
    const n = parseInt(hex.replace("#", ""), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function build() {
    const box = hero.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    width = box.width;
    height = box.height;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cols = Math.ceil(width / CELL) + 2;
    rows = Math.ceil(height / (CELL * 0.87)) + 2;
    points = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const offset = r % 2 ? CELL / 2 : 0;   // staggered rows -> near-equilateral triangles
        points.push({
          bx: (c - 1) * CELL + offset + (Math.random() - 0.5) * CELL * 0.45,
          by: (r - 1) * CELL * 0.87 + (Math.random() - 0.5) * CELL * 0.45,
          phase: Math.random() * Math.PI * 2,
          speed: 0.35 + Math.random() * 0.4,
          x: 0, y: 0,
        });
      }
    }
  }

  function move(time) {
    const t = time / 1000;
    for (const p of points) {
      let x = p.bx + Math.sin(t * p.speed + p.phase) * 6;
      let y = p.by + Math.cos(t * p.speed * 0.8 + p.phase) * 6;
      if (pointer.strength > 0.001) {
        const dx = x - pointer.x, dy = y - pointer.y;
        const dist = Math.hypot(dx, dy) || 1;
        if (dist < OPEN_RADIUS) {
          const falloff = 1 - dist / OPEN_RADIUS;
          const push = falloff * falloff * (3 - 2 * falloff) * OPEN_FORCE * pointer.strength;  // smoothstep
          x += (dx / dist) * push;
          y += (dy / dist) * push;
        }
      }
      p.x = x;
      p.y = y;
    }
  }

  function draw() {
    ctx.clearRect(0, 0, width, height);
    const a = hexToRgb(colors.a), b = hexToRgb(colors.b);
    ctx.lineWidth = 1;
    ctx.strokeStyle = colors.line;
    const at = (r, c) => points[r * cols + c];
    for (let r = 0; r < rows - 1; r++) {
      for (let c = 0; c < cols - 1; c++) {
        const odd = r % 2;
        const tris = odd
          ? [[at(r, c), at(r + 1, c), at(r + 1, c + 1)], [at(r, c), at(r, c + 1), at(r + 1, c + 1)]]
          : [[at(r, c), at(r + 1, c), at(r, c + 1)], [at(r, c + 1), at(r + 1, c), at(r + 1, c + 1)]];
        for (const [p1, p2, p3] of tris) {
          const cx = (p1.x + p2.x + p3.x) / 3;
          const cy = (p1.y + p2.y + p3.y) / 3;
          const mix = Math.min(1, Math.max(0, cx / width * 0.8 + cy / height * 0.2));
          // Triangles near the pointer glow a little brighter while the mesh is open.
          const glow = pointer.strength > 0.001
            ? Math.max(0, 1 - Math.hypot(cx - pointer.x, cy - pointer.y) / (OPEN_RADIUS * 1.6)) * pointer.strength
            : 0;
          const alpha = colors.fill * (0.55 + 0.45 * Math.sin(cx * 0.013 + cy * 0.017)) + glow * 0.22;
          const rgb = a.map((v, i) => Math.round(v + (b[i] - v) * mix));
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.lineTo(p3.x, p3.y);
          ctx.closePath();
          ctx.fillStyle = `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${alpha.toFixed(3)})`;
          ctx.fill();
          ctx.stroke();
        }
      }
    }
  }

  function tick(time) {
    // Ease the opening in and out instead of snapping.
    pointer.strength += ((pointer.inside ? 1 : 0) - pointer.strength) * 0.08;
    move(time);
    draw();
    frame = visible && !reduceMotion.matches ? requestAnimationFrame(tick) : null;
  }

  function start() {
    if (frame === null && visible && !reduceMotion.matches) frame = requestAnimationFrame(tick);
    if (reduceMotion.matches) { move(0); draw(); }
  }

  hero.addEventListener("pointermove", (event) => {
    const box = hero.getBoundingClientRect();
    pointer.x = event.clientX - box.left;
    pointer.y = event.clientY - box.top;
    pointer.inside = true;
  });
  hero.addEventListener("pointerleave", () => { pointer.inside = false; });

  new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    start();
  }).observe(hero);

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { build(); start(); }, 150);
  });
  // Re-read the palette when the theme changes.
  new MutationObserver(() => { readColors(); if (reduceMotion.matches) draw(); })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  window.matchMedia("(prefers-color-scheme: light)").addEventListener("change", readColors);
  reduceMotion.addEventListener("change", start);

  readColors();
  build();
  start();
})();
