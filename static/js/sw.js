/**
 * Service Worker Configuration
 * ==========================
 * Basic Service Worker setup with immediate activation
 */

// Install event handler
self.addEventListener('install', function(event) {
    // Skip waiting phase to become active immediately
    self.skipWaiting();
});

/**
 * Note: Fetch event listener is commented out since
 * no offline strategy is currently needed
 * 
 * Possible future implementations could include:
 * - Cache strategies
 * - Offline fallbacks
 * - Resource pre-caching
 */