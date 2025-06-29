# middleware.py
# Standard Library
import logging
import secrets
from urllib.parse import urlparse

# Third-Party
from flask import (
    Flask,
    g,
    make_response,
    request
)

# Initialize logger for CSP-related events
csp_logger = logging.getLogger("csp_logger")

def csp_middleware(app, report_only=False, report_uri='/csp-report'):
    """
    Middleware for implementing Content Security Policy (CSP).

    #### Parameters:
    - `app`: Flask app instance to which the middleware is applied.
    - `report_only` (bool, optional): If `True`, the policy is activated in `Content-Security-Policy-Report-Only` mode.
      This allows reporting violations without blocking them. Default: `False`.
    - `report_uri` (str, optional): The URI to which CSP violation reports should be sent. Default: `/csp-report`.

    #### Operation:
    - Generates a dynamic `nonce` for each request and adds it as global variable `g.csp_nonce`.
    - Defines a Content Security Policy based on app configurations and dynamic domains.
    - Sets the corresponding HTTP header (`Content-Security-Policy` or `Content-Security-Policy-Report-Only`).

    #### CSP Directives:
    - Default restrictive rules for resources like `script-src`, `style-src`, `frame-ancestors`, etc.
    - Report-URI for capturing CSP violations.

    #### Return:
    - The enhanced Flask app instance with configured CSP headers.

    #### Notes:
    This middleware provides complete protection through CSP headers and dynamic adaptations
    to external domains used by the app. It can be used in combination with referrer checks,
    but the CSP directives take the primary security role.
    """

    @app.before_request
    def set_csp_nonce():
        """
            Sets a dynamic nonce for the Content Security Policy (CSP).

            #### Description:
            - This function is executed before each request.
            - Generates a unique nonce (Number used once) for the current request.
            - Stores the nonce in the Flask `g` context variable (`g.csp_nonce`) for use in CSP directives.

            #### Purpose:
            - The nonce is used in the `script-src` and `style-src` directives to allow execution of inline scripts and
              styles that are marked with this nonce.
            - Protects against Cross-Site Scripting (XSS) attacks by only allowing trusted scripts and styles.

            #### Return:
            - No direct return, the nonce is stored in `g.csp_nonce`.

            #### Notes:
            - This function is an essential component of the dynamic CSP implementation.
        """
        # Generate a cryptographically secure random hex string
        if request.path.endswith("/csp-report"):
            return
        g.csp_nonce = secrets.token_hex(16)

    @app.after_request
    def add_csp_header(response):
        """
        Adds the Content Security Policy (CSP) header to the response.

        #### Parameters:
        - `response`: The HTTP response that is sent to the client.

        #### Description:
        - This function is executed after each request.
        - Generates the Content Security Policy (CSP) header based on predefined directives and dynamic
          configurations such as the nonce (`g.csp_nonce`).
        - Adds the generated header (`Content-Security-Policy` or `Content-Security-Policy-Report-Only`) to the response.

        #### CSP Directives:
        - Defines sources for scripts, styles, images, frames, etc.
        - Uses dynamic values such as:
            - Dynamic nonce (`g.csp_nonce`)
        - Includes the `report-uri` when specified to report violations.

        #### Return:
        - `response`: The modified HTTP response with the added CSP header.

        #### Notes:
        - This function is crucial for enforcing the CSP and protects the application against
          content injection attacks (e.g., XSS).
        """

        # Extract OAuth authorization URL from app config
        oauth_authorize_url = app.config.get('OAUTH_AUTHORIZE_URL', '')
        parsed_url = urlparse(oauth_authorize_url)
        # Construct OAuth domain for CSP rules
        oauth_domain = f"{parsed_url.scheme}://{parsed_url.netloc}" if parsed_url.netloc else ''

        csp = {
            'default-src': ["'self'"],  # Allow content only from own domain by default
            'script-src': [
                "'self'",
                "https://cdnjs.cloudflare.com",  # CloudFlare CDN for JavaScript libraries
                "https://cdn.jsdelivr.net",      # jsDelivr CDN
                "https://code.jquery.com",       # jQuery CDN
                "https://accounts.google.com",    # Required for Google OAuth
                oauth_domain,                     # OAuth provider domain
                "https://cdn.plot.ly",           # Plotly visualization library
                "https://kit.fontawesome.com",   # FontAwesome icons
                "https://stackpath.bootstrapcdn.com",  # Bootstrap CDN
                f"'nonce-{getattr(g, 'csp_nonce', '')}'"  # Dynamic nonce for inline scripts
            ],
            'script-src-elem': [
                "'self'",
                "http://localhost:5000",
                "https://cdnjs.cloudflare.com",
                "https://cdn.jsdelivr.net",
                "https://code.jquery.com",
                "https://accounts.google.com",
                oauth_domain,
                "https://cdn.plot.ly",
                "https://kit.fontawesome.com",
                "https://stackpath.bootstrapcdn.com",
                f"'nonce-{getattr(g, 'csp_nonce', '')}'"
            ],
            'style-src': [
                "'self'",
                "https://cdnjs.cloudflare.com",
                "https://cdn.jsdelivr.net",       # Allows external Bootstrap and Select2
                "https://code.jquery.com",        # jQuery UI CSS
                "https://fonts.googleapis.com",   # Google Fonts and Material Icons
                "https://stackpath.bootstrapcdn.com",
                "https://maxcdn.bootstrapcdn.com",
                "https://unpkg.com",
                f"'nonce-{getattr(g, 'csp_nonce', '')}'"  # Dynamic nonce for inline styles
            ],
            'style-src-elem': [
                "'self'",
                "http://localhost:5000",
                "https://cdnjs.cloudflare.com",
                "https://cdn.jsdelivr.net",
                "https://code.jquery.com",
                "https://fonts.googleapis.com",
                "https://stackpath.bootstrapcdn.com",
                "https://maxcdn.bootstrapcdn.com",
                "https://unpkg.com",
                f"'nonce-{getattr(g, 'csp_nonce', '')}'"
            ],
            'img-src': [
                "'self'",
                "data:",                         # Allow data: URIs for images
                "https://*.tile.openstreetmap.org",  # Map tiles from OpenStreetMap
                "https://*.tile.thunderforest.com",  # Alternative map tiles
                "https://*.tile.opentopomap.org",    # Topographic map tiles
                "https://unpkg.com",
                "https://server.arcgisonline.com",   # ArcGIS map services
            ],
            'font-src': [
                # Sources for web fonts
                "'self'",
                "https://fonts.gstatic.com",     # Google Fonts storage
                "https://fonts.googleapis.com",   # Google Fonts API
                "https://cdn.jsdelivr.net",
                "https://cdnjs.cloudflare.com",
                "https://maxcdn.bootstrapcdn.com",
                "data:"                          # Allow data: URIs for fonts
            ],
            'connect-src': [
                "'self'",
                "https://accounts.google.com",    # Google OAuth connections
                "https://www.googleapis.com",     # Google API connections
                "https://cdn.jsdelivr.net",
                oauth_domain
            ],
            'object-src': ["'none'"],            # Disable embedded objects (plugins)
            'media-src': ["'self'"],             # Allow media only from own domain
            'form-action': ["'self'"],           # Restrict form submissions to own domain
            'frame-src': [
                "'self'",
                oauth_domain,                     # Allow OAuth provider in frames
            ],
            'frame-ancestors': [
                "'self'",                        # Control who can embed your site
            ],
            'worker-src': ["'self'"],            # Restrict Web Workers to own domain
            'base-uri': ["'self'"],              # Restrict <base> tag URLs
        }

        # Add report-uri if specified
        if report_uri:
            csp['report-uri'] = [report_uri]

        # Generate CSP header string
        csp_header = "; ".join(
            f"{directive} {' '.join(sources)}"
            for directive, sources in csp.items()
        )

        # Set appropriate header based on report_only flag
        header_name = 'Content-Security-Policy-Report-Only' if report_only else 'Content-Security-Policy'
        response.headers[header_name] = csp_header
        return response

    return app