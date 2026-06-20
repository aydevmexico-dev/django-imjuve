/* ============================================================================
   IMJUVE · Panel — constructor de Encuestas (Test + Preguntas + Opciones)
   · Formset externo de Preguntas (token __qprefix__ al clonar).
   · Formset interno anidado de Opciones por pregunta (token __prefix__ nativo).
   · Las opciones solo se muestran cuando la pregunta es de Opción Múltiple (MC).
   Las pestañas y la cascada geográfica las maneja admin_forms.js (cargado antes).
   Sin dependencias externas.
   ========================================================================== */
(function () {
  "use strict";

  var builder = document.getElementById("qBuilder");
  if (!builder) return;

  var rows = document.getElementById("qRows");
  var addQBtn = document.getElementById("qAdd");
  var qTotal = document.getElementById("id_questions-TOTAL_FORMS");
  var qEmptyTpl = document.getElementById("qEmptyTpl");
  var countBadge = document.getElementById("qCount");

  var MULTIPLE_CHOICE = "MC";

  /* --------------------------- Utilidades ------------------------------- */
  function liveQRows() {
    return Array.prototype.slice.call(rows.querySelectorAll(".qrow"))
      .filter(function (r) { return !r.classList.contains("is-removed"); });
  }

  function renumber() {
    var live = liveQRows();
    live.forEach(function (r, i) {
      var num = r.querySelector("[data-qnum]");
      if (num) num.textContent = i + 1;
    });
    if (countBadge) countBadge.textContent = live.length ? String(live.length) : "";
  }

  function cloneFrom(tpl, token, index) {
    var html = tpl.innerHTML.replace(new RegExp(token, "g"), index);
    var tmp = document.createElement("div");
    tmp.innerHTML = html.trim();
    return tmp.firstElementChild;
  }

  /* --------------------- Opciones (formset interno) --------------------- */
  function choiceTotal(qrow) {
    return qrow.querySelector('[data-choices] input[name^="choices-"][name$="-TOTAL_FORMS"]');
  }

  function bindChoiceRow(crow) {
    var del = crow.querySelector("[data-cdel]");
    if (!del) return;
    del.addEventListener("click", function () {
      var flag = crow.querySelector('input[name^="choices-"][name$="-DELETE"]');
      if (flag) flag.checked = true;           // fila existente: Django la borra al guardar
      crow.classList.add("is-removed");        // nueva o existente: se oculta
    });
  }

  function bindChoices(qrow) {
    qrow.querySelectorAll(".choices__rows .crow").forEach(bindChoiceRow);

    var addBtn = qrow.querySelector("[data-cadd]");
    var tpl = qrow.querySelector(".choices__tpl");
    var box = qrow.querySelector(".choices__rows");
    var total = choiceTotal(qrow);
    if (!(addBtn && tpl && box && total)) return;

    addBtn.addEventListener("click", function () {
      var idx = parseInt(total.value, 10) || 0;
      var crow = cloneFrom(tpl, "__prefix__", idx);
      box.appendChild(crow);
      total.value = idx + 1;
      bindChoiceRow(crow);
      var input = crow.querySelector('input[type="text"]');
      if (input) input.focus();
    });
  }

  /* ------------------------- Toggle MC / Texto -------------------------- */
  function syncChoices(qrow) {
    var sel = qrow.querySelector('select[name$="-question_type"]');
    var box = qrow.querySelector("[data-choices]");
    if (!sel || !box) return;
    box.classList.toggle("choices--on", sel.value === MULTIPLE_CHOICE);
  }

  /* --------------------- Preguntas (formset externo) -------------------- */
  function bindQRow(qrow) {
    var sel = qrow.querySelector('select[name$="-question_type"]');
    if (sel) sel.addEventListener("change", function () { syncChoices(qrow); });
    syncChoices(qrow);

    var del = qrow.querySelector("[data-qdel]");
    if (del) {
      del.addEventListener("click", function () {
        var flag = qrow.querySelector('input[name^="questions-"][name$="-DELETE"]');
        if (flag) flag.checked = true;
        qrow.classList.add("is-removed");
        renumber();
      });
    }
    bindChoices(qrow);
  }

  rows.querySelectorAll(".qrow").forEach(bindQRow);

  if (addQBtn && qEmptyTpl && qTotal) {
    addQBtn.addEventListener("click", function () {
      var idx = parseInt(qTotal.value, 10) || 0;
      var qrow = cloneFrom(qEmptyTpl, "__qprefix__", idx);
      rows.appendChild(qrow);
      qTotal.value = idx + 1;
      bindQRow(qrow);
      renumber();
      var first = qrow.querySelector("textarea");
      if (first) first.focus();
    });
  }

  renumber();
})();
