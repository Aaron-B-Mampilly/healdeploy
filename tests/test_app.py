"""
HealDeploy — Application Tests (test_app.py)
=============================================
Tests for the Flask application routes, configuration and factory.

All tests use Flask's built-in test client and run entirely offline.
No Azure, Jenkins or network connection is required.

Run with:
    python -m pytest tests/test_app.py -v
"""

import json
import pytest
from app.app import create_app


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def app():
    """
    Create a test application instance with a known version string.

    Using a fixed version ("v-test") makes assertions predictable regardless
    of what HEALDEPLOY_VERSION is set to in the environment.
    """
    app = create_app(test_config={
        "TESTING": True,
        "HEALDEPLOY_VERSION": "v-test",
    })
    yield app


@pytest.fixture()
def client(app):
    """Return a Flask test client bound to the test application."""
    return app.test_client()


# ── Home page tests ───────────────────────────────────────────────────────────

class TestHomePage:
    """Tests for the GET / route."""

    def test_home_returns_200(self, client):
        """Home page must respond with HTTP 200."""
        response = client.get("/")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}"
        )

    def test_home_content_type_is_html(self, client):
        """Home page must return an HTML content type."""
        response = client.get("/")
        assert "text/html" in response.content_type

    def test_home_contains_project_name(self, client):
        """Home page must display the project name 'HealDeploy'."""
        response = client.get("/")
        assert b"HealDeploy" in response.data, (
            "Project name 'HealDeploy' not found in home page response"
        )

    def test_home_contains_version(self, client):
        """Home page must display the configured version string."""
        response = client.get("/")
        assert b"v-test" in response.data, (
            "Expected version 'v-test' to appear on home page"
        )

    def test_home_contains_health_status(self, client):
        """Home page must display the health status."""
        response = client.get("/")
        assert b"healthy" in response.data, (
            "Expected 'healthy' status on home page"
        )


# ── Health endpoint tests ─────────────────────────────────────────────────────

class TestHealthEndpoint:
    """Tests for the GET /health route."""

    def test_health_returns_200(self, client):
        """/health must respond with HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}"
        )

    def test_health_content_type_is_json(self, client):
        """/health must return application/json content type."""
        response = client.get("/health")
        assert response.content_type == "application/json", (
            f"Expected application/json, got {response.content_type}"
        )

    def test_health_response_is_valid_json(self, client):
        """/health body must be parseable as JSON."""
        response = client.get("/health")
        try:
            data = json.loads(response.data)
        except json.JSONDecodeError as exc:
            pytest.fail(f"/health returned invalid JSON: {exc}")

    def test_health_contains_status_field(self, client):
        """/health JSON must contain a 'status' field."""
        response = client.get("/health")
        data = json.loads(response.data)
        assert "status" in data, "Missing 'status' field in /health response"

    def test_health_status_is_healthy(self, client):
        """/health must report status 'healthy'."""
        response = client.get("/health")
        data = json.loads(response.data)
        assert data["status"] == "healthy", (
            f"Expected status 'healthy', got '{data.get('status')}'"
        )

    def test_health_contains_version_field(self, client):
        """/health JSON must contain a 'version' field."""
        response = client.get("/health")
        data = json.loads(response.data)
        assert "version" in data, "Missing 'version' field in /health response"

    def test_health_version_matches_config(self, client):
        """/health version must match the configured HEALDEPLOY_VERSION."""
        response = client.get("/health")
        data = json.loads(response.data)
        assert data["version"] == "v-test", (
            f"Expected version 'v-test', got '{data.get('version')}'"
        )


# ── Application factory tests ─────────────────────────────────────────────────

class TestAppFactory:
    """Tests for the create_app application factory."""

    def test_factory_creates_app(self):
        """create_app() must return a Flask app instance."""
        from flask import Flask
        app = create_app()
        assert isinstance(app, Flask)

    def test_factory_accepts_test_config(self):
        """create_app() must accept and apply test_config overrides."""
        app = create_app(test_config={"HEALDEPLOY_VERSION": "v-custom"})
        assert app.config["HEALDEPLOY_VERSION"] == "v-custom"

    def test_factory_default_version_is_set(self):
        """create_app() without config must set a default version."""
        import os
        # Temporarily unset the env var so we get the code default
        original = os.environ.pop("HEALDEPLOY_VERSION", None)
        try:
            app = create_app()
            assert app.config["HEALDEPLOY_VERSION"] == "v1.0.0"
        finally:
            if original is not None:
                os.environ["HEALDEPLOY_VERSION"] = original

    def test_version_override_via_env_var(self, monkeypatch):
        """HEALDEPLOY_VERSION env var must override the default version."""
        monkeypatch.setenv("HEALDEPLOY_VERSION", "v2.5.0")
        app = create_app()
        assert app.config["HEALDEPLOY_VERSION"] == "v2.5.0"


# ── 404 / routing tests ───────────────────────────────────────────────────────

class TestErrorHandling:
    """Tests for undefined routes."""

    def test_unknown_route_returns_404(self, client):
        """An undefined route must return HTTP 404."""
        response = client.get("/does-not-exist")
        assert response.status_code == 404, (
            f"Expected 404 for unknown route, got {response.status_code}"
        )

    def test_another_unknown_route_returns_404(self, client):
        """A second undefined route must also return HTTP 404."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
