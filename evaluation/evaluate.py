#!/usr/bin/env python3
"""Run the HealDeploy Phase 6 fault-injection evaluation matrix."""

import argparse
import json
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


FAULTS = [
    {
        "name": "fault-500",
        "job": "healdeploy-fault-500",
        "mode": "500",
        "description": "Health endpoint returns HTTP 500.",
    },
    {
        "name": "fault-startup",
        "job": "healdeploy-fault-startup",
        "mode": "startup",
        "description": "Application raises at import time and fails to start.",
    },
    {
        "name": "fault-slow",
        "job": "healdeploy-fault-slow",
        "mode": "slow",
        "description": "Health endpoint sleeps for 1s, exceeding the 500ms p95 budget.",
    },
]

CONSOLE_LINE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\]\s+(.*)$"
)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_timestamp(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_iso_timestamp(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def elapsed_seconds(start, end):
    if not start or not end:
        return None
    return round((end - start).total_seconds(), 1)


def stats(values):
    clean = [value for value in values if value is not None]
    if not clean:
        return None
    return {
        "count": len(clean),
        "min": round(min(clean), 1),
        "median": round(statistics.median(clean), 1),
        "mean": round(statistics.mean(clean), 1),
        "max": round(max(clean), 1),
    }


def make_session(base_url, user, password):
    session = requests.Session()
    session.auth = (user, password)
    session.headers.update({"Accept": "application/json"})
    return session


def get_crumb(session, base_url):
    response = session.get("%s/crumbIssuer/api/json" % base_url, timeout=30)
    response.raise_for_status()
    return response.json()["crumb"]


def last_build_number(session, base_url, job):
    response = session.get(
        "%s/job/%s/lastBuild/api/json" % (base_url, job),
        params={"tree": "number"},
        timeout=30,
    )
    if response.status_code == 404:
        return 0
    response.raise_for_status()
    data = response.json()
    return data.get("number", 0) if data else 0


def trigger_build(session, base_url, job, mode):
    previous = last_build_number(session, base_url, job)
    crumb = get_crumb(session, base_url)
    response = session.post(
        "%s/job/%s/buildWithParameters" % (base_url, job),
        params={"FAULT_MODE": mode},
        headers={"Jenkins-Crumb": crumb},
        timeout=30,
    )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            "could not trigger %s: HTTP %s %s"
            % (job, response.status_code, response.text[:300])
        )

    deadline = time.time() + 180
    while time.time() < deadline:
        current = last_build_number(session, base_url, job)
        if current > previous:
            return current
        time.sleep(3)
    raise TimeoutError("build for %s did not start within 180s" % job)


def wait_for_build(session, base_url, job, number, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = session.get(
            "%s/job/%s/%s/api/json" % (base_url, job, number),
            params={
                "tree": "number,building,result,duration,timestamp,"
                "artifacts[fileName,relativePath]"
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("building"):
            return data
        time.sleep(10)
    raise TimeoutError("build %s #%s did not finish within %ss" % (job, number, timeout_seconds))


def get_console(session, base_url, job, number):
    response = session.get(
        "%s/job/%s/%s/consoleText" % (base_url, job, number),
        timeout=60,
    )
    response.raise_for_status()
    return response.text


def parse_console_events(console):
    events = {}
    for line in console.splitlines():
        match = CONSOLE_LINE.match(line)
        if not match:
            continue
        timestamp, message = match.groups()
        if "activating release" in message and "activation" not in events:
            events["activation"] = timestamp
        elif "health policy failed" in message and "detection" not in events:
            events["detection"] = timestamp
        elif "recovery verified" in message and "recovery" not in events:
            events["recovery"] = timestamp
        elif message.startswith("Finished:") and "finished" not in events:
            events["finished"] = timestamp
    return events


def get_artifact_json(session, base_url, job, number, path):
    response = session.get(
        "%s/job/%s/%s/artifact/%s" % (base_url, job, number, path),
        timeout=60,
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


def get_public_health(url):
    if not url:
        return None
    try:
        response = requests.get(url, timeout=20)
        try:
            body = response.json()
        except ValueError:
            body = None
        return {
            "http_status": response.status_code,
            "body": body,
        }
    except requests.RequestException as exc:
        return {"error": str(exc)}


def run_fault(session, base_url, fault, health_url, timeout_seconds):
    number = trigger_build(session, base_url, fault["job"], fault["mode"])
    build = wait_for_build(session, base_url, fault["job"], number, timeout_seconds)
    console = get_console(session, base_url, fault["job"], number)
    events = parse_console_events(console)

    incident = get_artifact_json(
        session, base_url, fault["job"], number, "artifacts/incident_report.json"
    )
    release_id = incident.get("release_id") if incident else None
    failed_health = None
    rollback_health = None
    if release_id:
        failed_health = get_artifact_json(
            session,
            base_url,
            fault["job"],
            number,
            "artifacts/health-%s.json" % release_id,
        )
        rollback_health = get_artifact_json(
            session,
            base_url,
            fault["job"],
            number,
            "artifacts/health-rollback-%s.json" % release_id,
        )

    activation = parse_timestamp(events.get("activation"))
    detection = parse_timestamp(events.get("detection"))
    recovery = parse_timestamp(events.get("recovery"))
    finished = parse_timestamp(events.get("finished"))

    failed_started = parse_iso_timestamp(
        failed_health.get("started_at") if failed_health else None
    )
    failed_finished = parse_iso_timestamp(
        failed_health.get("finished_at") if failed_health else None
    )

    evaluation = failed_health.get("evaluation", {}) if failed_health else {}

    return {
        "fault": fault["name"],
        "mode": fault["mode"],
        "description": fault["description"],
        "job": fault["job"],
        "build_number": number,
        "build_result": build.get("result"),
        "build_url": "%s/job/%s/%s/" % (base_url, fault["job"], number),
        "build_duration_seconds": round((build.get("duration") or 0) / 1000.0, 1),
        "events": {
            "activation": events.get("activation"),
            "detection": events.get("detection"),
            "recovery": events.get("recovery"),
            "finished": events.get("finished"),
        },
        "metrics": {
            "activation_to_detection_seconds": elapsed_seconds(activation, detection),
            "detection_to_recovery_seconds": elapsed_seconds(detection, recovery),
            "activation_to_recovery_seconds": elapsed_seconds(activation, recovery),
            "health_check_seconds": elapsed_seconds(failed_started, failed_finished),
            "build_finish_seconds": elapsed_seconds(activation, finished),
        },
        "incident": incident,
        "failed_health": {
            "passed": evaluation.get("passed"),
            "successes": evaluation.get("successes"),
            "required_successes": evaluation.get("required_successes"),
            "p95_latency_ms": evaluation.get("p95_latency_ms"),
            "max_p95_latency_ms": evaluation.get("max_p95_latency_ms"),
            "failures": evaluation.get("failures"),
        },
        "rollback_health": {
            "passed": (rollback_health or {}).get("evaluation", {}).get("passed"),
            "p95_latency_ms": (rollback_health or {})
            .get("evaluation", {})
            .get("p95_latency_ms"),
        },
        "post_recovery_health": get_public_health(health_url),
    }


def summarize(runs):
    grouped = {}
    for run in runs:
        grouped.setdefault(run["fault"], []).append(run)

    summary = {}
    for fault, items in grouped.items():
        summary[fault] = {
            "runs": len(items),
            "failed_builds": sum(1 for item in items if item["build_result"] == "FAILURE"),
            "recovered_runs": sum(
                1
                for item in items
                if item["incident"] and item["incident"].get("recovery_verified")
            ),
            "activation_to_detection_seconds": stats(
                [item["metrics"]["activation_to_detection_seconds"] for item in items]
            ),
            "detection_to_recovery_seconds": stats(
                [item["metrics"]["detection_to_recovery_seconds"] for item in items]
            ),
            "activation_to_recovery_seconds": stats(
                [item["metrics"]["activation_to_recovery_seconds"] for item in items]
            ),
            "health_check_seconds": stats(
                [item["metrics"]["health_check_seconds"] for item in items]
            ),
            "build_duration_seconds": stats(
                [item["build_duration_seconds"] for item in items]
            ),
        }
    return summary


def write_markdown(path, payload):
    lines = [
        "# HealDeploy Phase 6 Evaluation Results",
        "",
        "Generated: %s" % payload["generated_at"],
        "",
        "## Runs",
        "",
        "| Fault | Build | Result | Detected (s) | Recovered (s) | Total (s) | Stable release | Recovery verified |",
        "|---|---:|---|---:|---:|---:|---|---|",
    ]
    for run in payload["runs"]:
        incident = run["incident"] or {}
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s | %s |"
            % (
                run["fault"],
                run["build_number"],
                run["build_result"],
                run["metrics"]["activation_to_detection_seconds"],
                run["metrics"]["detection_to_recovery_seconds"],
                run["metrics"]["activation_to_recovery_seconds"],
                incident.get("recovered_release"),
                incident.get("recovery_verified"),
            )
        )

    lines.extend(
        [
            "",
            "## Summary",
            "",
            "| Fault | Runs | Failed builds | Recovered | Detection median (s) | Recovery median (s) | Total median (s) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for fault, summary in payload["summary"].items():
        detection = summary["activation_to_detection_seconds"] or {}
        recovery = summary["detection_to_recovery_seconds"] or {}
        total = summary["activation_to_recovery_seconds"] or {}
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s |"
            % (
                fault,
                summary["runs"],
                summary["failed_builds"],
                summary["recovered_runs"],
                detection.get("median"),
                recovery.get("median"),
                total.get("median"),
            )
        )

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jenkins-url", default="http://localhost:8080")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password-file", default="jenkins/.admin_password")
    parser.add_argument("--health-url", default="http://20.205.103.245/health")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--faults",
        nargs="+",
        choices=[fault["name"] for fault in FAULTS],
        default=[fault["name"] for fault in FAULTS],
    )
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--output", default="evaluation/evaluation_results.json")
    parser.add_argument("--markdown", default="evaluation/evaluation_results.md")
    args = parser.parse_args()

    password = Path(args.password_file).read_text(encoding="utf-8").strip()
    base_url = args.jenkins_url.rstrip("/")
    session = make_session(base_url, args.user, password)

    selected_faults = [fault for fault in FAULTS if fault["name"] in args.faults]
    runs = []
    if args.append and Path(args.output).exists():
        existing = json.loads(Path(args.output).read_text(encoding="utf-8"))
        runs = existing.get("runs", [])

    for fault in selected_faults:
        for index in range(1, args.runs + 1):
            print(
                "Running %s (%d/%d) on %s"
                % (fault["name"], index, args.runs, fault["job"]),
                flush=True,
            )
            try:
                result = run_fault(
                    session, base_url, fault, args.health_url, args.timeout
                )
            except Exception as exc:
                result = {
                    "fault": fault["name"],
                    "mode": fault["mode"],
                    "description": fault["description"],
                    "job": fault["job"],
                    "error": str(exc),
                    "build_result": "ERROR",
                    "metrics": {},
                    "incident": None,
                }
            runs.append(result)
            if result.get("build_result") == "FAILURE":
                print(
                    "  build #%s FAILURE, recovered=%s, total=%ss"
                    % (
                        result.get("build_number"),
                        (result.get("incident") or {}).get("recovery_verified"),
                        result.get("metrics", {}).get("activation_to_recovery_seconds"),
                    ),
                    flush=True,
                )
            else:
                print("  %s" % result.get("build_result"), flush=True)

    payload = {
        "generated_at": utc_now(),
        "jenkins_url": base_url,
        "health_url": args.health_url,
        "runs_per_fault": args.runs,
        "total_runs": len(runs),
        "faults": selected_faults,
        "runs": runs,
        "summary": summarize([run for run in runs if "metrics" in run and run["metrics"]]),
    }

    Path(args.output).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    write_markdown(args.markdown, payload)
    print("Wrote %s and %s" % (args.output, args.markdown), flush=True)

    failed = [
        run
        for run in runs
        if run.get("build_result") != "FAILURE"
        or not (run.get("incident") or {}).get("recovery_verified")
    ]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
