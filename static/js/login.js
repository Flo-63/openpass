/*
===============================================================================
Project   : openpass
Module    : static/js/login.js
Created   : 2025-10-18
Author    : Florian
Purpose   : Used to handle email login modal display, closing, and rate limiting checks.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
*/



document.addEventListener("DOMContentLoaded", function () {
    const emailBtn = document.getElementById("emailLoginBtn");
    const emailModal = document.getElementById("emailModal");
    const closeBtn = document.getElementById("closeModalBtn");

    // Get CSRF token safely from DOM (no inline JS needed)
    const csrfTokenInput = document.querySelector('input[name="csrf_token"]');
    const csrfToken = csrfTokenInput ? csrfTokenInput.value : "";

    // Email login button click handler
    if (emailBtn && emailModal) {
        emailBtn.addEventListener("click", function (e) {
            e.preventDefault();

            fetch("/email_check_limit", {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                body: ""
            })
            .then(res => {
                if (res.ok) {
                    emailModal.style.display = "block";
                } else if (res.status === 429) {
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
