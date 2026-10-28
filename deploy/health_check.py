#!/usr/bin/env python3
"""
HealDeploy health policy evaluator.

Probes an application's /health endpoint according to a JSON policy and exits
with status 0 only when the release satisfies every configured requirement.

Usage:
    python health_check.py --url http://127.0.0.1:8000 \
        --policy health_policy.json --expected-version v1.0.1

Exit codes:
    0  policy passed
    1  policy failed
    2  invalid arguments / unreadable policy
"""

import argparse
import datetime as dt
import json
import os
import sys
import time

import requests


def utc_now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_policy(path):
    with open(path, "r", encoding="utf-8") as handle:
        policy = json.load(handle)

    required = [
        "startup_grace_seconds",
        "total_probes",
        "interval_seconds",
        "required_successes",
        "max_p95_latency_ms",
        "timeout_seconds",
        "health_path",
        "expected_status",
    ]
    missing = [key for key in required if key not in policy]
    if missing:
        raise ValueError("policy is missing keys: %s" % ", ".join(missing))
    return policy


def percentile(values, fraction):
    """Nearest-rank percentile over a list of numbers."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round(fraction * len(ordered))) - 1))
    return ordered[index]


def probe(url, timeout_seconds):
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=timeout_seconds)
        latency_ms = (time.perf_counter() - started) * 1000.0
        body = None
        try:
            body = response.json()
        except ValueError:
            body = None
        return {
            "http_status": response.status_code,
            "latency_ms": round(latency_ms, 2),
            "body": body,
            "error": None,
        }
    except requests.RequestException as exc:
        latency_ms = (time.perf_counter() - started) * 1000.0
        return {
            "http_status": None,
            "latency_ms": round(latency_ms, 2),
            "body": None,
            "error": str(exc),
        }


def evaluate(probes, policy, expected_version):
    successes = 0
    success_latencies = []
    observed_versions = set()
    failure_reasons = []

    for index, result in enumerate(probes, start=1):
        body = result.get("body") or {}
        version = body.get("version")
        if version:
            observed_versions.add(str(version))

        reasons = []
        if result.get("error"):
            reasons.append("request error: %s" % result["error"])
        if result.get("http_status") != 200:
            reasons.append("http status %s" % result.get("http_status"))
        if body.get("status") != policy["expected_status"]:
            reasons.append("status %r" % body.get("status"))
        if expected_version and version != expected_version:
            reasons.append("version %r != expected %r" % (version, expected_version))

        if reasons:
            failure_reasons.append({"probe": index, "reasons": reasons})
        else:
            successes += 1
            success_latencies.append(result["latency_ms"])

    p95 = percentile(success_latencies, 0.95)
    success_ok = successes >= policy["required_successes"]
    latency_ok = p95 is not None and p95 < policy["max_p95_latency_ms"]

    return {
        "passed": bool(success_ok and latency_ok),
        "successes": successes,
        "required_successes": policy["required_successes"],
        "success_criterion_met": success_ok,
        "p95_latency_ms": p95,
        "max_p95_latency_ms": policy["max_p95_latency_ms"],
        "latency_criterion_met": latency_ok,
        "observed_versions": sorted(observed_versions),
        "failures": failure_reasons,
    }


def main():
    default_policy = os.path.join(os.path.dirname(os.path.abspath(__file__)), "health_policy.json")

    parser = argparse.ArgumentParser(description="Evaluate the HealDeploy health policy")
    parser.add_argument("--url", required=True, help="Base URL or full health URL")
    parser.add_argument("--policy", default=default_policy, help="Path to health_policy.json")
    parser.add_argument("--expected-version", default=None, help="Version the release must report")
    parser.add_argument("--json-out", default=None, help="Write the result JSON to this path")
    parser.add_argument(
        "--grace-seconds",
        type=float,
        default=None,
        help="Override the policy startup grace period (seconds)",
    )
    args = parser.parse_args()

    try:
        policy = load_policy(args.policy)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("health_check: cannot load policy: %s" % exc, file=sys.stderr)
        return 2

    base = args.url.rstrip("/")
    health_path = policy["health_path"]
    health_url = base if base.endswith(health_path) else base + health_path

    grace = policy["startup_grace_seconds"] if args.grace_seconds is None else args.grace_seconds
    if grace > 0:
        print("health_check: waiting %.1fs startup grace period" % grace)
        time.sleep(grace)

    probes = []
    for index in range(1, policy["total_probes"] + 1):
        result = probe(health_url, policy["timeout_seconds"])
        result["probe"] = index
        result["at"] = utc_now()
        probes.append(result)
        print(
            "health_check: probe %d/%d http=%s latency=%.1fms"
            % (
                index,
                policy["total_probes"],
                result["http_status"],
                result["latency_ms"],
            )
        )
        if index < policy["total_probes"]:
            time.sleep(policy["interval_seconds"])

    evaluation = evaluate(probes, policy, args.expected_version)
    summary = {
        "started_at": probes[0]["at"] if probes else utc_now(),
        "finished_at": utc_now(),
        "url": health_url,
        "expected_version": args.expected_version,
        "policy": policy,
        "evaluation": evaluation,
        "probes": probes,
    }

    print(json.dumps({"evaluation": evaluation, "url": health_url}, indent=2))

    if args.json_out:
        try:
            with open(args.json_out, "w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2)
        except OSError as exc:
            print("health_check: cannot write result: %s" % exc, file=sys.stderr)

    return 0 if evaluation["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
