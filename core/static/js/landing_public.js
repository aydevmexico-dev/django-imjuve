/* ============================================================================
   IMJUVE · Landing pública — comportamiento del cliente.
   · Conmuta mapa (programas/eventos) ↔ tarjetas (descuentos) con los tabs.
   · Mapa Leaflet con marcadores por centroide estatal y búsqueda en vivo (/api/buscar/).
   · Carrusel de avisos: autoavance con pausa al pasar el cursor; respeta reduce-motion.
   Vanilla, sin dependencias salvo Leaflet. Sin estilos inline (las clases viven en CSS).
   ========================================================================== */
(function () {
  "use strict";

  var MEXICO_CENTER = [23.6, -102.5];
  var KIND_COLOR = { programa: "#B30F34", evento: "#A67C45" }; // guinda / dorado
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function $(id) { return document.getElementById(id); }
  function readJSON(id) {
    var el = $(id);
    try { return el ? JSON.parse(el.textContent) : []; } catch (_) { return []; }
  }
  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }

  var initial = { programas: readJSON("data-programas"), descuentos: readJSON("data-descuentos") };

  var searchInput = $("lp-search-input");
  var statusEl = $("lp-search-status");
  var vistaMapa = $("territorio");
  var vistaDesc = $("lp-discounts");
  var cardsGrid = $("lp-cards");
  var cardsEmpty = $("lp-cards-empty");

  var currentTipo = "programas";

  /* ----------------------------------------------------------------- Mapa */
  var map, markersLayer, mapReady = false;
  function ensureMap() {
    if (typeof L === "undefined") return false;
    if (mapReady) { map.invalidateSize(); return true; }
    map = L.map("lp-map", { scrollWheelZoom: false }).setView(MEXICO_CENTER, 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    markersLayer = L.layerGroup().addTo(map);
    mapReady = true;
    map.invalidateSize();
    return true;
  }

  function dateRange(start, end) {
    if (start && end) return "Del " + start + " al " + end;
    if (start) return "Desde " + start;
    if (end) return "Hasta " + end;
    return "Vigencia abierta";
  }
  // Desfase determinista para que varios marcadores del mismo estado no se encimen.
  function jitter(v, i, salt) {
    var k = ((i + 1) * (salt === "lat" ? 0.013 : 0.017)) % 0.18;
    return v + (i % 2 === 0 ? k : -k);
  }

  function renderMarkers(items) {
    if (!ensureMap()) return;
    markersLayer.clearLayers();
    items.forEach(function (it, i) {
      if (typeof it.lat !== "number" || typeof it.lng !== "number") return;
      var color = KIND_COLOR[it.kind] || "#6B0A20";
      var marker = L.circleMarker([jitter(it.lat, i, "lat"), jitter(it.lng, i, "lng")], {
        radius: 8, color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.95,
      });
      var tipo = it.kind === "evento" ? "Evento" : "Programa";
      var loc = [it.municipality, it.state].filter(Boolean).join(", ");
      marker.bindPopup(
        "<strong>" + escapeHtml(it.name) + "</strong><br>" +
        '<span style="color:' + color + '">&#9679;</span> ' + tipo +
        (loc ? "<br>" + escapeHtml(loc) : "") +
        "<br><small>" + escapeHtml(dateRange(it.start_date, it.end_date)) + "</small>"
      );
      markersLayer.addLayer(marker);
    });
  }

  /* ----------------------------------------------------- Tarjetas de descuentos */
  function buildCard(p) {
    var loc = [p.city, p.municipality, p.state].filter(Boolean).join(", ") || "A nivel nacional";
    var initialLetter = (p.company || "?").charAt(0).toUpperCase();
    var logo = p.logo_url
      ? '<img src="' + encodeURI(p.logo_url) + '" alt="' + escapeHtml(p.company) + '">'
      : escapeHtml(initialLetter);
    var badge = p.active
      ? '<span class="lp-badge lp-badge--on">Activo</span>'
      : '<span class="lp-badge lp-badge--off">Inactivo</span>';
    var card = document.createElement("article");
    card.className = "lp-card";
    card.innerHTML =
      '<div class="lp-card__top">' +
        '<div class="lp-card__logo">' + logo + "</div>" +
        "<div>" +
          '<span class="lp-card__co">' + escapeHtml(p.company) + "</span>" +
          '<h4 class="lp-card__name">' + escapeHtml(p.name) + "</h4>" +
          '<p class="lp-card__desc">' + escapeHtml(p.description) + "</p>" +
        "</div>" +
      "</div>" +
      '<div class="lp-card__foot"><span>' + escapeHtml(loc) + "</span>" + badge + "</div>";
    return card;
  }

  function renderCards(items) {
    cardsGrid.innerHTML = "";
    if (!items.length) { cardsEmpty.hidden = false; return; }
    cardsEmpty.hidden = true;
    var frag = document.createDocumentFragment();
    items.forEach(function (p) { frag.appendChild(buildCard(p)); });
    cardsGrid.appendChild(frag);
  }

  function render(tipo, items) {
    if (tipo === "descuentos") renderCards(items);
    else renderMarkers(items);
    statusEl.textContent = items.length + " resultado" + (items.length === 1 ? "" : "s");
  }

  /* --------------------------------------------------------- Búsqueda backend */
  var reqToken = 0;
  function runSearch() {
    var tipo = currentTipo, q = searchInput.value.trim(), token = ++reqToken;
    statusEl.textContent = "Buscando…";
    fetch("/api/buscar/?tipo=" + encodeURIComponent(tipo) + "&q=" + encodeURIComponent(q),
          { headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { return r.json(); })
      .then(function (data) { if (token === reqToken) render(tipo, data.results || []); })
      .catch(function () { if (token === reqToken) statusEl.textContent = "No se pudo completar la búsqueda. Intenta de nuevo."; });
  }

  /* ------------------------------------------------------------- Conmutar vista */
  function toggleVista(valor) {
    currentTipo = valor;
    var isDesc = valor === "descuentos";
    vistaDesc.classList.toggle("is-hidden", !isDesc);
    vistaMapa.classList.toggle("is-hidden", isDesc);
    searchInput.placeholder = isDesc
      ? "Busca por empresa, promoción, sector o ubicación…"
      : "Busca por estado, municipio, ciudad, C.P. o palabra clave…";
    if (!isDesc) ensureMap();
    if (!searchInput.value.trim()) render(valor, initial[valor] || []);
    else runSearch();
  }

  /* ------------------------------------------------------------- Carrusel avisos */
  function initCarousel() {
    var track = $("lp-promo-track"), dotsWrap = $("lp-promo-dots");
    if (!track) return;
    var slides = Array.prototype.slice.call(track.children);
    if (slides.length < 2) return;
    var idx = 0, timer = null;

    slides.forEach(function (_, i) {
      var dot = document.createElement("button");
      dot.className = "lp-promo__dot";
      dot.setAttribute("role", "tab");
      dot.setAttribute("aria-label", "Aviso " + (i + 1));
      dot.addEventListener("click", function () { go(i, true); });
      dotsWrap.appendChild(dot);
    });
    var dots = Array.prototype.slice.call(dotsWrap.children);

    function paint() {
      dots.forEach(function (d, i) { d.setAttribute("aria-current", i === idx ? "true" : "false"); });
    }
    function go(i, user) {
      idx = (i + slides.length) % slides.length;
      track.scrollTo({ left: slides[idx].offsetLeft - track.offsetLeft, behavior: reduceMotion ? "auto" : "smooth" });
      paint();
      if (user) restart();
    }
    function next() { go(idx + 1); }
    function start() { if (!reduceMotion) timer = setInterval(next, 6000); }
    function stop() { if (timer) { clearInterval(timer); timer = null; } }
    function restart() { stop(); start(); }

    // Sincroniza los puntos cuando el usuario desliza manualmente.
    track.addEventListener("scroll", debounce(function () {
      var nearest = 0, best = Infinity;
      slides.forEach(function (s, i) {
        var d = Math.abs(s.offsetLeft - track.offsetLeft - track.scrollLeft);
        if (d < best) { best = d; nearest = i; }
      });
      if (nearest !== idx) { idx = nearest; paint(); }
    }, 120));

    track.addEventListener("mouseenter", stop);
    track.addEventListener("mouseleave", start);
    track.addEventListener("focusin", stop);
    track.addEventListener("focusout", start);

    paint();
    start();
  }

  /* ------------------------------------------------------------------- Arranque */
  function boot() {
    document.querySelectorAll('input[name="tipo_busqueda"]').forEach(function (radio) {
      radio.addEventListener("change", function () { toggleVista(this.value); });
    });
    searchInput.addEventListener("input", debounce(runSearch, 250));
    initCarousel();
    // Tras un cambio de tamaño, Leaflet recalcula sus tiles para no quedar recortado.
    window.addEventListener("resize", debounce(function () { if (mapReady) map.invalidateSize(); }, 200));
    // Vista inicial: programas con los datos embebidos (sin pegarle al backend).
    ensureMap();
    render("programas", initial.programas);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
