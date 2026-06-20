/* ============================================================================
   IMJUVE · Panel de Administración — interactividad
   Sidebar (riel/drawer) · KPIs (count-up) · gráfica de tendencia (SVG) ·
   donut (SVG) · tooltips · tablas con búsqueda, orden y filtros por estatus.
   Sin dependencias externas. Respeta prefers-reduced-motion.
   ========================================================================== */
(function () {
  "use strict";

  const SVGNS = "http://www.w3.org/2000/svg";
  const PALETTE = ["#B30F34", "#BC955C", "#A67C45", "#8E3B49", "#D8BC8C"];
  const body = document.body;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const MOBILE = "(max-width: 860px)";
  const isMobile = () => window.matchMedia(MOBILE).matches;
  const svgEl = (n, attrs) => {
    const e = document.createElementNS(SVGNS, n);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  };
  const debounce = (fn, ms) => { let t; return function () { const a = arguments; clearTimeout(t); t = setTimeout(() => fn.apply(null, a), ms); }; };

  /* --------------------------- Sidebar -------------------------------- */
  (function sidebar() {
    const toggle = document.getElementById("navToggle");
    const scrim = document.getElementById("sidebarScrim");
    const KEY = "imjuve.sidebar.collapsed";
    try { if (localStorage.getItem(KEY) === "1" && !isMobile()) body.classList.add("sidebar-collapsed"); } catch (_) {}
    const closeDrawer = () => body.classList.remove("nav-open");
    if (toggle) toggle.addEventListener("click", function () {
      if (isMobile()) { body.classList.toggle("nav-open"); }
      else {
        body.classList.toggle("sidebar-collapsed");
        try { localStorage.setItem(KEY, body.classList.contains("sidebar-collapsed") ? "1" : "0"); } catch (_) {}
      }
    });
    if (scrim) scrim.addEventListener("click", closeDrawer);
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeDrawer(); });
    document.querySelectorAll(".nav__item").forEach(a => a.addEventListener("click", () => { if (isMobile()) closeDrawer(); }));
    window.matchMedia(MOBILE).addEventListener("change", e => { if (!e.matches) closeDrawer(); });
  })();

  /* --------------------------- Tooltip -------------------------------- */
  let tip;
  function showTip(html, x, y) {
    if (!tip) { tip = document.createElement("div"); tip.className = "viz-tip"; document.body.appendChild(tip); }
    tip.innerHTML = html;
    tip.style.left = (x + 12) + "px";
    tip.style.top = (y - 10) + "px";
    tip.classList.add("is-on");
  }
  function hideTip() { if (tip) tip.classList.remove("is-on"); }

  /* --------------------------- KPIs count-up -------------------------- */
  function countUp(el) {
    const target = parseInt(el.dataset.count, 10) || 0;
    if (reduce || target === 0) { el.textContent = target.toLocaleString("es-MX"); return; }
    const dur = 900, t0 = performance.now();
    (function tick(now) {
      const t = Math.min(1, (now - t0) / dur);
      el.textContent = Math.round(target * (1 - Math.pow(1 - t, 3))).toLocaleString("es-MX");
      if (t < 1) requestAnimationFrame(tick); else el.textContent = target.toLocaleString("es-MX");
    })(t0);
  }

  /* --------------------- Gráfica de tendencia (área) ------------------- */
  function renderTrend(host) {
    const pts = Array.from(host.querySelectorAll(".trend__pt"));
    if (!pts.length) return;
    host.querySelectorAll("svg, .trend__labels").forEach(n => n.remove());

    const vals = pts.map(p => parseFloat(p.dataset.v) || 0);
    const labels = pts.map(p => p.dataset.l || "");
    const max = parseFloat(host.dataset.max) || Math.max.apply(null, vals) || 1;
    const W = host.clientWidth || 600, H = 200;
    const pl = 14, pr = 14, pt = 22, pb = 14;
    const n = vals.length;
    const X = i => pl + (n === 1 ? (W - pl - pr) / 2 : i * (W - pl - pr) / (n - 1));
    const Y = v => (H - pb) - (v / max) * (H - pt - pb);

    const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none" });

    // Rejilla horizontal (3 líneas)
    const grid = svgEl("g", { class: "trend-grid" });
    for (let g = 0; g <= 2; g++) {
      const yy = pt + g * (H - pt - pb) / 2;
      grid.appendChild(svgEl("line", { x1: pl, y1: yy, x2: W - pr, y2: yy }));
    }
    svg.appendChild(grid);

    let line = `M ${X(0)} ${Y(vals[0])}`;
    for (let i = 1; i < n; i++) line += ` L ${X(i)} ${Y(vals[i])}`;
    const area = `M ${X(0)} ${H - pb} L ${X(0)} ${Y(vals[0])}` +
      vals.slice(1).map((v, i) => ` L ${X(i + 1)} ${Y(v)}`).join("") +
      ` L ${X(n - 1)} ${H - pb} Z`;

    svg.appendChild(svgEl("path", { d: area, class: "trend-area", fill: "rgba(106,27,41,.10)" }));
    const lineEl = svgEl("path", { d: line, class: "trend-line", "vector-effect": "non-scaling-stroke" });
    svg.appendChild(lineEl);

    vals.forEach((v, i) => {
      const dot = svgEl("circle", { cx: X(i), cy: Y(v), r: 4, class: "trend-dot", "vector-effect": "non-scaling-stroke" });
      dot.addEventListener("mousemove", e => showTip(`${labels[i]} · <b>${v}</b>`, e.clientX, e.clientY));
      dot.addEventListener("mouseleave", hideTip);
      svg.appendChild(dot);
    });

    host.appendChild(svg);
    const lab = document.createElement("div");
    lab.className = "trend__labels";
    labels.forEach(l => { const s = document.createElement("span"); s.textContent = l; lab.appendChild(s); });
    host.appendChild(lab);

    // Animación de "dibujo" de la línea + aparición del área.
    const area0 = svg.querySelector(".trend-area");
    if (reduce) { area0.classList.add("is-in"); return; }
    const len = lineEl.getTotalLength();
    lineEl.style.strokeDasharray = len;
    lineEl.style.strokeDashoffset = len;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      lineEl.style.strokeDashoffset = 0;
      area0.classList.add("is-in");
    }));
  }

  /* ------------------------------ Donut ------------------------------- */
  function renderDonut(host) {
    const segs = Array.from(host.querySelectorAll(".donut__seg"));
    if (!segs.length) return;
    host.querySelectorAll("svg, .donut__center").forEach(n => n.remove());

    const data = segs.map(s => ({ label: s.dataset.l || "", value: parseFloat(s.dataset.v) || 0 }));
    const total = data.reduce((a, d) => a + d.value, 0);
    const R = 15.915, C = 100; // circunferencia ≈ 100 => porcentajes directos

    const svg = svgEl("svg", { viewBox: "0 0 36 36" });
    svg.appendChild(svgEl("circle", { class: "track", cx: 18, cy: 18, r: R }));

    let acc = 0;
    data.forEach((d, i) => {
      if (total === 0) return;
      const pct = (d.value / total) * C;
      const seg = svgEl("circle", {
        class: "seg", cx: 18, cy: 18, r: R, stroke: PALETTE[i % PALETTE.length],
        "stroke-dasharray": reduce ? `${pct} ${C - pct}` : `0 ${C}`,
        "stroke-dashoffset": -acc,
      });
      seg.addEventListener("mousemove", e => showTip(`${d.label} · <b>${d.value}</b> (${Math.round(pct)}%)`, e.clientX, e.clientY));
      seg.addEventListener("mouseleave", hideTip);
      svg.appendChild(seg);
      if (!reduce) requestAnimationFrame(() => requestAnimationFrame(() => { seg.style.strokeDasharray = `${pct} ${C - pct}`; }));
      acc += pct;
    });
    host.appendChild(svg);

    const center = document.createElement("div");
    center.className = "donut__center";
    center.innerHTML = `<b>${total.toLocaleString("es-MX")}</b><small>registros</small>`;
    host.appendChild(center);

    const legend = host.closest(".donut-wrap") && host.closest(".donut-wrap").querySelector(".legend");
    if (legend) {
      legend.innerHTML = "";
      data.forEach((d, i) => {
        const li = document.createElement("li");
        li.innerHTML = `<span class="sw" style="background:${PALETTE[i % PALETTE.length]}"></span>` +
          `<span class="lg-label">${d.label}</span><span class="lg-val">${d.value}</span>`;
        legend.appendChild(li);
      });
    }
  }

  /* --------------- Tablas: búsqueda + filtro por estatus -------------- */
  const filterState = {};
  function applyFilter(sel) {
    const st = filterState[sel] || { q: "", status: "all" };
    document.querySelectorAll(sel).forEach(row => {
      if (row.querySelector(".empty")) return;
      const txt = (row.dataset.text || row.textContent).toLowerCase();
      const okQ = !st.q || txt.indexOf(st.q) !== -1;
      const okS = st.status === "all" || row.dataset.status === st.status;
      row.classList.toggle("row-hidden", !(okQ && okS));
    });
  }
  function initFilters() {
    document.querySelectorAll(".toolbar__search").forEach(inp => {
      const sel = inp.dataset.filterTarget; if (!sel) return;
      filterState[sel] = filterState[sel] || { q: "", status: "all" };
      inp.addEventListener("input", () => { filterState[sel].q = inp.value.trim().toLowerCase(); applyFilter(sel); });
    });
    document.querySelectorAll(".chip-filter").forEach(btn => {
      const sel = btn.dataset.filterRows; if (!sel) return;
      filterState[sel] = filterState[sel] || { q: "", status: "all" };
      btn.addEventListener("click", () => {
        filterState[sel].status = btn.dataset.statusFilter;
        document.querySelectorAll('.chip-filter[data-filter-rows="' + sel + '"]')
          .forEach(b => b.classList.toggle("is-active", b === btn));
        applyFilter(sel);
      });
    });
  }

  /* ----------------------- Tablas: ordenamiento ----------------------- */
  function cellVal(td, type) {
    if (!td) return type === "text" ? "" : 0;
    const raw = td.hasAttribute("data-value") ? td.getAttribute("data-value") : td.textContent.trim();
    if (type === "num" || type === "date") return parseFloat(raw) || 0;
    return raw.toLowerCase();
  }
  function initSort() {
    document.querySelectorAll(".js-table").forEach(table => {
      const ths = Array.from(table.querySelectorAll("thead th[data-sort]"));
      ths.forEach((th, idx) => th.addEventListener("click", () => {
        const type = th.dataset.sort;
        const asc = !th.classList.contains("sort-asc");
        ths.forEach(h => h.classList.remove("sort-asc", "sort-desc"));
        th.classList.add(asc ? "sort-asc" : "sort-desc");
        const tbody = table.querySelector("tbody");
        const rows = Array.from(tbody.querySelectorAll("tr")).filter(r => !r.querySelector(".empty"));
        rows.sort((a, b) => {
          const av = cellVal(a.children[idx], type), bv = cellVal(b.children[idx], type);
          return av < bv ? (asc ? -1 : 1) : av > bv ? (asc ? 1 : -1) : 0;
        });
        rows.forEach(r => tbody.appendChild(r));
      }));
    });
  }

  /* ------------------------------- Init ------------------------------- */
  function renderViz() {
    document.querySelectorAll(".trend").forEach(renderTrend);
    document.querySelectorAll(".donut").forEach(renderDonut);
  }
  document.querySelectorAll(".kpi__num[data-count]").forEach(countUp);
  renderViz();
  initFilters();
  initSort();
  window.addEventListener("resize", debounce(renderViz, 200));
})();
