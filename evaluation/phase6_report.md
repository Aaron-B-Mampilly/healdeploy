# HealDeploy Phase 6 Evaluation Report

## Objective

Evaluate whether the HealDeploy CI/CD pipeline can detect synthetic bad releases,
roll them back automatically, and verify recovery without manual intervention.

## Environment

| Component | Value |
|---|---|
| Azure VM | `vm-healdeploy-prod` (`Standard_D2s_v4`, `eastasia`) |
| Application URL | `http://20.205.103.245/` |
| Health URL | `http://20.205.103.245/health` |
| Jenkins | Docker container `healdeploy-jenkins`, `http://localhost:8080` |
| Stable release during evaluation | `jenkins-6-5ff39f4` (`v1.0.6`) |
| Deployment model | Versioned releases under `/opt/healdeploy/releases/`, `current` symlink, `stable_release.txt` |
| Health policy | 15s startup grace, 10 probes, 3s interval, 9 required successes, p95 < 500ms, 5s timeout |

## Fault Injection Design

Each fault branch adds a runtime-only condition controlled by the `HEALDEPLOY_FAULT`
environment variable. The Jenkins `FAULT_MODE` parameter is passed to `deploy.sh`, which
writes it into the release `.env` file. The test suite runs without this variable, so the
release passes tests and reaches the deployment and health-validation stage.

| Fault | Branch / Job | Runtime behavior | Expected health result |
|---|---|---|---|
| `fault-500` | `fault-500` / `healdeploy-fault-500` | `/health` returns HTTP 500 with `status: unhealthy` | 0/10 successes |
| `fault-startup` | `fault-startup` / `healdeploy-fault-startup` | Application raises `RuntimeError` at import; Gunicorn cannot start | Connection refused on every probe |
| `fault-slow` | `fault-slow` / `healdeploy-fault-slow` | `/health` sleeps 1s before responding | 10/10 successes but p95 latency above 500ms |

## Method

1. Trigger the fault job with `FAULT_MODE=<fault>`.
2. Jenkins runs tests, packages the release, copies it to the VM, and runs `deploy.sh`.
3. `deploy.sh` activates the release and runs the health policy.
4. A failed policy triggers `rollback.sh`, which restores `stable_release.txt`, restarts
   `healdeploy.service`, and independently re-runs the health policy.
5. The Jenkins build remains `FAILURE` even when recovery succeeds.
6. `evaluation/evaluate.py` records build results, console timestamps, health JSON,
   incident reports, rollback health, and public post-recovery health.

Measurement points:

- **Detection time**: release activation to health-policy failure.
- **Recovery time**: health-policy failure to verified rollback health.
- **Total self-healing time**: release activation to verified rollback health.
- **Baseline**: manual activation of a known bad release, a fixed 120s observation
  window, and manual restoration.

## Results

### Individual runs

| Fault | Build | Build result | Detection (s) | Recovery (s) | Total (s) | Recovered release | Verified |
|---|---:|---|---:|---:|---:|---|---|
| fault-startup | 2 | FAILURE | 46.5 | 46.5 | 93.0 | `jenkins-6-5ff39f4` | yes |
| fault-startup | 3 | FAILURE | 46.5 | 38.6 | 85.1 | `jenkins-6-5ff39f4` | yes |
| fault-startup | 4 | FAILURE | 46.5 | 38.6 | 85.1 | `jenkins-6-5ff39f4` | yes |
| fault-500 | 4 | FAILURE | 46.5 | 46.5 | 93.0 | `jenkins-6-5ff39f4` | yes |
| fault-500 | 5 | FAILURE | 46.5 | 46.5 | 93.0 | `jenkins-6-5ff39f4` | yes |
| fault-500 | 6 | FAILURE | 46.5 | 38.6 | 85.1 | `jenkins-6-5ff39f4` | yes |
| fault-slow | 2 | FAILURE | 56.1 | 46.5 | 102.6 | `jenkins-6-5ff39f4` | yes |
| fault-slow | 3 | FAILURE | 56.1 | 46.5 | 102.6 | `jenkins-6-5ff39f4` | yes |
| fault-slow | 4 | FAILURE | 56.1 | 46.5 | 102.6 | `jenkins-6-5ff39f4` | yes |

### Summary

| Fault | Runs | Failed builds | Recovered | Detection median (s) | Recovery median (s) | Total median (s) | Total range (s) |
|---|---:|---:|---:|---:|---:|---:|---|
| fault-startup | 3 | 3 | 3 | 46.5 | 38.6 | 85.1 | 85.1-93.0 |
| fault-500 | 3 | 3 | 3 | 46.5 | 46.5 | 93.0 | 85.1-93.0 |
| fault-slow | 3 | 3 | 3 | 56.1 | 46.5 | 102.6 | 102.6-102.6 |

All 9 fault builds failed as designed, all 9 rollbacks recovered, and every rollback
verified the stable release `jenkins-6-5ff39f4` (`v1.0.6`). Public health returned
HTTP 200 with `{"status": "healthy", "version": "v1.0.6"}` after every run.

### Failure evidence

- **fault-500**: 0/10 successful probes; every probe returned HTTP 500 and
  `status: unhealthy`; failed p95 was `null`.
- **fault-startup**: 0/10 successful probes; every probe reported connection refused on
  `127.0.0.1:8000`; the service could not start.
- **fault-slow**: 10/10 successful probes, but p95 latency was `1010.0ms`, above the
  `500ms` budget; this confirms that latency-only failures are detected even when the
  endpoint returns HTTP 200 and a healthy status.
- **Rollback health**: p95 latency was approximately `8.2-8.3ms` after restoration.

### Baseline comparison

The manual baseline activated the known bad release `jenkins-3-7f98fd1` (`v1.0.3` with
`HEALDEPLOY_FAULT=500`), observed it for 120s, and then restored `jenkins-6-5ff39f4`
manually. The measured outage was **121s** (120s observation + 1s restore).

This is an optimistic baseline: the operator already knew the release was bad and did not
need time to notice or diagnose it. The automated pipeline detected faults in 46.5-56.1s
and completed verified recovery in 85.1-102.6s total. The main benefit is not only speed
but bounded, repeatable recovery with independent verification and an audit trail.

## Observations

1. **Fail-closed behavior works.** Every faulty release produced a `FAILURE` build, even
   though recovery succeeded. Bad releases were never silently accepted.
2. **Recovery is consistent.** The same stable release was restored in every run, and
   rollback health verification passed each time.
3. **Latency faults take longer to detect.** `fault-slow` required all 10 probes to
   compute p95, so detection took 56.1s versus 46.5s for HTTP/startup failures.
4. **Artifact hygiene works.** Each build archived only its own health, rollback-health,
   incident, tarball, and test artifacts after the workspace cleanup fix.
5. **The service remains available after rollback.** Public health returned HTTP 200 and
   the stable version after every run.
6. **Fault jobs do not poll SCM.** Polling was removed from the evaluation branches and
   jobs so only explicitly triggered fault builds run; the main job retains Poll SCM.

## Limitations

- Evaluation used a single VM in a single region; no multi-node or zone-failure testing.
- Health probes run against `127.0.0.1`; external black-box monitoring is not evaluated.
- Faults are synthetic and deterministic. Network partitions, disk exhaustion,
  dependency failures, and load-induced latency were not tested.
- The 15s grace period and 10-probe policy dominate detection time; different policies
  would change the results.
- The manual baseline uses a fixed 120s observation window and assumes immediate
  detection; real human response time is likely longer and more variable.
- Version strings are derived from per-job build numbers; release IDs remain unique
  because they include the job build number and Git SHA.
- Jenkins runs as a single Docker container on the operator workstation, not as a
  highly available production service.
- No load or concurrency testing was performed; only one deployment ran at a time.

## Reproducibility

```powershell
# Start Jenkins (see README section 5)
docker build -t healdeploy-jenkins:phase4 jenkins/
docker run -d --name healdeploy-jenkins --restart unless-stopped `
  -p 8080:8080 -p 50000:50000 `
  -v healdeploy-jenkins-home:/var/jenkins_home `
  -v "${env:USERPROFILE}\.ssh\healdeploy_rsa:/run/secrets/healdeploy_rsa:ro" `
  -e "JENKINS_ADMIN_PASSWORD=$(Get-Content jenkins\.admin_password -Raw)" `
  -e "JAVA_OPTS=-Djenkins.install.runSetupWizard=false" `
  healdeploy-jenkins:phase4

# Run the evaluation matrix
.\.venv\Scripts\python.exe evaluation\evaluate.py --runs 3
```

Fault jobs: `healdeploy-fault-500`, `healdeploy-fault-startup`, `healdeploy-fault-slow`.
Trigger each with `buildWithParameters?FAULT_MODE=500`, `startup`, or `slow`.

Raw data:

- `evaluation/evaluation_results.json`
- `evaluation/evaluation_results.md`
- `evaluation/baseline_result.json`

## Conclusion

The self-healing pipeline met the Phase 6 objective. Across nine synthetic fault runs,
every bad release was detected, rolled back, and independently verified, while the
Jenkins build correctly remained failed. Recovery was bounded at 85.1-102.6s total and
always restored the known-good stable release. The manual baseline was 121s under an
optimistic fixed observation window, so the primary advantage of the automated system is
consistent, auditable recovery without human intervention rather than raw speed alone.
