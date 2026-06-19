/* Landing IMJUVE — toggle de vistas, mapa Leaflet y búsqueda en vivo contra /api/buscar/. */
(function () {
  "use strict";

  const MEXICO_CENTER = [23.6, -102.5];
  const KIND_COLOR = { programa: "#16a34a", evento: "#2563eb" }; // verde / azul

  // --- Datos iniciales embebidos (json_script) ---
  function readJSON(id) {
    const el = document.getElementById(id);
    try { return el ? JSON.parse(el.textContent) : []; } catch (_) { return []; }
  }
  const initialData = {
    programas: readJSON("data-programas"),
    descuentos: readJSON("data-descuentos"),
  };

  const searchInput = document.getElementById("main-search");
  const statusEl = document.getElementById("search-status");
  const vistaMapa = document.getElementById("vista-mapa");
  const vistaDesc = document.getElementById("vista-descuentos");
  const cardsGrid = document.getElementById("cards-grid");
  const cardsEmpty = document.getElementById("cards-empty");

  let currentTipo = "programas";
  let mapInitialized = false;

  // --- Mapa Leaflet ---
  let map, markersLayer;
  function ensureMap() {
    if (mapInitialized) { map.invalidateSize(); return; }
    map = L.map("map", { scrollWheelZoom: false }).setView(MEXICO_CENTER, 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    markersLayer = L.layerGroup().addTo(map);
    mapInitialized = true;
    map.invalidateSize();
  }

  function dateRange(start, end) {
    if (start && end) return "Del " + start + " al " + end;
    if (start) return "Desde " + start;
    if (end) return "Hasta " + end;
    return "Vigencia abierta";
  }

  // Pequeño desfase determinista para que varios marcadores del mismo estado no se encimen.
  function jitter(value, index, salt) {
    const k = ((index + 1) * (salt === "lat" ? 0.013 : 0.017)) % 0.18;
    return value + (index % 2 === 0 ? k : -k);
  }

  function renderMarkers(items) {
    ensureMap();
    markersLayer.clearLayers();
    items.forEach(function (it, i) {
      if (typeof it.lat !== "number" || typeof it.lng !== "number") return;
      const lat = jitter(it.lat, i, "lat");
      const lng = jitter(it.lng, i, "lng");
      const color = KIND_COLOR[it.kind] || "#6A1B29";
      const marker = L.circleMarker([lat, lng], {
        radius: 8, color: "#ffffff", weight: 2,
        fillColor: color, fillOpacity: 0.95,
      });
      const tipo = it.kind === "evento" ? "Evento" : "Programa";
      const loc = [it.municipality, it.state].filter(Boolean).join(", ");
      marker.bindPopup(
        '<strong>' + escapeHtml(it.name) + '</strong><br>' +
        '<span style="color:' + color + '">&#9679;</span> ' + tipo +
        (loc ? '<br>' + escapeHtml(loc) : '') +
        '<br><small>' + escapeHtml(dateRange(it.start_date, it.end_date)) + '</small>'
      );
      markersLayer.addLayer(marker);
    });
  }

  // --- Tarjetas de descuentos ---
  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function buildCard(p) {
    const card = document.createElement("div");
    card.className = "bg-white rounded-xl shadow-sm border border-gray-100 p-5 hover:shadow-md transition duration-200 flex flex-col justify-between";

    const top = document.createElement("div");
    top.className = "flex items-start space-x-4";

    const logoBox = document.createElement("div");
    logoBox.className = "w-16 h-16 bg-[#6A1B29]/10 rounded-lg flex items-center justify-center text-2xl font-bold text-[#6A1B29] shrink-0 overflow-hidden";
    if (p.logo_url) {
      const img = document.createElement("img");
      img.src = p.logo_url;
      img.alt = p.company || "";
      img.className = "w-full h-full object-contain";
      img.onerror = function () { logoBox.textContent = (p.company || "?").charAt(0).toUpperCase(); };
      logoBox.appendChild(img);
    } else {
      logoBox.textContent = (p.company || "?").charAt(0).toUpperCase();
    }

    const info = document.createElement("div");
    const loc = [p.city, p.municipality, p.state].filter(Boolean).join(", ") || "A nivel nacional";
    info.innerHTML =
      '<span class="text-[10px] uppercase font-bold text-[#BC955C] tracking-widest block">' + escapeHtml(p.company) + '</span>' +
      '<h4 class="font-bold text-gray-800 text-lg">' + escapeHtml(p.name) + '</h4>' +
      '<p class="text-xs text-gray-500 mt-1 line-clamp-2">' + escapeHtml(p.description) + '</p>';

    top.appendChild(logoBox);
    top.appendChild(info);

    const footer = document.createElement("div");
    footer.className = "mt-4 pt-3 border-t border-gray-100 flex justify-between items-center text-xs text-gray-400";
    const badgeClass = p.active ? "text-green-600 bg-green-50" : "text-gray-500 bg-gray-100";
    const badgeText = p.active ? "Activo" : "Inactivo";
    footer.innerHTML =
      '<span>' + escapeHtml(loc) + '</span>' +
      '<span class="font-semibold px-2 py-0.5 rounded ' + badgeClass + '">' + badgeText + '</span>';

    card.appendChild(top);
    card.appendChild(footer);
    return card;
  }

  function renderCards(items) {
    cardsGrid.innerHTML = "";
    if (!items.length) {
      cardsEmpty.classList.remove("hidden");
      return;
    }
    cardsEmpty.classList.add("hidden");
    const frag = document.createDocumentFragment();
    items.forEach(function (p) { frag.appendChild(buildCard(p)); });
    cardsGrid.appendChild(frag);
  }

  function render(tipo, items) {
    if (tipo === "descuentos") renderCards(items);
    else renderMarkers(items);
    statusEl.textContent = items.length + " resultado" + (items.length === 1 ? "" : "s");
  }

  // --- Búsqueda contra el backend ---
  let reqToken = 0;
  function runSearch() {
    const tipo = currentTipo;
    const q = searchInput.value.trim();
    const token = ++reqToken;
    statusEl.textContent = "Buscando…";
    const url = "/api/buscar/?tipo=" + encodeURIComponent(tipo) + "&q=" + encodeURIComponent(q);
    fetch(url, { headers: { "X-Requested-With": "fetch" } })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (token !== reqToken) return; // descarta respuestas obsoletas
        render(tipo, data.results || []);
      })
      .catch(function () {
        if (token !== reqToken) return;
        statusEl.textContent = "No se pudo completar la búsqueda.";
      });
  }

  function debounce(fn, ms) {
    let t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }

  // --- Toggle de vistas ---
  function toggleVista(valor) {
    currentTipo = valor;
    if (valor === "descuentos") {
      vistaMapa.classList.add("hidden");
      vistaMapa.classList.remove("block");
      vistaDesc.classList.remove("hidden");
      searchInput.placeholder = "Buscar por empresa, promoción, sector o ubicación...";
    } else {
      vistaDesc.classList.add("hidden");
      vistaMapa.classList.remove("hidden");
      vistaMapa.classList.add("block");
      searchInput.placeholder = "Buscar por Estado, Municipio, Ciudad, CP o palabra clave del evento...";
      ensureMap();
    }
    // Si no hay texto, usamos los datos iniciales sin pegarle al backend.
    if (!searchInput.value.trim()) render(valor, initialData[valor] || []);
    else runSearch();
  }

  // --- Wiring ---
  document.querySelectorAll('input[name="tipo_busqueda"]').forEach(function (radio) {
    radio.addEventListener("change", function () { toggleVista(this.value); });
  });
  searchInput.addEventListener("input", debounce(runSearch, 250));

  // Estado inicial: vista de programas con los datos embebidos.
  ensureMap();
  render("programas", initialData.programas);
})();
