/*
===============================================================================
Project   : openpass
Module    : static/js/members_manage.js
Created   : 2025-10-18
Author    : Florian
Purpose   : This module handles the CSV import form for managing members.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
*/
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("csv-import-form");
  if (!form) return;

  // Blockiert normales HTML-Formular-Submit
  form.addEventListener("submit", (event) => {
    event.preventDefault();
  });
});
