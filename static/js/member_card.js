// member_card.js

document.addEventListener('DOMContentLoaded', () => {
  // ----------------------------
  // Generic Modal Helpers
  // ----------------------------
  function openModal(modal) {
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden'; // optional: scroll lock
  }

  function closeModal(modal) {
    modal.style.display = 'none';
    document.body.style.overflow = ''; // restore scroll
  }

  // ----------------------------
  // Grab Modals and Triggers
  // ----------------------------
  const mailModal     = document.getElementById('mailModal');
  const flashModal    = document.getElementById('flashModal');
  const openMailBtn   = document.getElementById('openMailModal');
  const closeMailBtn  = mailModal    && mailModal.querySelector('.close');
  const closeFlashBtn = flashModal   && flashModal.querySelector('.close');
  const mailForm      = document.getElementById('mailForm');
  const sendButton    = document.getElementById('sendButton');
  const sendingStatus = document.getElementById('sendingStatus');

  // ----------------------------
  // Mail-Modal Open/Close
  // ----------------------------
  if (openMailBtn && mailModal) {
    openMailBtn.addEventListener('click', () => openModal(mailModal));
  }
  if (closeMailBtn) {
    closeMailBtn.addEventListener('click', () => closeModal(mailModal));
  }

  // ----------------------------
  // Flash-Modal: open if any .flash inside
  // ----------------------------
  if (flashModal) {
    const hasFlash = flashModal.querySelectorAll('.flash').length > 0;
    if (hasFlash) openModal(flashModal);
    if (closeFlashBtn) {
      closeFlashBtn.addEventListener('click', () => closeModal(flashModal));
    }
  }

  // ----------------------------
  // Close all modals on outside click
  // ----------------------------
  window.addEventListener('click', (e) => {
    if (e.target === mailModal)  closeModal(mailModal);
    if (e.target === flashModal) closeModal(flashModal);
  });

  // ----------------------------
  // Close all modals on ESC
  // ----------------------------
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (mailModal)  closeModal(mailModal);
      if (flashModal) closeModal(flashModal);
    }
  });

  // ----------------------------
  // Form Submission State
  // ----------------------------
  if (mailForm && sendButton && sendingStatus) {
    mailForm.addEventListener('submit', () => {
      sendButton.disabled = true;
      sendButton.textContent = 'Senden…';
      sendingStatus.style.display = 'block';
    });
  }
});
