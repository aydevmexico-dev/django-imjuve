/* ============================================================================
   IMJUVE · Panel — formularios (v2)
   · Pestañas internas (Datos Generales | Requisitos | Imágenes Adicionales).
   · Formsets dinámicos (agregar / quitar filas) sobre inlineformset_factory.
   · Multiselect de Ciudades (chips + buscador + checkboxes), 100% vanilla.
   · Cascada geográfica Estado -> Municipio + Ciudad(es) — solo SUPER; el ESTATAL
     trae el estado bloqueado y la geografía pre-filtrada por el servidor (no-op).
   Sin dependencias externas. Independiente de admin_dashboard.js.
   ========================================================================== */
(function () {
  "use strict";

  /* -------------------------------- Tabs -------------------------------- */
  function initTabs() {
    document.querySelectorAll(".nav-tabs").forEach(function (bar) {
      var form = bar.closest("form");
      var tabs = Array.prototype.slice.call(bar.querySelectorAll(".nav-tabs__tab"));
      function activate(key) {
        tabs.forEach(function (t) {
          var on = t.dataset.tab === key;
          t.classList.toggle("is-active", on);
          t.setAttribute("aria-selected", on ? "true" : "false");
        });
        form.querySelectorAll(".tab-pane").forEach(function (p) {
          p.classList.toggle("is-active", p.dataset.pane === key);
        });
      }
      tabs.forEach(function (t) {
        t.addEventListener("click", function () { activate(t.dataset.tab); });
        t.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); activate(t.dataset.tab); }
        });
      });
    });
  }

  /* ------------------------------ Formsets ------------------------------ */
  function rowFilled(row) {
    var idf = row.querySelector('input[name$="-id"]');
    if (idf && idf.value) return true;                       // registro ya guardado
    var first = row.querySelector('.formset__field input, .formset__field textarea, .formset__field select');
    if (first && first.type === "file") return first.files && first.files.length > 0;
    return !!(first && first.value);
  }

  function updateCount(formset) {
    var badge = document.querySelector('.nav-tabs__count[data-count-for="' + formset.dataset.prefix + '"]');
    if (!badge) return;
    var n = 0;
    formset.querySelectorAll(".formset__row").forEach(function (r) {
      if (!r.classList.contains("is-removed") && rowFilled(r)) n++;
    });
    badge.textContent = n ? String(n) : "";
  }

  function initFormsets() {
    document.querySelectorAll(".formset").forEach(function (formset) {
      var prefix = formset.dataset.prefix;
      var rowsBox = formset.querySelector(".formset__rows");
      var tpl = formset.querySelector(".formset__empty");
      var addBtn = formset.querySelector(".formset__add");
      var total = document.getElementById("id_" + prefix + "-TOTAL_FORMS");

      function bindRow(row) {
        var btn = row.querySelector(".formset__remove");
        if (btn) {
          btn.addEventListener("click", function () {
            var del = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
            if (del) del.checked = true;            // fila existente: Django la elimina al guardar
            row.classList.add("is-removed");         // nueva o existente: se oculta
            updateCount(formset);
          });
        }
        row.addEventListener("input", function () { updateCount(formset); });
        row.addEventListener("change", function () { updateCount(formset); });
      }

      rowsBox.querySelectorAll(".formset__row").forEach(bindRow);

      if (addBtn && tpl && total) {
        addBtn.addEventListener("click", function () {
          var idx = parseInt(total.value, 10) || 0;
          var html = tpl.innerHTML.replace(/__prefix__/g, idx);
          var tmp = document.createElement("div");
          tmp.innerHTML = html.trim();
          var row = tmp.firstElementChild;
          rowsBox.appendChild(row);
          total.value = idx + 1;
          bindRow(row);
          updateCount(formset);
        });
      }
      updateCount(formset);
    });
  }

  /* --------------------- Multiselect de Ciudades ------------------------ */
  function buildMultiselect(select) {
    var wrap = document.createElement("div");
    wrap.className = "ms";
    select.parentNode.insertBefore(wrap, select);
    wrap.appendChild(select);

    var control = document.createElement("div");
    control.className = "ms__control";
    var menu = document.createElement("div");
    menu.className = "ms__menu";
    var search = document.createElement("input");
    search.className = "ms__search";
    search.type = "text";
    search.placeholder = "Buscar ciudad…";
    var optsBox = document.createElement("div");
    menu.appendChild(search);
    menu.appendChild(optsBox);
    wrap.appendChild(control);
    wrap.appendChild(menu);

    function options() { return Array.prototype.slice.call(select.options); }

    function renderControl() {
      control.querySelectorAll(".ms__chip, .ms__ph").forEach(function (n) { n.remove(); });
      var selected = options().filter(function (o) { return o.selected && o.value; });
      if (!selected.length) {
        var ph = document.createElement("span");
        ph.className = "ms__ph";
        ph.textContent = select.disabled ? "—" : "Selecciona ciudades…";
        control.appendChild(ph);
        return;
      }
      selected.forEach(function (o) {
        var chip = document.createElement("span");
        chip.className = "ms__chip";
        chip.textContent = o.textContent;
        if (!select.disabled) {
          var x = document.createElement("span");
          x.className = "ms__chip-x";
          x.textContent = "×";
          x.addEventListener("click", function (e) { e.stopPropagation(); o.selected = false; sync(); });
          chip.appendChild(x);
        }
        control.appendChild(chip);
      });
    }

    function renderMenu() {
      optsBox.innerHTML = "";
      var q = search.value.trim().toLowerCase();
      var any = false;
      options().forEach(function (o) {
        if (!o.value) return;
        var row = document.createElement("label");
        row.className = "ms__opt";
        if (o.textContent.toLowerCase().indexOf(q) === -1) row.classList.add("is-hidden");
        else any = true;
        var cb = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = o.selected;
        cb.disabled = select.disabled;
        cb.addEventListener("change", function () { o.selected = cb.checked; renderControl(); });
        var span = document.createElement("span");
        span.textContent = o.textContent;
        row.appendChild(cb);
        row.appendChild(span);
        optsBox.appendChild(row);
      });
      if (!any) {
        var empty = document.createElement("div");
        empty.className = "ms__empty";
        empty.textContent = options().filter(function (o) { return o.value; }).length
          ? "Sin coincidencias." : "Elige un estado para ver ciudades.";
        optsBox.appendChild(empty);
      }
    }

    function sync() { renderControl(); renderMenu(); }
    function close() { wrap.classList.remove("is-open"); }
    control.addEventListener("click", function () {
      if (select.disabled) return;
      if (wrap.classList.contains("is-open")) { close(); }
      else { wrap.classList.add("is-open"); search.value = ""; renderMenu(); search.focus(); }
    });
    search.addEventListener("input", renderMenu);
    document.addEventListener("click", function (e) { if (!wrap.contains(e.target)) close(); });

    // La cascada (SUPER) llama refresh() tras reconstruir las <option> del select.
    select._ms = { refresh: sync };
    sync();
  }

  function initMultiselects() {
    document.querySelectorAll('select[multiple][data-geo="cities"]').forEach(buildMultiselect);
  }

  /* ----------------------- Cascada geográfica --------------------------- */
  function initGeoCascade() {
    var form = document.querySelector("form[data-municipios-url]");
    if (!form) return;
    var URL_MUNI = form.dataset.municipiosUrl;
    var URL_CIUDAD = form.dataset.ciudadesUrl;
    var stateSel = form.querySelector('[data-geo="state"]');
    var muniSel = form.querySelector('[data-geo="municipality"]');
    var citySel = form.querySelector('[data-geo="city"]');
    var citiesSel = form.querySelector('[data-geo="cities"]');
    if (!stateSel) return;
    if (stateSel.disabled || stateSel.dataset.locked === "1") return;   // ESTATAL: no-op

    function getJSON(url) {
      return fetch(url, { headers: { "X-Requested-With": "fetch" } })
        .then(function (r) { return r.ok ? r.json() : { results: [] }; })
        .catch(function () { return { results: [] }; });
    }
    function fill(sel, items, placeholder, selected) {
      if (!sel) return;
      var multiple = sel.multiple;
      var chosen = multiple
        ? (selected || []).map(String)
        : (selected != null && selected !== "" ? [String(selected)] : []);
      sel.innerHTML = "";
      if (!multiple) {
        var ph = document.createElement("option");
        ph.value = "";
        ph.textContent = placeholder;
        sel.appendChild(ph);
      }
      items.forEach(function (it) {
        var opt = document.createElement("option");
        opt.value = it.id;
        opt.textContent = it.name;
        if (chosen.indexOf(String(it.id)) !== -1) opt.selected = true;
        sel.appendChild(opt);
      });
      if (sel._ms) sel._ms.refresh();   // refresca el multiselect de ciudades si aplica
    }
    function selectedValues(sel) {
      if (!sel) return null;
      if (sel.multiple) return Array.prototype.slice.call(sel.selectedOptions).map(function (o) { return o.value; });
      return sel.value;
    }
    function loadFor(stateId, keepMuni, keepCity, keepCities) {
      if (!stateId) {
        fill(muniSel, [], "— Elige un estado primero —", null);
        fill(citySel, [], "— Elige un estado primero —", null);
        fill(citiesSel, [], "", []);
        return;
      }
      getJSON(URL_MUNI + "?state=" + encodeURIComponent(stateId)).then(function (d) {
        fill(muniSel, d.results || [], "— Selecciona —", keepMuni);
      });
      getJSON(URL_CIUDAD + "?state=" + encodeURIComponent(stateId)).then(function (d) {
        var results = d.results || [];
        fill(citySel, results, "— Selecciona —", keepCity);
        fill(citiesSel, results, "", keepCities);
      });
    }
    stateSel.addEventListener("change", function () { loadFor(this.value, null, null, []); });
    if (stateSel.value) {
      loadFor(stateSel.value, selectedValues(muniSel), selectedValues(citySel), selectedValues(citiesSel));
    }
  }

  /* -------------------------------- Init -------------------------------- */
  initTabs();
  initFormsets();
  initMultiselects();   // antes de la cascada: deja `_ms` listo para refresh()
  initGeoCascade();
})();
