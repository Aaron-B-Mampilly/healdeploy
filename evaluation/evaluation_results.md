# HealDeploy Phase 6 Evaluation Results

Generated: 2026-10-28T22:04:55Z

## Runs

| Fault | Build | Result | Detected (s) | Recovered (s) | Total (s) | Stable release | Recovery verified |
|---|---:|---|---:|---:|---:|---|---|
| fault-startup | 2 | FAILURE | 46.5 | 46.5 | 93.0 | jenkins-6-5ff39f4 | True |
| fault-slow | 2 | FAILURE | 56.1 | 46.5 | 102.6 | jenkins-6-5ff39f4 | True |
| fault-500 | 4 | FAILURE | 46.5 | 46.5 | 93.0 | jenkins-6-5ff39f4 | True |
| fault-500 | 5 | FAILURE | 46.5 | 46.5 | 93.0 | jenkins-6-5ff39f4 | True |
| fault-500 | 6 | FAILURE | 46.5 | 38.6 | 85.1 | jenkins-6-5ff39f4 | True |
| fault-startup | 3 | FAILURE | 46.5 | 38.6 | 85.1 | jenkins-6-5ff39f4 | True |
| fault-startup | 4 | FAILURE | 46.5 | 38.6 | 85.1 | jenkins-6-5ff39f4 | True |
| fault-slow | 3 | FAILURE | 56.1 | 46.5 | 102.6 | jenkins-6-5ff39f4 | True |
| fault-slow | 4 | FAILURE | 56.1 | 46.5 | 102.6 | jenkins-6-5ff39f4 | True |

## Summary

| Fault | Runs | Failed builds | Recovered | Detection median (s) | Recovery median (s) | Total median (s) |
|---|---:|---:|---:|---:|---:|---:|
| fault-startup | 3 | 3 | 3 | 46.5 | 38.6 | 85.1 |
| fault-slow | 3 | 3 | 3 | 56.1 | 46.5 | 102.6 |
| fault-500 | 3 | 3 | 3 | 46.5 | 46.5 | 93.0 |
