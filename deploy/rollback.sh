#!/usr/bin/env bash
# =============================================================================
# HealDeploy rollback and recovery verification
# =============================================================================
# Restores the last stable release, restarts Gunicorn, and independently
# verifies the restored service with the health policy. Writes
# incident_report.json with the outcome.
#
# Usage:
#   rollback.sh <failed_release_id> <reason> <failed_app_version> \
#       [detected_at] [rollback_started_at]
#
# Exit codes:
#   0  previous stable release restored and verified healthy
#   1  rollback attempted but recovery verification failed
#   2  no rollback target exists
# =============================================================================

set -euo pipefail

FAILED_RELEASE_ID="${1:-unknown}"
REASON="${2:-health policy failure}"
FAILED_APP_VERSION="${3:-unknown}"
DETECTED_AT="${4:-}"
ROLLBACK_STARTED_AT="${5:-}"

BASE_DIR="/opt/healdeploy"
DEPLOY_DIR="$BASE_DIR/deploy"
RELEASES_DIR="$BASE_DIR/releases"
CURRENT_LINK="$BASE_DIR/current"
STABLE_FILE="$BASE_DIR/stable_release.txt"
SHARED_DIR="$BASE_DIR/shared"
INCIDENT_FILE="$SHARED_DIR/incident_report.json"
POLICY_FILE="$DEPLOY_DIR/health_policy.json"
HEALTH_SCRIPT="$DEPLOY_DIR/health_check.py"
SERVICE_NAME="healdeploy.service"

timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
    printf '[rollback] %s\n' "$*"
}

write_incident() {
    local final_status="$1"
    local recovered_release="$2"
    local recovery_verified="$3"
    local detected_at="$4"
    local rollback_started_at="$5"
    local recovery_completed_at="$6"

    python3 - "$INCIDENT_FILE" "$FAILED_RELEASE_ID" "$FAILED_APP_VERSION" \
        "$final_status" "$recovered_release" "$recovery_verified" "$REASON" \
        "$detected_at" "$rollback_started_at" "$recovery_completed_at" <<'PY'
import json
import sys

(
    path,
    release_id,
    app_version,
    final_status,
    recovered_release,
    recovery_verified,
    reason,
    detected_at,
    rollback_started_at,
    recovery_completed_at,
) = sys.argv[1:11]

data = {
    "release_id": release_id,
    "app_version": app_version,
    "failure_reason": reason,
    "detected_at": detected_at or None,
    "rollback_started_at": rollback_started_at or None,
    "recovery_completed_at": recovery_completed_at or None,
    "recovered_release": recovered_release or None,
    "recovery_verified": recovery_verified == "true",
    "final_status": final_status,
}

with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
    handle.write("\n")
PY

    chown healdeploy:healdeploy "$INCIDENT_FILE" 2>/dev/null || true
}

mkdir -p "$SHARED_DIR"

if [ -z "$DETECTED_AT" ]; then
    DETECTED_AT="$(timestamp)"
fi
if [ -z "$ROLLBACK_STARTED_AT" ]; then
    ROLLBACK_STARTED_AT="$(timestamp)"
fi

STABLE_RELEASE=""
if [ -s "$STABLE_FILE" ]; then
    STABLE_RELEASE="$(tr -d '[:space:]' < "$STABLE_FILE")"
fi

if [ -z "$STABLE_RELEASE" ] || [ ! -d "$RELEASES_DIR/$STABLE_RELEASE" ]; then
    log "no rollback target: stable_release.txt is empty or the release is missing"
    write_incident "no_rollback_target" "" "false" "$DETECTED_AT" "$ROLLBACK_STARTED_AT" "$(timestamp)"
    exit 2
fi

STABLE_DIR="$RELEASES_DIR/$STABLE_RELEASE"

if [ ! -x "$STABLE_DIR/.venv/bin/python" ]; then
    log "rollback target $STABLE_RELEASE has no usable virtual environment"
    write_incident "rollback_failed" "$STABLE_RELEASE" "false" "$DETECTED_AT" "$ROLLBACK_STARTED_AT" "$(timestamp)"
    exit 1
fi

EXPECTED_VERSION=""
if [ -f "$STABLE_DIR/.env" ]; then
    EXPECTED_VERSION="$(grep -E '^HEALDEPLOY_VERSION=' "$STABLE_DIR/.env" | head -n 1 | cut -d= -f2- || true)"
fi

log "restoring stable release $STABLE_RELEASE"
ln -sfn "$STABLE_DIR" "$CURRENT_LINK"
chown -h healdeploy:healdeploy "$CURRENT_LINK" 2>/dev/null || true
systemctl restart "$SERVICE_NAME"

for _ in $(seq 1 20); do
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        break
    fi
    sleep 1
done

HEALTH_JSON="$SHARED_DIR/health-rollback-$FAILED_RELEASE_ID.json"
set +e
sudo -u healdeploy "$STABLE_DIR/.venv/bin/python" "$HEALTH_SCRIPT" \
    --url "http://127.0.0.1:8000" \
    --policy "$POLICY_FILE" \
    --expected-version "$EXPECTED_VERSION" \
    --json-out "$HEALTH_JSON"
HEALTH_RC=$?
set -e

RECOVERY_COMPLETED_AT="$(timestamp)"

if [ "$HEALTH_RC" -eq 0 ]; then
    log "recovery verified: $STABLE_RELEASE is healthy"
    write_incident "recovered" "$STABLE_RELEASE" "true" "$DETECTED_AT" "$ROLLBACK_STARTED_AT" "$RECOVERY_COMPLETED_AT"
    exit 0
fi

log "recovery verification FAILED for $STABLE_RELEASE; manual intervention is required"
write_incident "rollback_failed" "$STABLE_RELEASE" "false" "$DETECTED_AT" "$ROLLBACK_STARTED_AT" "$RECOVERY_COMPLETED_AT"
exit 1
