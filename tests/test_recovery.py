"""
HealDeploy — Recovery Tests (test_recovery.py)
================================================
Phase 2 status: Application-level tests only.

The self-healing rollback and recovery verification logic will be
implemented in Phase 4 (Jenkins pipeline) and Phase 5 (health check
scripts and evaluation).  At that stage, this file will contain tests
that validate the automatic recovery workflow end-to-end.

What is NOT tested here yet (and why):
  - Automatic rollback triggering      — requires Jenkins pipeline (Phase 4)
  - Azure VM deployment interaction    — requires Terraform provisioning (Phase 3)
  - Recovery verification reports      — evaluation scripts planned for Phase 5
  - Faulty-release simulation          — test branches/tags not yet created

What IS tested here (Phase 2 scope):
  - The /health endpoint correctly signals a healthy state after app startup.
  - A version change (simulating a new release) is reflected immediately.
  - A version change is also visible on the home page.

These tests serve as the foundation that the self-healing system will
build upon: if /health stops returning 200 + {"status":"healthy"} after
a deployment, Jenkins will trigger rollback.
"""

import json
import pytest
from app.app import create_app


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def healthy_client():
    """Test client configured to simulate a healthy initial release."""
    app = create_app(test_config={
        "TESTING": True,
        "HEALDEPLOY_VERSION": "v1.0.0",
    })
    return app.test_client()


@pytest.fixture()
def new_release_client():
    """Test client configured to simulate a new release (v1.1.0)."""
    app = create_app(test_config={
        "TESTING": True,
        "HEALDEPLOY_VERSION": "v1.1.0",
    })
    return app.test_client()


# ── Health signal tests (foundation for recovery logic) ───────────────────────

class TestHealthSignal:
    """
    Validate that /health reliably signals application health.

    Jenkins will poll this endpoint after every deployment.  These tests
    confirm that the endpoint contract is stable before the pipeline is wired.
    """

    def test_health_signals_healthy_on_startup(self, healthy_client):
        """/health must return HTTP 200 for a freshly started application."""
        response = healthy_client.get("/health")
        assert response.status_code == 200

    def test_health_body_signals_healthy_status(self, healthy_client):
        """/health body must contain status='healthy' (not 'degraded' etc.)."""
        response = healthy_client.get("/health")
        data = json.loads(response.data)
        assert data["status"] == "healthy", (
            f"Health endpoint must report 'healthy'; got '{data.get('status')}'"
        )

    def test_health_includes_version_v1(self, healthy_client):
        """/health version field must match the configured release version."""
        response = healthy_client.get("/health")
        data = json.loads(response.data)
        assert data["version"] == "v1.0.0"


# ── Version-change simulation (new release) ───────────────────────────────────

class TestVersionChange:
    """
    Simulate a new release by switching to a different version config.

    In Phase 4, Jenkins will deploy a new version and call /health.
    This test confirms that a version change is immediately reflected
    in both the health endpoint and the home page — which is the
    baseline requirement for the self-healing detection logic.
    """

    def test_new_release_health_returns_200(self, new_release_client):
        """After a version bump, /health must still return HTTP 200."""
        response = new_release_client.get("/health")
        assert response.status_code == 200

    def test_new_release_version_reflected_in_health(self, new_release_client):
        """New release version must appear in /health response."""
        response = new_release_client.get("/health")
        data = json.loads(response.data)
        assert data["version"] == "v1.1.0", (
            f"Expected new version 'v1.1.0', got '{data.get('version')}'"
        )

    def test_new_release_version_reflected_on_home_page(self, new_release_client):
        """New release version must be visible on the home page."""
        response = new_release_client.get("/")
        assert b"v1.1.0" in response.data, (
            "New version not visible on home page after simulated release"
        )

    def test_new_release_status_still_healthy(self, new_release_client):
        """A simple version bump must not degrade the health status."""
        response = new_release_client.get("/health")
        data = json.loads(response.data)
        assert data["status"] == "healthy"


# ── Deferred: full recovery workflow ─────────────────────────────────────────
# The following scenarios will be implemented in Phase 4 / Phase 5:
#
#   test_rollback_triggered_on_unhealthy_release()
#     → Simulate a faulty release → verify Jenkins detects health failure
#     → Verify rollback script is invoked
#     → Verify previous version is restored
#
#   test_recovery_verification_passes_after_rollback()
#     → After rollback, /health must return {"status":"healthy"}
#     → Recovery report must document the event
#
#   test_stable_version_preserved_in_state_file()
#     → Verify the deployment state file records the last known-good version
