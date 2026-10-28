#!/usr/bin/env bash
# =============================================================================
# HealDeploy release deployment
# =============================================================================
# Creates a versioned release, installs its own virtual environment, switches
# the active symlink, restarts Gunicorn, and applies the health policy.
#
# If the health policy fails, the previous stable release is restored and
# independently health-checked. The build still fails even when recovery
# succeeds, so a bad release is never silently accepted.
#
# Usage:
#   deploy.sh <release_id> <app_version> <archive_path> [fault_mode]
#
# fault_mode is optional and is written to the release .env as
# HEALDEPLOY_FAULT for controlled fault-injection evaluation.
#
# This script is intended to run as root (invoked through sudo) on the VM.
# =============================================================================

set -euo pipefail

RELEASE_ID="${1:?usage: deploy.sh <release_id> <app_version> <archive_path> [fault_mode]}"
APP_VERSION="${2:?usage: deploy.sh <release_id> <app_version> <archive_path> [fault_mode]}"
ARCHIVE="${3:?usage: deploy.sh <release_id> <app_version> <archive_path> [fault_mode]}"
FAULT_MODE="${4:-}"

BASE_DIR="/opt/healdeploy"
DEPLOY_DIR="$BASE_DIR/deploy"
RELEASES_DIR="$BASE_DIR/releases"
CURRENT_LINK="$BASE_DIR/current"
STABLE_FILE="$BASE_DIR/stable_release.txt"
SHARED_DIR="$BASE_DIR/shared"
INCIDENT_FILE="$SHARED_DIR/incident_report.json"
POLICY_FILE="$DEPLOY_DIR/health_policy.json"
HEALTH_SCRIPT="$DEPLOY_DIR/health_check.py"
ROLLBACK_SCRIPT="$DEPLOY_DIR/rollback.sh"
SERVICE_NAME="healdeploy.service"
RELEASE_DIR="$RELEASES_DIR/$RELEASE_ID"

INCIDENT_WRITTEN=0

timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
    printf '[deploy] %s\n' "$*"
}

write_incident() {
    local final_status="$1"
    local recovered_release="$2"
    local recovery_verified="$3"
    local reason="$4"
    local detected_at="$5"
    local rollback_started_at="$6"
    local recovery_completed_at="$7"

    python3 - "$INCIDENT_FILE" "$RELEASE_ID" "$APP_VERSION" "$final_status" \
        "$recovered_release" "$recovery_verified" "$reason" "$detected_at" \
        "$rollback_started_at" "$recovery_completed_at" <<'PY'
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
    INCIDENT_WRITTEN=1
}

on_exit() {
    local rc=$?
    if [ "$rc" -ne 0 ] && [ "$INCIDENT_WRITTEN" -eq 0 ]; then
        write_incident \
            "deployment_failed" \
            "" \
            "false" \
            "deployment failed before activation (exit $rc)" \
            "$(timestamp)" \
            "" \
            ""
    fi
}

prune_releases() {
    local keep=5
    local current_target
    local stable
    local dir
    local name
    local -a candidates=()

    current_target="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
    stable="$(tr -d '[:space:]' < "$STABLE_FILE" 2>/dev/null || true)"

    mapfile -t candidates < <(ls -1dt "$RELEASES_DIR"/*/ 2>/dev/null | tail -n +$((keep + 1)))

    for dir in "${candidates[@]:-}"; do
        [ -n "$dir" ] || continue
        name="$(basename "$dir")"
        if [ "$name" = "$stable" ]; then
            continue
        fi
        if [ "${dir%/}" = "$current_target" ]; then
            continue
        fi
        log "pruning old release $name"
        rm -rf "$dir"
    done
}

trap on_exit EXIT

if ! [[ "$RELEASE_ID" =~ ^[A-Za-z0-9._-]+$ ]]; then
    log "invalid release id: $RELEASE_ID"
    exit 1
fi

if [ -n "$FAULT_MODE" ] && ! [[ "$FAULT_MODE" =~ ^[A-Za-z0-9._-]+$ ]]; then
    log "invalid fault mode: $FAULT_MODE"
    exit 1
fi

if [ ! -f "$ARCHIVE" ]; then
    log "archive not found: $ARCHIVE"
    exit 1
fi

if [ ! -f "$HEALTH_SCRIPT" ] || [ ! -f "$POLICY_FILE" ] || [ ! -x "$ROLLBACK_SCRIPT" ]; then
    log "deploy helpers are missing under $DEPLOY_DIR"
    exit 1
fi

mkdir -p "$RELEASES_DIR" "$SHARED_DIR"

PREVIOUS_STABLE=""
if [ -s "$STABLE_FILE" ]; then
    PREVIOUS_STABLE="$(tr -d '[:space:]' < "$STABLE_FILE")"
fi

log "creating release $RELEASE_ID ($APP_VERSION)"
if [ -e "$RELEASE_DIR" ]; then
    rm -rf "$RELEASE_DIR"
fi
mkdir -p "$RELEASE_DIR"
tar -xzf "$ARCHIVE" -C "$RELEASE_DIR"
chown -R healdeploy:healdeploy "$RELEASE_DIR"

log "creating isolated virtual environment"
sudo -u healdeploy python3 -m venv "$RELEASE_DIR/.venv"
sudo -u healdeploy "$RELEASE_DIR/.venv/bin/python" -m pip install --upgrade pip >/dev/null
sudo -u healdeploy "$RELEASE_DIR/.venv/bin/pip" install --no-cache-dir -r "$RELEASE_DIR/requirements.txt"

printf 'HEALDEPLOY_VERSION=%s\nPYTHONUNBUFFERED=1\n' "$APP_VERSION" > "$RELEASE_DIR/.env"
if [ -n "$FAULT_MODE" ]; then
    printf 'HEALDEPLOY_FAULT=%s\n' "$FAULT_MODE" >> "$RELEASE_DIR/.env"
fi
chown healdeploy:healdeploy "$RELEASE_DIR/.env"

log "activating release $RELEASE_ID"
ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"
chown -h healdeploy:healdeploy "$CURRENT_LINK" 2>/dev/null || true
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1 || true
systemctl restart "$SERVICE_NAME"

for _ in $(seq 1 20); do
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        break
    fi
    sleep 1
done

HEALTH_JSON="$SHARED_DIR/health-$RELEASE_ID.json"
set +e
sudo -u healdeploy "$RELEASE_DIR/.venv/bin/python" "$HEALTH_SCRIPT" \
    --url "http://127.0.0.1:8000" \
    --policy "$POLICY_FILE" \
    --expected-version "$APP_VERSION" \
    --json-out "$HEALTH_JSON"
HEALTH_RC=$?
set -e

if [ "$HEALTH_RC" -eq 0 ]; then
    printf '%s\n' "$RELEASE_ID" > "$STABLE_FILE"
    chown healdeploy:healdeploy "$STABLE_FILE"
    log "release $RELEASE_ID passed the health policy and was promoted to stable"
    prune_releases
    exit 0
fi

DETECTED_AT="$(timestamp)"
REASON="health policy failed for release $RELEASE_ID"

if [ -n "$PREVIOUS_STABLE" ] && [ -d "$RELEASES_DIR/$PREVIOUS_STABLE" ]; then
    ROLLBACK_STARTED="$(timestamp)"
    log "$REASON; rolling back to $PREVIOUS_STABLE"
    set +e
    "$ROLLBACK_SCRIPT" "$RELEASE_ID" "$REASON" "$APP_VERSION" "$DETECTED_AT" "$ROLLBACK_STARTED"
    ROLLBACK_RC=$?
    set -e
    INCIDENT_WRITTEN=1
    if [ "$ROLLBACK_RC" -eq 0 ]; then
        log "rollback recovered $PREVIOUS_STABLE; the release build remains FAILED"
        exit 1
    fi
    log "rollback failed to recover the service; manual intervention is required"
    exit 2
fi

log "$REASON; no previous stable release exists, so there is no rollback target"
set +e
"$ROLLBACK_SCRIPT" "$RELEASE_ID" "$REASON" "$APP_VERSION" "$DETECTED_AT" ""
set -e
INCIDENT_WRITTEN=1
exit 2
