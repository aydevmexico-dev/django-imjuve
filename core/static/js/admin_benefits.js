/* ============================================================================
   IMJUVE · Panel — sección Descuentos.
   Previsualización del logo de la Empresa al elegir archivo en el formulario.
   No-op fuera del formulario de Empresa (lista, formulario de Promoción, etc.).
   Sin dependencias externas.
   ========================================================================== */
(function () {
  "use strict";

  // El logo es el único file input cuyo name termina en "logo" (CompanyForm).
  var input = document.querySelector('form input[type="file"][name$="logo"]');
  if (!input) return;

  var preview = document.createElement("img");
  preview.className = "logo-preview";
  preview.alt = "Vista previa del logo";
  preview.hidden = true;
  input.insertAdjacentElement("afterend", preview);

  input.addEventListener("change", function () {
    var file = input.files && input.files[0];
    if (!file || !/^image\//.test(file.type)) {
      preview.hidden = true;
      preview.removeAttribute("src");
      return;
    }
    var reader = new FileReader();
    reader.onload = function (e) { preview.src = e.target.result; preview.hidden = false; };
    reader.readAsDataURL(file);
  });
})();
