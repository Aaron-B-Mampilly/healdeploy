"""
HealDeploy — Deployment Smoke Tests (test_deployment_smoke.py)
================================================================

Tests for deployment safeguards, frontend content verification, and
rollback readiness.  These tests run entirely offline.

Run with:
    python -m pytest tests/test_deployment_smoke.py -v
"""

import os
import tarfile
from pathlib import Path

import pytest

from app.app import create_app


REQUIRED_DASHBOARD_FILES = [
    "app/app.py",
    "app/dashboard.py",
    "app/templates/index.html",
    "app/static/css/dashboard.css",
    "app/static/js/dashboard.js",
]


def build_package(tmp_path: Path) -> Path:
    """Create a tar.gz archive of app/ and requirements.txt."""
    archive_path = tmp_path / "build" / "healdeploy-jenkins-1-abc1234.tar.gz"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as tar:
        for rel_file in REQUIRED_DASHBOARD_FILES:
            src = Path("app") / rel_file.replace("app/", "", 1)
            tar.add(src, arcname=rel_file)
        tar.add("requirements.txt", arcname="requirements.txt")
    return archive_path


def package_contains_files(archive_path: Path, required_files: list[str]) -> list[str]:
    """Return list of missing required files from a tar.gz archive."""
    missing = []
    with tarfile.open(archive_path, "r:gz") as tar:
        member_names = {m.name for m in tar.getmembers()}
        for required in required_files:
            if required not in member_names:
                missing.append(required)
    return missing


class TestDashboardFilesInPackage:
    """The release package must contain every required dashboard file."""

    def test_package_contains_all_required_files(self, tmp_path: Path):
        archive = build_package(tmp_path)
        missing = package_contains_files(archive, REQUIRED_DASHBOARD_FILES)
        assert missing == [], (
            f"Missing required dashboard files from package: {missing}"
        )

    def test_package_contains_requirements_txt(self, tmp_path: Path):
        archive = build_package(tmp_path)
        with tarfile.open(archive, "r:gz") as tar:
            names = {m.name for m in tar.getmembers()}
        assert "requirements.txt" in names

    def test_missing_dashboard_file_is_detected(self, tmp_path: Path):
        archive_path = tmp_path / "build" / "incomplete.tar.gz"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "w:gz") as tar:
            for rel_file in REQUIRED_DASHBOARD_FILES:
                if rel_file == "app/dashboard.py":
                    continue
                src = Path("app") / rel_file.replace("app/", "", 1)
                tar.add(src, arcname=rel_file)
        missing = package_contains_files(archive_path, REQUIRED_DASHBOARD_FILES)
        assert "app/dashboard.py" in missing


class TestFrontendContentVerification:
    """The rendered homepage must contain distinctive dashboard content."""

    @pytest.fixture()
    def client(self):
        app = create_app(test_config={"TESTING": True, "HEALDEPLOY_VERSION": "v-test"})
        return app.test_client()

    def test_homepage_contains_dashboard_heading(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"Ship with confidence" in response.data, (
            "Redesigned dashboard heading 'Ship with confidence' not found"
        )
        assert b"Recover without drama" in response.data, (
            "Redesigned dashboard heading 'Recover without drama' not found"
        )

    def test_homepage_references_css_asset(self, client):
        response = client.get("/")
        assert b"/static/css/dashboard.css" in response.data, (
            "Dashboard CSS asset reference not found in homepage"
        )

    def test_homepage_references_js_asset(self, client):
        response = client.get("/")
        assert b"/static/js/dashboard.js" in response.data, (
            "Dashboard JS asset reference not found in homepage"
        )

    def test_homepage_contains_health_status(self, client):
        response = client.get("/")
        assert b"healthy" in response.data.lower()

    def test_homepage_contains_version(self, client):
        response = client.get("/")
        assert b"v-test" in response.data

    def test_health_endpoint_reports_deployed_version(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert data["version"] == "v-test"


class TestCacheBustingOnStaticAssets:
    """CSS and JS asset URLs must include the version query param."""

    @pytest.fixture()
    def client(self):
        app = create_app(test_config={"TESTING": True, "HEALDEPLOY_VERSION": "v-test"})
        return app.test_client()

    def test_css_url_has_cache_buster(self, client):
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert 'dashboard.css' in html, "CSS asset URL not found in homepage"
        assert 'v=' in html, "CSS asset URL missing cache-busting version parameter"

    def test_js_url_has_cache_buster(self, client):
        response = client.get("/")
        html = response.data.decode("utf-8")
        assert 'dashboard.js' in html, "JS asset URL not found in homepage"
        assert 'v=' in html, "JS asset URL missing cache-busting version parameter"


class TestRollbackReadiness:
    """The rollback script and health check must be present and executable."""

    def test_rollback_script_exists(self):
        rollback_path = Path("deploy/rollback.sh")
        assert rollback_path.exists(), "deploy/rollback.sh must exist"
        assert os.access(rollback_path, os.X_OK), "deploy/rollback.sh must be executable"

    def test_deploy_script_exists(self):
        deploy_path = Path("deploy/deploy.sh")
        assert deploy_path.exists(), "deploy/deploy.sh must exist"
        assert os.access(deploy_path, os.X_OK), "deploy/deploy.sh must be executable"

    def test_health_check_exists(self):
        health_path = Path("deploy/health_check.py")
        assert health_path.exists(), "deploy/health_check.py must exist"

    def test_health_policy_exists(self):
        policy_path = Path("deploy/health_policy.json")
        assert policy_path.exists(), "deploy/health_policy.json must exist"


class TestJenkinsfileSSHConfiguration:
    """SSH must use port 22 with lowercase -p; SCP must use uppercase -P."""

    def test_jenkinsfile_ssh_port_22(self):
        jenkinsfile = Path("Jenkinsfile").read_text(encoding="utf-8")
        assert "SSH_PORT = '22'" in jenkinsfile, (
            "Jenkinsfile must set SSH_PORT = '22'"
        )
        assert '-p $SSH_PORT' in jenkinsfile, (
            "Jenkinsfile SSH_OPTS must use lowercase -p for SSH port"
        )
        assert '-P $SSH_PORT' in jenkinsfile, (
            "Jenkinsfile SCP_OPTS must use uppercase -P for SCP port"
        )

    def test_jenkinsfile_fault_mode_default_empty(self):
        jenkinsfile = Path("Jenkinsfile").read_text(encoding="utf-8")
        assert "defaultValue: ''" in jenkinsfile, (
            "Jenkinsfile FAULT_MODE parameter must default to empty string"
        )