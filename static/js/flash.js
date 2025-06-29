/**
 * Flash Message Handler
 * ====================
 * Manages the automatic fading and removal of flash messages
 * in the user interface.
 */

window.addEventListener("DOMContentLoaded", () => {
    // Delay before starting the fade-out effect (5 seconds)
    setTimeout(() => {
        // Select all flash messages on the page
        const flashes = document.querySelectorAll('.flash');
        
        // Process each flash message individually
        flashes.forEach(el => {
            // Smooth fade-out using opacity transition
            el.style.opacity = '0';
            
            // Optional: Completely remove element after fade-out
            // 1-second delay to allow for animation completion
            setTimeout(() => el.remove(), 1000);
        });
    }, 5000);
});