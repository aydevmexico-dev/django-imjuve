/* Cascada geográfica del registro: Estado -> Municipio -> Colonia, y autocompletado por CP. */
(function () {
  "use strict";

  const form = document.querySelector("form[data-municipios-url]");
  if (!form) return;

  const URL_MUNICIPIOS = form.dataset.municipiosUrl;  // /api/geo/municipios/
  const URL_COLONIAS = form.dataset.coloniasUrl;      // /api/geo/colonias/

  const stateSel = document.getElementById("id_state");
  const muniSel = document.getElementById("id_municipality");
  const coloniaSel = document.getElementById("id_residence_location");
  const cpInput = document.getElementById("id_postal_code");

  // Rellena un <select> con items; opcionalmente reselecciona un valor previo (data-selected).
  function fillSelect(sel, items, placeholder, selectedValue) {
    sel.innerHTML = "";
    const ph = document.createElement("option");
    ph.value = "";
    ph.textContent = placeholder;
    sel.appendChild(ph);
    items.forEach(function (it) {
      const opt = document.createElement("option");
      opt.value = it.id;
      opt.textContent = it.label;
      if (selectedValue && String(selectedValue) === String(it.id)) opt.selected = true;
      sel.appendChild(opt);
    });
  }

  function getJSON(url) {
    return fetch(url, { headers: { "X-Requested-With": "fetch" } }).then(function (r) {
      return r.ok ? r.json() : { results: [] };
    });
  }

  // --- Drill-down: Estado -> Municipios ---
  function loadMunicipios(stateId, selectMuni, thenLoadColonia) {
    if (!stateId) {
      fillSelect(muniSel, [], "— Selecciona un estado primero —");
      fillSelect(coloniaSel, [], "— Selecciona un municipio primero —");
      return Promise.resolve();
    }
    return getJSON(URL_MUNICIPIOS + "?state=" + encodeURIComponent(stateId)).then(function (data) {
      const items = (data.results || []).map(function (m) { return { id: m.id, label: m.name }; });
      fillSelect(muniSel, items, "— Selecciona —", selectMuni);
      fillSelect(coloniaSel, [], "— Selecciona un municipio primero —");
      if (thenLoadColonia && selectMuni) return loadColonias(selectMuni, null);
    });
  }

  // --- Municipio -> Colonias ---
  function loadColonias(municipalityId, selectColonia) {
    if (!municipalityId) {
      fillSelect(coloniaSel, [], "— Selecciona un municipio primero —");
      return Promise.resolve();
    }
    return getJSON(URL_COLONIAS + "?municipality=" + encodeURIComponent(municipalityId)).then(function (data) {
      const items = (data.results || []).map(function (c) {
        return { id: c.id, label: c.name + " (" + c.settlement_type + ") · " + c.postal_code };
      });
      fillSelect(coloniaSel, items, "— Selecciona —", selectColonia);
    });
  }

  // --- Autocompletado por Código Postal ---
  function loadByPostalCode(cp) {
    if (!cp || cp.length < 4) return;
    getJSON(URL_COLONIAS + "?postal_code=" + encodeURIComponent(cp)).then(function (data) {
      const results = data.results || [];
      if (!results.length) return;
      const first = results[0];  // todas las colonias de un CP comparten estado y municipio
      stateSel.value = first.state_id;
      fillSelect(muniSel, [{ id: first.municipality_id, label: first.municipality }], "— Selecciona —", first.municipality_id);
      const colonias = results.map(function (c) {
        return { id: c.id, label: c.name + " (" + c.settlement_type + ")" };
      });
      fillSelect(coloniaSel, colonias, "— Selecciona tu colonia —");
    });
  }

  function debounce(fn, ms) {
    let t;
    return function () { const a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); };
  }

  // --- Wiring ---
  stateSel.addEventListener("change", function () { loadMunicipios(this.value, null, false); });
  muniSel.addEventListener("change", function () { loadColonias(this.value, null); });
  cpInput.addEventListener("input", debounce(function () { loadByPostalCode(this.value.trim()); }, 350));

  // Al recargar con errores de validación, reconstruir los selects con lo ya elegido.
  const preMuni = muniSel.dataset.selected;
  const preColonia = coloniaSel.dataset.selected;
  if (stateSel.value) {
    loadMunicipios(stateSel.value, preMuni, false).then(function () {
      if (preMuni) loadColonias(preMuni, preColonia);
    });
  }
})();
