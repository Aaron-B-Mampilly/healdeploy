"""
HealDeploy — Flask Application
================================
Core application factory and route definitions.

Routes:
  GET /         — Home page (HTML)
  GET /health   — Health check endpoint (JSON)

Configuration:
  HEALDEPLOY_VERSION  — Application version string (default: "v1.0.0")
                        Set this environment variable to control the displayed
                        and reported version without changing any source code.

Usage (development):
  set HEALDEPLOY_VERSION=v1.0.0
  python -m flask --app app.app run

Usage (production via Gunicorn on Linux):
  gunicorn --bind 0.0.0.0:8000 "app.app:create_app()"
"""

import os
from flask import Flask, jsonify, render_template


def create_app(test_config=None):
    """
    Application factory.

    Parameters
    ----------
    test_config : dict, optional
        Configuration overrides for unit testing.  When provided, these
        values replace the defaults so tests run in isolation without
        reading from environment variables.

    Returns
    -------
    Flask
        A configured Flask application instance.
    """
    app = Flask(__name__, template_folder="templates")

    # ── Default configuration ──────────────────────────────────────────────
    # Read the version from the environment so it can be set at deploy time.
    # The fallback "v1.0.0" is used only when the variable is not set.
    app.config.setdefault("HEALDEPLOY_VERSION", os.environ.get("HEALDEPLOY_VERSION", "v1.0.0"))
    app.config.setdefault("TESTING", False)

    # ── Test configuration override ────────────────────────────────────────
    if test_config is not None:
        app.config.update(test_config)

    # ── Routes ─────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        """
        Home page.

        Renders an HTML page showing the project name, version and
        current health status.  The version comes from app.config so
        tests can override it cleanly.
        """
        version = app.config["HEALDEPLOY_VERSION"]
        return render_template("index.html", version=version, status="healthy")

    @app.route("/health")
    def health():
        """
        Health check endpoint.

        Returns a JSON object that Jenkins will parse during deployment
        validation.  HTTP 200 means the application is healthy.

        Example response:
            {"status": "healthy", "version": "v1.0.0"}
        """
        version = app.config["HEALDEPLOY_VERSION"]
        return jsonify({"status": "healthy", "version": version}), 200

    return app
