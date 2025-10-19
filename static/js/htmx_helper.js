/*
===============================================================================
Project   : openpass
Module    : static/js/htmx_helper.js
Created   : 2025-10-18
Author    : Florian
Purpose   : [Describe the purpose of this module.]

@docstyle: google
@language: english
@voice: imperative
===============================================================================
*/
document.addEventListener("DOMContentLoaded", () => {
  // CSRF automatisch mitsenden
  document.body.addEventListener("htmx:configRequest", (event) => {
    const token = document.querySelector('input[name="csrf_token"]')?.value;
    if (token) event.detail.headers["X-CSRFToken"] = token;
  });

  // Ladeanzeige steuern
  const spinner = document.querySelector("#htmx-loading");
  if (!spinner) return;

  document.body.addEventListener("htmx:beforeRequest", () => spinner.classList.remove("hidden"));
  document.body.addEventListener("htmx:afterSwap", () => spinner.classList.add("hidden"));
  document.body.addEventListener("htmx:responseError", (evt) => {
    console.error("HTMX Error:", evt.detail.xhr.responseText);
    alert("❌ Ein Fehler ist aufgetreten beim Laden der Daten.");
  });
});


