/**
 * Image Upload Handler
 * ==================
 * Manages image preview and upload status display
 */

// Wait for DOM readiness
document.addEventListener("DOMContentLoaded", function () {
    // Element references
    const input = document.querySelector('input[type="file"]');
    const preview = document.getElementById("preview");
    const uploadingMessage = document.getElementById("uploading-message");

    // Image preview handler
    if (input) {
        input.addEventListener("change", function (event) {
            const file = event.target.files[0];
            if (file && preview) {
                // Create temporary URL for image preview
                preview.src = URL.createObjectURL(file);
            }
        });
    }

    // Upload status handler
    const form = document.querySelector("form[enctype]");
    if (form && uploadingMessage) {
        form.addEventListener("submit", function () {
            // Show upload status
            uploadingMessage.style.display = "block";
        });
    }
});