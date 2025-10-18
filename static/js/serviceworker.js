(() => {
    // Verhindere doppeltes Ausführen
    if (window.__serviceWorkerInitialized) return;
    window.__serviceWorkerInitialized = true;

    let deferredPrompt = null;

    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;

        const btn = document.getElementById('installBtn');
        if (!btn) return;

        btn.classList.remove('hidden');
        btn.style.display = 'inline-block';

        btn.addEventListener(
            'click',
            async () => {
                if (!deferredPrompt) return;

                deferredPrompt.prompt();
                const { outcome } = await deferredPrompt.userChoice;
                console.log(`User response to the install prompt: ${outcome}`);

                deferredPrompt = null;
                btn.classList.add('hidden');
            },
            { once: true } // Click-Handler nur einmal ausführen
        );
    });

    // Optional: Service Worker Registrierung
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker
            .register('/serviceworker.js', { scope: '/' })
            .then(() => console.log('✅ Service Worker registered'))
            .catch((err) => console.warn('⚠️ Service Worker registration failed:', err));
    }
})();
