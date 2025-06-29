/**
 * Mail Modal and Flash Message Handler
 * ==================================
 * Manages mail modal interactions, flash messages,
 * and form submission states.
 */

// Initial setup on page load
window.addEventListener('load', function() {
    const successFlash = document.querySelector('.flash.success');
    const errorFlash = document.querySelector('.flash.error');
    const mailModal = document.getElementById("mailModal");
    const redirectUrl = document.body.dataset.redirectUrl;

    // Handle success flash message
    if (successFlash) {
        // Close modal if open
        if (mailModal && mailModal.style.display === "block") {
            closeModal();
        }

        // Fade out success message
        setTimeout(function() {
            successFlash.style.transition = "opacity 1s";
            successFlash.style.opacity = "0";
        }, 2000);

        // Redirect after message fade
        setTimeout(function() {
            window.location.href = redirectUrl;
        }, 3000);
    }

    // Show modal if there's an error
    if (errorFlash && mailModal) {
        mailModal.style.display = "block";
    }
});

/**
 * Modal Control Functions
 */
function openModal() {
    document.getElementById("mailModal").style.display = "block";
}

function closeModal() {
    document.getElementById("mailModal").style.display = "none";
}

// Close modal on outside click
window.onclick = function(event) {
    const modal = document.getElementById("mailModal");
    if (event.target === modal) {
        modal.style.display = "none";
    }
}

/**
 * Form Submission Handler
 * Updates UI elements during form submission
 */
document.getElementById("mailForm").addEventListener("submit", function() {
    const sendButton = document.getElementById("sendButton");
    const sendingStatus = document.getElementById("sendingStatus");

    if (sendButton && sendingStatus) {
        // Disable button and show sending status
        sendButton.disabled = true;
        sendButton.textContent = "Senden...";
        sendingStatus.style.display = "block";
    }
});

/**
 * Modal Button Event Listeners
 * Set up click handlers for modal open/close buttons
 */
document.addEventListener("DOMContentLoaded", function () {
    const openModalBtn =
        document.getElementById("openMailModal")        // neuer Button
        || document.querySelector(".mail-button button"); // Fallback alt
    const closeModalBtn = document.querySelector("#mailModal .close");

    if (openModalBtn) {
        openModalBtn.addEventListener("click", openModal);
    }

    if (closeModalBtn) {
        closeModalBtn.addEventListener("click", closeModal);
    }
});