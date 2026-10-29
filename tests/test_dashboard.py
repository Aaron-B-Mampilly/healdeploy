"""Tests for dashboard data derived from real deployment artifacts."""

import json
from pathlib import Path

import pytest

from app.app import create_app
from app.dashboard import build_dashboard_context


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_release(root: Path, release_id: str, version: str) -> None:
    release_dir = root / "releases" / release_id
    release_dir.mkdir(parents=True, exist_ok=True)
    (release_dir / ".env").write_text(
        f"HEALDEPLOY_VERSION={version}\nPYTHONUNBUFFERED=1\n",
        encoding="utf-8",
    )


def health_payload(
    version: str,
    passed: bool,
    finished_at: str,
    p95: float | None,
    successes: int,
    required: int = 9,
) -> dict:
    return {
        "started_at": finished_at,
        "finished_at": finished_at,
        "url": "http://127.0.0.1:8000/health",
        "expected_version": version,
        "policy": {
            "required_successes": required,
            "max_p95_latency_ms": 500,
        },
        "evaluation": {
            "passed": passed,
            "successes": successes,
            "required_successes": required,
            "p95_latency_ms": p95,
            "max_p95_latency_ms": 500,
            "failures": [],
        },
    }


@pytest.fixture()
def deployment_root(tmp_path: Path) -> Path:
    root = tmp_path / "healdeploy"
    write_release(root, "jenkins-10-74964d6", "v1.0.10")
    write_release(root, "jenkins-6-5ff39f4", "v1.0.6")
    write_release(root, "jenkins-4-bbb18ae", "v1.0.4")
    (root / "stable_release.txt").write_text("jenkins-10-74964d6\n", encoding="utf-8")

    shared = root / "shared"
    write_json(
        shared / "health-jenkins-10-74964d6.json",
        health_payload("v1.0.10", True, "2026-10-29T01:00:00Z", 8.33, 10),
    )
    write_json(
        shared / "health-jenkins-4-bbb18ae.json",
        health_payload("v1.0.4", False, "2026-10-28T22:03:00Z", 1009.95, 10),
    )
    write_json(
        shared / "health-rollback-jenkins-4-bbb18ae.json",
        health_payload("v1.0.6", True, "2026-10-28T22:04:00Z", 7.25, 10),
    )
    write_json(
        shared / "incident_report.json",
        {
            "release_id": "jenkins-4-bbb18ae",
            "app_version": "v1.0.4",
            "failure_reason": "health policy failed for release jenkins-4-bbb18ae",
            "detected_at": "2026-10-28T22:03:57Z",
            "rollback_started_at": "2026-10-28T22:03:57Z",
            "recovery_completed_at": "2026-10-28T22:04:39Z",
            "recovered_release": "jenkins-6-5ff39f4",
            "recovery_verified": True,
            "final_status": "recovered",
        },
    )
    return root


def test_context_uses_real_artifacts(deployment_root: Path) -> None:
    context = build_dashboard_context(deployment_root, "v1.0.10")

    assert context["history_available"] is True
    assert context["timeline_total"] == 4
    assert context["latest_deployment"]["release_id"] == "jenkins-10-74964d6"
    assert context["latest_deployment"]["event_label"] == "Release promoted"
    assert context["latest_deployment"]["version"] == "v1.0.10"
    assert context["latest_recovery"]["status_label"] == "Recovered"
    assert context["latest_recovery"]["recovered_release"] == "jenkins-6-5ff39f4"
    assert context["latest_recovery"]["recovered_version"] == "v1.0.6"
    assert context["latest_recovery"]["recovery_verified"] is True
    assert context["stable_release"]["release_id"] == "jenkins-10-74964d6"


def test_timeline_contains_release_and_recovery_events(deployment_root: Path) -> None:
    context = build_dashboard_context(deployment_root, "v1.0.10")
    labels = [event["event_label"] for event in context["timeline"]]

    assert labels == [
        "Release promoted",
        "Recovery verified",
        "Rollback initiated",
        "Release rejected",
    ]

    rejected = next(
        event for event in context["timeline"] if event["event_label"] == "Release rejected"
    )
    assert "exceeded the 500 ms budget" in rejected["detail"]

    verified = next(
        event for event in context["timeline"] if event["event_label"] == "Recovery verified"
    )
    assert "p95 7.2 ms" in verified["detail"]


def test_home_page_renders_real_dashboard_data(deployment_root: Path) -> None:
    app = create_app(
        test_config={
            "TESTING": True,
            "HEALDEPLOY_VERSION": "v1.0.10",
            "HEALDEPLOY_ROOT": str(deployment_root),
        }
    )
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"jenkins-10-74964d6" in response.data
    assert b"Recovered" in response.data
    assert b"Recovery verified" in response.data
    assert b"v1.0.6" in response.data
    assert b"Deployment activity" in response.data


def test_home_page_has_honest_empty_state(tmp_path: Path) -> None:
    app = create_app(
        test_config={
            "TESTING": True,
            "HEALDEPLOY_VERSION": "v-test",
            "HEALDEPLOY_ROOT": str(tmp_path / "missing"),
        }
    )
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"No deployment history in this environment" in response.data
    assert b"No record" in response.data
    assert b"No incident" in response.data


def test_corrupt_artifacts_do_not_break_dashboard(tmp_path: Path) -> None:
    shared = tmp_path / "shared"
    shared.mkdir(parents=True)
    (shared / "health-broken.json").write_text("{not-json", encoding="utf-8")
    (shared / "incident_report.json").write_text("{not-json", encoding="utf-8")

    app = create_app(
        test_config={
            "TESTING": True,
            "HEALDEPLOY_VERSION": "v-test",
            "HEALDEPLOY_ROOT": str(tmp_path),
        }
    )
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"No deployment history in this environment" in response.data


def test_health_endpoint_contract_is_unchanged(deployment_root: Path) -> None:
    app = create_app(
        test_config={
            "TESTING": True,
            "HEALDEPLOY_VERSION": "v1.0.10",
            "HEALDEPLOY_ROOT": str(deployment_root),
        }
    )
    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.content_type == "application/json"
    assert response.get_json() == {"status": "healthy", "version": "v1.0.10"}
