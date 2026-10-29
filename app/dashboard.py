"""Read-only dashboard data derived from HealDeploy deployment artifacts."""

from __future__ import annotations

import json
import os
import platform
import re
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

TIMELINE_LIMIT = 8
MAX_HEALTH_FILES = 40
RELEASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
REPO_URL = "https://github.com/Aaron-B-Mampilly/healdeploy"
JENKINS_JOB = "healdeploy"

RECOVERY_STATUS = {
    "recovered": ("Recovered", "success", "shield-check"),
    "rollback_failed": ("Rollback failed", "danger", "alert-triangle"),
    "no_rollback_target": ("No rollback target", "warning", "alert-circle"),
    "deployment_failed": ("Deployment failed", "danger", "x-circle"),
}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _safe_release_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value and RELEASE_ID_PATTERN.fullmatch(value):
        return value
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: Any) -> str | None:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    return parsed.strftime("%d %b %Y, %H:%M UTC")


def _format_duration(seconds: Any) -> str | None:
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return None
    total = int(round(seconds))
    if total < 60:
        return f"{total}s"
    minutes, remainder = divmod(total, 60)
    return f"{minutes}m {remainder:02d}s"


def _format_latency(value: Any) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    return f"{value:.1f} ms"


def _release_version(releases_dir: Path, release_id: str | None) -> str | None:
    release_id = _safe_release_id(release_id)
    if not release_id:
        return None
    text = _read_text(releases_dir / release_id / ".env")
    if not text:
        return None
    for line in text.splitlines():
        if line.startswith("HEALDEPLOY_VERSION="):
            value = line.split("=", 1)[1].strip()
            return value or None
    return None


def _package_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _current_release(root: Path) -> str | None:
    current = root / "current"
    try:
        if not current.exists() and not current.is_symlink():
            return None
        resolved = Path(os.path.realpath(current))
    except OSError:
        return None
    if not resolved.is_dir():
        return None
    return _safe_release_id(resolved.name)


def _health_files(shared_dir: Path) -> list[Path]:
    try:
        files = list(shared_dir.glob("health-*.json"))
    except OSError:
        return []

    def mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    return sorted(files, key=mtime, reverse=True)[:MAX_HEALTH_FILES]


def _health_event(path: Path, releases_dir: Path) -> dict[str, Any] | None:
    data = _read_json(path)
    if not data:
        return None

    name = path.name
    is_rollback = name.startswith("health-rollback-")
    if is_rollback:
        release_id = _safe_release_id(name[len("health-rollback-"):-len(".json")])
        event_type = "recovery"
    elif name.startswith("health-") and name.endswith(".json"):
        release_id = _safe_release_id(name[len("health-"):-len(".json")])
        event_type = "deployment"
    else:
        return None

    if not release_id:
        return None

    evaluation = data.get("evaluation")
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    passed = bool(evaluation.get("passed"))
    version = data.get("expected_version") or _release_version(releases_dir, release_id)
    version = str(version).strip() if version else None
    p95 = evaluation.get("p95_latency_ms")
    max_p95 = evaluation.get("max_p95_latency_ms")
    successes = evaluation.get("successes")
    required = evaluation.get("required_successes")
    latency = _format_latency(p95)

    finished = data.get("finished_at") or data.get("started_at")
    parsed = _parse_timestamp(finished)
    if parsed is None:
        try:
            parsed = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            parsed = None

    timestamp_iso = parsed.isoformat().replace("+00:00", "Z") if parsed else None

    if event_type == "recovery":
        if passed:
            label, status, icon = "Recovery verified", "success", "shield-check"
            detail = (
                f"Stable release healthy · p95 {latency}"
                if latency
                else "Stable release passed the health policy"
            )
        else:
            label, status, icon = "Recovery verification failed", "danger", "alert-triangle"
            detail = "Restored release did not satisfy the health policy"
    elif passed:
        label, status, icon = "Release promoted", "success", "rocket"
        detail_parts = []
        if latency:
            detail_parts.append(f"p95 {latency}")
        if isinstance(successes, int) and isinstance(required, int):
            detail_parts.append(f"{successes}/{required} probes")
        detail = " · ".join(detail_parts) or "Health policy passed"
    else:
        label, status, icon = "Release rejected", "danger", "alert-triangle"
        if (
            isinstance(p95, (int, float))
            and isinstance(max_p95, (int, float))
            and p95 >= max_p95
        ):
            detail = f"p95 {latency} exceeded the {max_p95:.0f} ms budget"
        elif isinstance(successes, int) and isinstance(required, int):
            detail = f"{successes}/{required} probes passed"
        else:
            detail = "Health policy failed"

    return {
        "type": event_type,
        "event_label": label,
        "status": status,
        "icon": icon,
        "release_id": release_id,
        "version": version,
        "timestamp": _format_timestamp(timestamp_iso) or "Time unavailable",
        "timestamp_iso": timestamp_iso,
        "detail": detail,
        "_sort_time": parsed or datetime.min.replace(tzinfo=timezone.utc),
    }


def _incident_context(incident: dict[str, Any], releases_dir: Path) -> dict[str, Any]:
    final_status = str(incident.get("final_status") or "unknown")
    status_label, status_class, icon = RECOVERY_STATUS.get(
        final_status, ("Recorded", "neutral", "activity")
    )

    release_id = _safe_release_id(incident.get("release_id"))
    recovered_release = _safe_release_id(incident.get("recovered_release"))
    detected_at = incident.get("detected_at")
    rollback_started_at = incident.get("rollback_started_at")
    recovery_completed_at = incident.get("recovery_completed_at")

    detected_dt = _parse_timestamp(detected_at)
    rollback_dt = _parse_timestamp(rollback_started_at)
    completed_dt = _parse_timestamp(recovery_completed_at)

    duration_seconds = None
    if detected_dt and completed_dt:
        duration_seconds = max(0.0, (completed_dt - detected_dt).total_seconds())

    return {
        "final_status": final_status,
        "status_label": status_label,
        "status_class": status_class,
        "icon": icon,
        "release_id": release_id,
        "version": incident.get("app_version") or _release_version(releases_dir, release_id),
        "recovered_release": recovered_release,
        "recovered_version": _release_version(releases_dir, recovered_release),
        "recovery_verified": bool(incident.get("recovery_verified")),
        "failure_reason": incident.get("failure_reason") or "No failure reason recorded",
        "detected_at": _format_timestamp(detected_at),
        "detected_at_iso": detected_at if detected_dt else None,
        "rollback_started_at": _format_timestamp(rollback_started_at),
        "rollback_started_at_iso": rollback_started_at if rollback_dt else None,
        "recovery_completed_at": _format_timestamp(recovery_completed_at),
        "recovery_completed_at_iso": recovery_completed_at if completed_dt else None,
        "duration_seconds": duration_seconds,
        "duration": _format_duration(duration_seconds),
        "_detected_dt": detected_dt,
        "_rollback_dt": rollback_dt,
        "_completed_dt": completed_dt,
    }


def _incident_event(recovery: dict[str, Any]) -> dict[str, Any]:
    final_status = recovery["final_status"]
    recovered_release = recovery["recovered_release"]
    recovered_version = recovery["recovered_version"]

    if final_status == "recovered":
        label, status, icon = "Rollback initiated", "info", "rotate"
        timestamp = recovery["rollback_started_at"] or recovery["detected_at"]
        timestamp_iso = recovery["rollback_started_at_iso"] or recovery["detected_at_iso"]
        sort_time = recovery["_rollback_dt"] or recovery["_detected_dt"]
        detail = (
            f"Restored {recovered_release}"
            + (f" ({recovered_version})" if recovered_version else "")
            if recovered_release
            else "Restoring the stable release"
        )
    elif final_status == "rollback_failed":
        label, status, icon = "Rollback failed", "danger", "alert-triangle"
        timestamp = recovery["recovery_completed_at"] or recovery["rollback_started_at"]
        timestamp_iso = (
            recovery["recovery_completed_at_iso"] or recovery["rollback_started_at_iso"]
        )
        sort_time = recovery["_completed_dt"] or recovery["_rollback_dt"]
        detail = "Manual intervention required"
    elif final_status == "no_rollback_target":
        label, status, icon = "No rollback target", "warning", "alert-circle"
        timestamp = recovery["detected_at"]
        timestamp_iso = recovery["detected_at_iso"]
        sort_time = recovery["_detected_dt"]
        detail = "Stable release anchor was unavailable"
    else:
        label, status, icon = "Deployment failed", "danger", "x-circle"
        timestamp = recovery["detected_at"]
        timestamp_iso = recovery["detected_at_iso"]
        sort_time = recovery["_detected_dt"]
        detail = recovery["failure_reason"]

    return {
        "type": "incident",
        "event_label": label,
        "status": status,
        "icon": icon,
        "release_id": recovery["release_id"],
        "version": recovery["version"],
        "timestamp": timestamp or "Time unavailable",
        "timestamp_iso": timestamp_iso,
        "detail": detail,
        "_sort_time": sort_time or datetime.min.replace(tzinfo=timezone.utc),
    }


def build_dashboard_context(root: str | os.PathLike[str] | None, version: str) -> dict[str, Any]:
    root_path = Path(root) if root else Path("/opt/healdeploy")
    shared_dir = root_path / "shared"
    releases_dir = root_path / "releases"
    deployed = root_path.is_dir()

    stable_id = _safe_release_id(_read_text(root_path / "stable_release.txt"))
    active_id = _current_release(root_path)
    active_version = _release_version(releases_dir, active_id) or version
    stable_version = _release_version(releases_dir, stable_id)

    active_release = {
        "release_id": active_id,
        "version": active_version,
        "is_stable": (active_id == stable_id) if active_id and stable_id else None,
        "stable_release_id": stable_id,
        "stable_version": stable_version,
    }

    deployment_records = []
    timeline = []
    for path in _health_files(shared_dir):
        event = _health_event(path, releases_dir)
        if not event:
            continue
        timeline.append(event)
        if event["type"] == "deployment":
            deployment_records.append(event)

    incident = _read_json(shared_dir / "incident_report.json")
    recovery = _incident_context(incident, releases_dir) if incident else None
    if recovery:
        timeline.append(_incident_event(recovery))

    latest_deployment = None
    if deployment_records:
        latest_deployment = max(
            deployment_records, key=lambda item: item["_sort_time"]
        ).copy()
        latest_deployment.pop("_sort_time", None)

    timeline.sort(key=lambda item: item["_sort_time"], reverse=True)
    timeline_total = len(timeline)
    timeline = timeline[:TIMELINE_LIMIT]
    for item in timeline:
        item.pop("_sort_time", None)

    if recovery:
        for key in ("_detected_dt", "_rollback_dt", "_completed_dt"):
            recovery.pop(key, None)

    flask_version = _package_version("flask")
    system = platform.system() or "Unknown"
    environment = {
        "label": "Production" if deployed else "Local development",
        "platform": f"{system} · Azure VM" if deployed else f"{system} · Local workstation",
        "python": platform.python_version(),
        "flask": flask_version,
        "service": "healdeploy.service" if deployed else None,
    }

    health_payload = json.dumps({"status": "healthy", "version": version}, indent=2)

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "version": version,
        "status": "healthy",
        "status_class": "healthy",
        "active_release": active_release,
        "stable_release": {"release_id": stable_id, "version": stable_version},
        "latest_deployment": latest_deployment,
        "latest_recovery": recovery,
        "timeline": timeline,
        "timeline_total": timeline_total,
        "history_available": bool(timeline_total),
        "history_source": str(shared_dir) if deployed else None,
        "environment": environment,
        "health_json": health_payload,
        "health_path": "/health",
        "repo_url": REPO_URL,
        "jenkins_job": JENKINS_JOB,
    }
