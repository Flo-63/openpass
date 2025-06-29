/**
 * Email Login Modal Handler
 * =======================
 * Manages the email login modal functionality including rate limiting,
 * modal display/hide, and click events.
 */

document.addEventListener("DOMContentLoaded", function () {
    // Get DOM elements
    const emailBtn = document.getElementById("emailLoginBtn");
    const emailModal = document.getElementById("emailModal");
    const closeBtn = document.getElementById("closeModalBtn");

    // Email login button click handler
    if (emailBtn && emailModal) {
        emailBtn.addEventListener("click", function (e) {
            e.preventDefault();

            // Check rate limiting before showing modal
            fetch("/email_check_limit", {
                method: "POST",
                headers: {
                    "X-CSRFToken": window.csrf_token,
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                body: ""
            })
            .then(res => {
                if (res.ok) {
                    // Show modal if rate limit not exceeded
                    emailModal.style.display = "block";
                } else if (res.status === 429) {
                    // Redirect to rate limit page if limit exceeded
                    window.location.href = "/rate_limited";
                }
            });
        });
    }

    // Modal close button handler
    if (closeBtn && emailModal) {
        closeBtn.addEventListener("click", function () {
            emailModal.style.display = "none";
        });
    }

    // Close modal when clicking outside
    window.addEventListener("click", function (event) {
        if (event.target === emailModal) {
            emailModal.style.display = "none";
        }
    });
});