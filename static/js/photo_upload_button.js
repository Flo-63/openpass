/**
 * Photo Upload Button Initializer
 * ==============================
 * Handles photo upload functionality through logo interactions
 * on both desktop and mobile devices.
 */

function initPhotoUploadButton() {
    // Get logo element and return if not found
    const logo = document.getElementById("logo-img");
    if (!logo) return;

    // Timer for long-press detection
    let touchTimer = null;
    const uploadUrl = logo.getAttribute("data-upload-url");

    // Mobile long-press handler
    // Prevents default actions (like "Save Image") but only on long press
    logo.addEventListener("touchstart", (e) => {
        touchTimer = setTimeout(() => {
            e.preventDefault();
            if (uploadUrl) {
                window.location.href = uploadUrl;
            }
        }, 800); // 800ms threshold for long press
    });

    // Clear timer if touch is released or moved
    logo.addEventListener("touchend", () => clearTimeout(touchTimer));
    logo.addEventListener("touchmove", () => clearTimeout(touchTimer));

    // Prevent context menu on right-click (desktop)
    logo.addEventListener("contextmenu", e => e.preventDefault());

    // Handle double-click navigation (desktop or mobile)
    if (uploadUrl) {
        logo.addEventListener("dblclick", () => {
            window.location.href = uploadUrl;
        });
    }
}

// Initialize when DOM is fully loaded
document.addEventListener("DOMContentLoaded", initPhotoUploadButton);