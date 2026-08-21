"""
===============================================================================
Project   : openpass
Module    : core/middleware.py
Created   : 2025-10-17
Author    : Florian
Purpose   : This provides middleware for implementing Content Security Policy (CSP) in Flask applications.

@docstyle: google
@language: english
@voice: imperative
===============================================================================
"""

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
    A middleware function that integrates Content Security Policy (CSP) management into a Flask application.

    #### Description:
    - This middleware provides dynamic CSP generation and enforcement.
    - It includes a mechanism to set a cryptographic nonce for each request and applies this nonce to specific CSP
      directives.

    #### Parameters:
    - `app` (Flask): The Flask application instance to which the middleware is applied.
    - `report_only` (bool): If `True`, the middleware adds a `Content-Security-Policy-Report-Only` header instead of
      enforcing the policy.
    - `report_uri` (str): The URI where CSP violation reports should be sent.

    #### Purpose:
    - Enhances the security of the Flask application by preventing content injection attacks such as Cross-Site
      Scripting (XSS).
    - The middleware dynamically enables safe inline scripts and styles using a nonce while restricting other
      potentially harmful sources.

    #### Behavior:
    - Before each request, a unique nonce is generated and stored in the request context (`g.csp_nonce`).
    - After each request, a CSP header is added to the HTTP response, including dynamic values such as the nonce,
      predefined directives, and additional configurations.

    #### Notes:
    - The CSP includes a wide range of directives tailored for common use-cases, including support for CDNs, Google
      OAuth, and map services.
    - Violations can be monitored using the `report-only` mode without enforcing the restrictions.
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

        # Only sources the application actually loads are listed. A permissive
        # allow-list of public CDNs is a well-known way around a nonce-based policy:
        # several of them host libraries that can be coerced into executing arbitrary
        # markup, so an attacker with an injection point can load one of those instead
        # of guessing the nonce. Every script this app serves comes from `self`, so
        # script-src needs no third-party origin at all. jsDelivr stays in the style
        # directives because templates/upload_photo.html pulls Bootstrap CSS from it.
        csp = {
            'default-src': ["'self'"],  # Allow content only from own domain by default
            'script-src': [
                "'self'",
                f"'nonce-{getattr(g, 'csp_nonce', '')}'"  # Dynamic nonce for inline scripts
            ],
            'script-src-elem': [
                "'self'",
                f"'nonce-{getattr(g, 'csp_nonce', '')}'"
            ],
            'style-src': [
                "'self'",
                "https://cdn.jsdelivr.net",       # Bootstrap CSS on upload_photo.html
                f"'nonce-{getattr(g, 'csp_nonce', '')}'"  # Dynamic nonce for inline styles
            ],
            # Inline style *attributes* are used throughout the templates. Without this
            # directive they would fall back to style-src and break the layout as soon
            # as the policy is enforced rather than merely reported.
            'style-src-attr': ["'unsafe-inline'"],
            'style-src-elem': [
                "'self'",
                "'unsafe-inline'",
                "https://cdn.jsdelivr.net",
            ],
            'img-src': [
                "'self'",
                "data:",                         # QR codes are rendered as data: URIs
            ],
            'font-src': [
                "'self'",
                "data:"                          # Allow data: URIs for fonts
            ],
            'connect-src': [
                "'self'",
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

        # Generate CSP header string. Empty sources are dropped: `oauth_domain` is an
        # empty string when no OAuth provider is configured, and an empty entry would
        # otherwise leave a stray separator in the directive.
        csp_header = "; ".join(
            f"{directive} {' '.join(filter(None, sources))}"
            for directive, sources in csp.items()
        )

        # Enforce the policy when configured to; otherwise keep reporting only.
        enforce = app.config.get("CSP_ENFORCE", not report_only)
        header_name = 'Content-Security-Policy' if enforce else 'Content-Security-Policy-Report-Only'
        response.headers[header_name] = csp_header

        # Baseline security headers. These are safe to send unconditionally and do not
        # depend on the CSP being enforced.
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        # Membership and photo tokens travel in URLs, so never leak a full URL to a
        # third-party origin via the Referer header.
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy', 'geolocation=(), microphone=(), camera=(self)'
        )

        # HSTS. Email login links carry a valid credential in the URL, so a single
        # plaintext request is enough to hand it over. The header is only sent over a
        # secure connection – browsers ignore it on plain HTTP anyway, and sending it
        # in local development would pin `localhost` to HTTPS for the configured
        # duration, which is a genuinely painful thing to undo.
        max_age = app.config.get('HSTS_MAX_AGE', 0)
        if max_age and request.is_secure:
            value = f'max-age={max_age}'
            if app.config.get('HSTS_INCLUDE_SUBDOMAINS'):
                value += '; includeSubDomains'
            response.headers.setdefault('Strict-Transport-Security', value)

        return response

    return app