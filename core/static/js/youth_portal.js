/* ============================================================================
   IMJUVE · Portal Joven — interacción del cliente
   · Detalle bajo demanda: click en tarjeta -> fetch del fragmento -> modal + carrusel.
   · Buscador superior: filtra tarjetas (listados) o repinta el mapa (vista mapa).
   · Mapa Leaflet con refresco AJAX por búsqueda + categoría.
   · Enlaces externos (convocatorias/descargas) siempre en pestaña nueva.
   Vanilla, sin dependencias (salvo Leaflet en la vista de mapa). El init corre en
   DOMContentLoaded para garantizar que Leaflet (cargado en extra_js) ya esté disponible.
   ========================================================================== */
(function () {
  "use strict";

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function debounce(fn, ms) {
    var t;
    return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); };
  }

  /* ----------------------- Enlaces externos en pestaña nueva ----------- */
  function hardenExternalLinks(root) {
    (root || document).querySelectorAll("a[data-external], a[target='_blank']").forEach(function (a) {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    });
  }

  /* ------------------------------- Carrusel ---------------------------- */
  function initCarousels(root) {
    (root || document).querySelectorAll("[data-carousel]").forEach(function (car) {
      var slides = Array.prototype.slice.call(car.querySelectorAll(".ycarousel__slide"));
      if (slides.length < 2) return;
      var idx = 0;
      function show(n) {
        idx = (n + slides.length) % slides.length;
        slides.forEach(function (s, i) { s.classList.toggle("is-active", i === idx); });
      }
      var prev = car.querySelector("[data-carousel-prev]");
      var next = car.querySelector("[data-carousel-next]");
      if (prev) prev.addEventListener("click", function () { show(idx - 1); });
      if (next) next.addEventListener("click", function () { show(idx + 1); });
    });
  }

  /* -------------------------- Modal de detalle ------------------------- */
  function initModal() {
    var modal = document.getElementById("yModal");
    var body = document.getElementById("yModalBody");
    if (!modal || !body) return;

    function open() { modal.hidden = false; document.body.classList.add("ymodal-open"); }
    function close() { modal.hidden = true; document.body.classList.remove("ymodal-open"); body.innerHTML = ""; }

    function loadDetail(url) {
      body.innerHTML = '<p class="empty">Cargando…</p>';
      open();
      fetch(url, { headers: { "X-Requested-With": "fetch" } })
        .then(function (r) { return r.ok ? r.text() : Promise.reject(); })
        .then(function (html) {
          body.innerHTML = html;
          initCarousels(body);
          hardenExternalLinks(body);
        })
        .catch(function () { body.innerHTML = '<p class="empty">No se pudo cargar el detalle.</p>'; });
    }

    // Delegación: cualquier tarjeta con data-detail-url abre el modal.
    document.addEventListener("click", function (e) {
      var card = e.target.closest("[data-detail-url]");
      if (card) { e.preventDefault(); loadDetail(card.dataset.detailUrl); }
      if (e.target.closest("[data-ymodal-close]")) close();
    });
    // Activación por teclado en las tarjetas (role="button").
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !modal.hidden) close();
      if ((e.key === "Enter" || e.key === " ")) {
        var card = e.target.closest && e.target.closest("[data-detail-url]");
        if (card) { e.preventDefault(); loadDetail(card.dataset.detailUrl); }
      }
    });
  }

  /* --------------------- Filtro de tarjetas (listados) ----------------- */
  function initCardSearch(searchInput) {
    var grid = document.getElementById("yCards");
    var empty = document.getElementById("yCardsEmpty");
    if (!grid) return false;
    var items = Array.prototype.slice.call(grid.children);
    function apply() {
      var q = searchInput.value.trim().toLowerCase();
      var visible = 0;
      items.forEach(function (el) {
        var hay = (el.getAttribute("data-search") || el.textContent).toLowerCase();
        var ok = !q || hay.indexOf(q) !== -1;
        el.style.display = ok ? "" : "none";
        if (ok) visible++;
      });
      if (empty) empty.hidden = visible !== 0;
    }
    searchInput.addEventListener("input", debounce(apply, 150));
    return true;
  }

  /* --------------------------- Mapa interactivo ------------------------ */
  var KIND_COLOR = { programa: "#16a34a", evento: "#2563eb" };
  var MEXICO_CENTER = [23.6, -102.5];

  function dateRange(start, end) {
    if (start && end) return "Del " + start + " al " + end;
    if (start) return "Desde " + start;
    if (end) return "Hasta " + end;
    return "Vigencia abierta";
  }
  function jitter(value, index, salt) {
    var k = ((index + 1) * (salt === "lat" ? 0.013 : 0.017)) % 0.18;
    return value + (index % 2 === 0 ? k : -k);
  }

  function initMap(searchInput) {
    var card = document.querySelector(".ymap-card[data-map-url]");
    var mapEl = document.getElementById("map");
    if (!card || !mapEl || typeof L === "undefined") return false;

    var url = card.dataset.mapUrl;
    var status = document.getElementById("yMapStatus");
    var cat = "all";

    var map = L.map("map", { scrollWheelZoom: false }).setView(MEXICO_CENTER, 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    var markers = L.layerGroup().addTo(map);

    function render(items) {
      markers.clearLayers();
      items.forEach(function (it, i) {
        if (typeof it.lat !== "number" || typeof it.lng !== "number") return;
        var color = KIND_COLOR[it.kind] || "#6A1B29";
        var marker = L.circleMarker([jitter(it.lat, i, "lat"), jitter(it.lng, i, "lng")], {
          radius: 8, color: "#ffffff", weight: 2, fillColor: color, fillOpacity: 0.95,
        });
        var tipo = it.kind === "evento" ? "Evento" : "Programa";
        var loc = [it.municipality, it.state].filter(Boolean).join(", ");
        marker.bindPopup(
          "<strong>" + escapeHtml(it.name) + "</strong><br>" + tipo +
          (loc ? "<br>" + escapeHtml(loc) : "") +
          "<br><small>" + escapeHtml(dateRange(it.start_date, it.end_date)) + "</small>"
        );
        markers.addLayer(marker);
      });
    }

    var token = 0;
    function load() {
      var q = searchInput ? searchInput.value.trim() : "";
      var t = ++token;
      if (status) status.textContent = "Cargando…";
      var full = url + "?cat=" + encodeURIComponent(cat) + "&q=" + encodeURIComponent(q);
      fetch(full, { headers: { "X-Requested-With": "fetch" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (t !== token) return;
          render(data.results || []);
          if (status) status.textContent = (data.count || 0) + " resultado" + (data.count === 1 ? "" : "s");
        })
        .catch(function () { if (t === token && status) status.textContent = "No se pudo cargar el mapa."; });
    }

    card.querySelectorAll("[data-map-cat]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        cat = btn.dataset.mapCat;
        card.querySelectorAll("[data-map-cat]").forEach(function (b) { b.classList.toggle("is-active", b === btn); });
        load();
      });
    });
    if (searchInput) searchInput.addEventListener("input", debounce(load, 250));

    map.invalidateSize();
    load();
    return true;
  }

  /* -------------------------------- Init ------------------------------- */
  function init() {
    hardenExternalLinks(document);
    initCarousels(document);
    initModal();

    var searchInput = document.getElementById("ySearch");
    // El buscador superior alimenta al mapa (si existe) o filtra las tarjetas.
    var mapped = initMap(searchInput);
    if (!mapped && searchInput) initCardSearch(searchInput);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
