/*
===============================================================================
Project   : openpass
Module    : static/js/member_editor.js
Author    : Florian & Code GPT
Created   : 2025-10-19
Purpose   : Handles live SHA256 hash preview when editing or creating members.
Notes     : htmx-safe, production-ready, optional debug logging (with Krautsalat)
===============================================================================
*/

// ----------------------------------------------------------------------------
// 🥬 Krautsalat Logging System (DEBUG Mode Toggle)
// ----------------------------------------------------------------------------
const DEBUG = false; // 👉 Auf true stellen für Entwickler-Logs

function log(...args) {
  if (DEBUG) console.log("🥬", ...args);
}
function warn(...args) {
  if (DEBUG) console.warn("⚠️🥬", ...args);
}
function error(...args) {
  if (DEBUG) console.error("❌🥬", ...args);
}

// ----------------------------------------------------------------------------
// 🧠 Local Hash Cache (reduziert Serverlast beim Tippen)
// ----------------------------------------------------------------------------
const hashCache = new Map();

// ----------------------------------------------------------------------------
// 🔧 Core Function: initHashPreview()
// ----------------------------------------------------------------------------
function initHashPreview(context = document) {
  const emailInput = context.querySelector("#new-email");
  const hashField = context.querySelector("#new-hash");
  const showBtn = context.querySelector("#show-hash");

  // Keine relevanten Elemente gefunden → abbrechen
  if (!emailInput || !hashField || !showBtn) {
    warn("Hash preview elements not found in context", context);
    return;
  }

  // Mehrfache Initialisierung verhindern
  if (emailInput.dataset.listenerAttached === "true") return;
  emailInput.dataset.listenerAttached = "true";

  // ----------------------------------------------------------------------------
  // 🔹 Subfunction: Hash berechnen & anzeigen
  // ----------------------------------------------------------------------------
  async function updateHash() {
    const email = emailInput.value.trim();
    if (!email) {
      hashField.value = "";
      showBtn.dataset.fullhash = "";
      return;
    }

    // Caching nutzen, um unnötige Requests zu sparen
    if (hashCache.has(email)) {
      const cachedHash = hashCache.get(email);
      hashField.value = cachedHash.substring(0, 10) + "…";
      showBtn.dataset.fullhash = cachedHash;
      log("♻️ Cached hash used for:", email);
      return;
    }

    try {
      log("🔹 Requesting hash preview for:", email);
      const res = await fetch(`/members/hash-preview?email=${encodeURIComponent(email)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const hash = await res.text();

      hashCache.set(email, hash); // Cache speichern
      hashField.value = hash.substring(0, 10) + "…";
      showBtn.dataset.fullhash = hash;
      log("✅ Hash received:", hash);
    } catch (err) {
      hashField.value = "⚠️ Fehler";
      error("Hash preview failed:", err);
    }
  }

  // ----------------------------------------------------------------------------
  // 💬 Events
  // ----------------------------------------------------------------------------
  // Live Hash Update bei Eingabe
  emailInput.addEventListener("input", updateHash);

  // Vollständigen Hash anzeigen (oder sofort berechnen)
  showBtn.addEventListener("click", async () => {
    if (!showBtn.dataset.fullhash && emailInput.value.trim()) {
      await updateHash(); // Berechnen, falls leer
    }
    const fullHash = showBtn.dataset.fullhash;
    alert(fullHash ? `Vollständiger Hash:\n\n${fullHash}` : "Bitte zuerst eine gültige E-Mail-Adresse eingeben.");
  });

  log("✅ Hash preview initialized in fragment", context);
}

// ----------------------------------------------------------------------------
// 🧩 Initialization Hooks
// ----------------------------------------------------------------------------

// Initial bei normalem Seitenaufruf
document.addEventListener("DOMContentLoaded", () => {
  log("📦 DOMContentLoaded — Initializing hash preview");
  initHashPreview(document);
});

// Nach htmx-Austausch eines Fragments
document.body.addEventListener("htmx:afterSettle", (evt) => {
  const fragment = evt.target.querySelector("#new-email") ? evt.target : null;
  if (fragment) {
    log("♻️ Initializing hash preview for new fragment");
    initHashPreview(fragment);
  }
});
