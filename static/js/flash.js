/**
 * Flash-Modal Handler
 */
window.addEventListener("DOMContentLoaded", () => {
  const flashModal   = document.getElementById("flashModal");
  const closeFlash   = document.getElementById("closeFlashModal");
  const flashes      = flashModal ? flashModal.querySelectorAll(".flash") : [];

  // Wenn Flash-Nachrichten vorhanden sind: Modal öffnen
  if (flashes.length > 0) {
    flashModal.style.display = "flex";
  }

  // Klick auf × schließt Flash-Modal
  closeFlash?.addEventListener("click", () => {
    flashModal.style.display = "none";
  });

  // Klick außerhalb schließt Flash-Modal
  window.addEventListener("click", e => {
    if (e.target === flashModal) {
      flashModal.style.display = "none";
    }
  });

  // Automatisches Fade-Out nach 5 Sekunden
  setTimeout(() => {
    flashes.forEach(el => {
      el.style.opacity = "0";
      setTimeout(() => {
        el.remove();
        // wenn keine Meldungen mehr da sind: Modal schließen
        if (flashModal.querySelectorAll(".flash").length === 0) {
          flashModal.style.display = "none";
        }
      }, 1000);
    });
  }, 5000);
});
