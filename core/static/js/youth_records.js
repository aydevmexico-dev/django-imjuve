/* ============================================================================
   IMJUVE · Expediente Digital — interacción del cliente.
   · Pestañas internas del expediente (Mi Perfil / Guardados / Encuestas / Actividad).
   · Guardar/quitar favoritos vía POST AJAX (CSRF) desde cualquier página del portal.
   · Bitácora de búsquedas: el buscador superior (#ySearch) registra el término (debounced).
   Vanilla, sin dependencias. Se carga en todo el portal; cada bloque no-opera si su
   marcado no está presente. La protección de acceso/rol vive en el servidor (views.py).
   ========================================================================== */
(function () {
  "use strict";

  var body = document.body;

  /* ----------------------------- Utilidades ---------------------------- */
  function csrfToken() {
    var input = document.querySelector("input[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function debounce(fn, ms) {
    var t;
    return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); };
  }

  function postForm(url, data) {
    var body = new URLSearchParams(data).toString();
    return fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "fetch",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: body,
      credentials: "same-origin",
    });
  }

  /* ----------------------------- Pestañas ------------------------------ */
  function initTabs() {
    var root = document.getElementById("recordRoot");
    if (!root) return;
    var tabs = Array.prototype.slice.call(root.querySelectorAll(".rtab"));
    var panels = Array.prototype.slice.call(root.querySelectorAll("[data-tab-panel]"));
    if (!tabs.length) return;

    function activate(name) {
      tabs.forEach(function (t) {
        var on = t.dataset.tab === name;
        t.classList.toggle("is-active", on);
        t.setAttribute("aria-selected", on ? "true" : "false");
      });
      panels.forEach(function (p) {
        var on = p.dataset.tabPanel === name;
        p.classList.toggle("is-active", on);
        p.hidden = !on;
      });
    }

    tabs.forEach(function (t) {
      t.addEventListener("click", function () { activate(t.dataset.tab); });
    });
  }

  /* ----------------------------- Favoritos ----------------------------- */
  function initFavorites() {
    var favUrl = body.getAttribute("data-fav-url");
    if (!favUrl) return;

    document.addEventListener("click", function (e) {
      // Guardar / dejar de guardar desde el detalle (toggle con etiqueta).
      var toggle = e.target.closest("[data-fav-toggle]");
      if (toggle) {
        e.preventDefault();
        if (toggle.disabled) return;
        toggle.disabled = true;
        postForm(favUrl, { kind: toggle.dataset.kind, id: toggle.dataset.objId })
          .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
          .then(function (data) {
            var saved = !!data.saved;
            toggle.classList.toggle("is-saved", saved);
            toggle.setAttribute("aria-pressed", saved ? "true" : "false");
            var label = toggle.querySelector(".btn-fav__label");
            if (label) label.textContent = saved ? "Guardado" : "Guardar";
          })
          .catch(function () { /* silencioso: el servidor es la autoridad */ })
          .then(function () { toggle.disabled = false; });
        return;
      }

      // Quitar desde el expediente (elimina la tarjeta del listado).
      var remove = e.target.closest("[data-fav-remove]");
      if (remove) {
        e.preventDefault();
        if (remove.disabled) return;
        remove.disabled = true;
        postForm(favUrl, { kind: remove.dataset.kind, id: remove.dataset.objId })
          .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
          .then(function (data) {
            if (!data.saved) {
              var card = remove.closest("[data-saved-id]");
              if (card) card.remove();
            }
          })
          .catch(function () { remove.disabled = false; });
      }
    });
  }

  /* ----------------------- Bitácora de búsquedas ----------------------- */
  function initSearchLog() {
    var url = body.getAttribute("data-search-log-url");
    var input = document.getElementById("ySearch");
    // Solo los jóvenes (no admins en vista previa) alimentan su expediente.
    if (!url || !input || body.getAttribute("data-can-log") !== "1") return;

    var log = debounce(function () {
      var q = (input.value || "").trim();
      if (q.length < 2) return;
      postForm(url, { q: q }).catch(function () { /* fire-and-forget */ });
    }, 900);

    input.addEventListener("input", log);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTabs();
    initFavorites();
    initSearchLog();
  });
})();
