/**
 * Login Rate Limit Checker
 * ======================
 * Manages the "Back to Login" button state based on
 * email login rate limiting.
 */

// Get the back to login button
const btn = document.getElementById("backToLogin");

/**
 * Checks if user is allowed to request email login
 * Enables/disables button based on server response
 */
function checkLimit() {
    fetch("/can_request_email_login")
        .then(r => r.json())
        .then(data => {
            if (data.allowed) {
                // Enable button if requests are allowed
                btn.disabled = false;
                btn.classList.remove("disabled");
            } else {
                // Check again in 60 seconds if not allowed
                setTimeout(checkLimit, 60000);
            }
        });
}

// Initial check
checkLimit();

// Navigate to login page when button is clicked
btn.addEventListener("click", () => {
    window.location.href = "/login";
});