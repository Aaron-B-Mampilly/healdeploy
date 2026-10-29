# HealDeploy

> **A Self-Healing CI/CD Pipeline with Automatic Rollback and Recovery Verification**

[![Phase 3: Provisioned & Verified](https://img.shields.io/badge/Phase%203-Provisioned%20%26%20Verified-green.svg)]()
[![Python 3.10](https://img.shields.io/badge/Python-3.10-blue.svg)]()
[![Terraform 1.16.6](https://img.shields.io/badge/Terraform-1.16.6-purple.svg)]()
[![AzureRM ~> 4.0](https://img.shields.io/badge/AzureRM-v4.81.0-blue.svg)]()
[![Tests: pytest](https://img.shields.io/badge/Tests-25%20Passed-success.svg)]()

---

## 1. Project Overview

**HealDeploy** is a DevOps IA3 project designed to demonstrate a self-healing continuous integration and deployment pipeline.

The project automates deployment of a Python Flask web application to Microsoft Azure using Terraform, Jenkins, and GitHub. The central innovation is an **automated self-healing deployment cycle**:
1. A release candidate is deployed.
2. The deployment is subjected to automated synthetic health checks and performance threshold validation.
3. If the release violates the defined health policy, the pipeline automatically triggers a rollback to the previous known stable release.
4. Recovery verification is executed to confirm normal application service is restored.

---

## 2. Architecture & Roadmap

```
GitHub Repository
       â”‚ (Push / Tag)
       â–¼
Jenkins Pipeline (Docker)
       â”‚ (Trigger Terraform & Remote Exec)
       â–¼
Azure Linux Virtual Machine (Nginx + Gunicorn + Flask in virtualenv)
       â”‚
       â–¼
Deployment Health Check & Policy Evaluation
       â”œâ”€â”€ PASS â”€â”€â–º Release Promoted to Stable
       â””â”€â”€ FAIL â”€â”€â–º Automated Rollback â”€â”€â–º Recovery Verification
```

### Phase Implementation Status

| Phase | Description | Status | Scope & Deliverables |
|:---|:---|:---:|:---|
| **Phase 1** | Environment Setup & Repo Initialization | âœ… Completed | Tools verified (Python 3.10, Git, Terraform, Azure CLI, Docker), directory layout, virtualenv initialized. |
| **Phase 2** | Flask Application, Tests & Docker Validation | âœ… Completed | Application factory (`app.app`), home dashboard, `/health` endpoint, 25 unit/integration tests, Dockerfile, cross-platform dependencies. |
| **Phase 3** | Terraform Infrastructure Provisioning & Verification | âœ… Completed | 8 Azure resources provisioned in `eastasia`; VM running; SSH/NSG corrected; Nginx and cloud-init verified. See `phase3_validation.md`. |
| **Phase 4** | Jenkins CI/CD Pipeline | âœ… Completed | Jenkins in Docker, GitHub Poll SCM, tests, packaging, Azure Run Command deployment, health validation, and build artifacts. |
| **Phase 5** | Health Validation & Self-Healing Logic | âœ… Completed | `deploy.sh`, `rollback.sh`, `health_check.py`, `health_policy.json`; a faulty release was rolled back and recovery was verified with `incident_report.json`. |
| **Phase 6** | Failure Injection, Evaluation & Documentation | ✅ Completed | Three synthetic fault types evaluated across nine Jenkins runs; 9/9 faulty builds failed and recovered; median total recovery 85.1-102.6s; manual baseline 121s. See `evaluation/phase6_report.md`. |

---

## 3. Phase 2 Features

In Phase 2, the core web application and testing infrastructure were implemented:

- **Application Factory Pattern (`app/app.py`)**: Uses `create_app()` allowing test isolation and configuration overrides without global state.
- **Home Dashboard (`GET /`)**: Renders a clean, dark-themed HTML interface showing project title, configured version, and pulse health status badge.
- **Health Endpoint (`GET /health`)**: Lightweight JSON endpoint returning HTTP 200 with `status` and `version` fields for automated probe consumption.
- **Version Configuration**: The application version is driven dynamically by the `HEALDEPLOY_VERSION` environment variable (default: `v1.0.0`).
- **Comprehensive Test Suite (`tests/`)**: 25 automated pytest tests verifying route responses, content types, JSON schemas, factory overrides, and 404 handlers.
- **Cross-Platform Dependencies**: `requirements.txt` utilizes PEP 508 platform markers (`sys_platform != 'win32'`) so `gunicorn` installs seamlessly on Linux/Docker while Windows local development remains clean.
- **Containerization (`Dockerfile`)**: Production-ready Dockerfile based on `python:3.10-slim` running Gunicorn with a non-root security user.

---

## 4. Phase 3 Infrastructure (Provisioned & Verified)

The infrastructure is provisioned in Azure and has been verified end to end. The declarative
Infrastructure as Code (IaC) configuration remains under `terraform/`. The full verification
record is in `phase3_validation.md`.

### Live Deployment

| Item | Value |
|---|---|
| Resource group | `rg-healdeploy-eastasia` |
| VM | `vm-healdeploy-prod` (running) |
| Public IP | `20.205.103.245` (static) |
| Application URL | http://20.205.103.245/ |
| Health URL | http://20.205.103.245/health |
| SSH | `ssh -i ~/.ssh/healdeploy_rsa azureuser@20.205.103.245` |

> Before the first release is deployed in Phase 4, HTTP requests return `502 Bad Gateway`
> because Nginx is running but Gunicorn is not yet installed under
> `/opt/healdeploy/current`. This is expected.

### Resource Architecture
1. **Resource Group (`rg-healdeploy-eastasia`)**: Dedicated boundary in `eastasia` (policy-allowed student region).
2. **Virtual Network & Subnet**: `vnet-healdeploy` (`10.0.0.0/16`) and `snet-healdeploy-app` (`10.0.1.0/24`).
3. **Network Security Group (`nsg-healdeploy`)**:
   - **Port 80 (HTTP)**: Inbound allow from `*` (Internet) for public web access.
   - **Port 22 (SSH)**: Inbound allow strictly restricted to the developer source IP (`allowed_ssh_cidr`, currently `106.76.187.20/32`). This is the address Azure actually receives, which can differ from public IP echo services on some ISPs and may change when the ISP rotates its NAT pool; update `terraform.tfvars` and the NSG rule when that happens.
   - **Port 8000 (Gunicorn)**: **Closed to Internet**; strictly bound to `127.0.0.1:8000` on the VM.
4. **Public IP (`pip-healdeploy-vm`)**: Standard SKU with Static allocation.
5. **Network Interface (`nic-healdeploy-vm`)**: Connects VM to subnet with static public IP and NSG association.
6. **Linux Virtual Machine (`vm-healdeploy-prod`)**:
   - **SKU**: `Standard_D2s_v4` (2 vCPUs, 8 GiB RAM, Gen2 architecture).
   - **OS**: Ubuntu Server 22.04 LTS (`Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest`).
   - **Auth**: SSH public-key authentication only; password authentication disabled.
   - **OS Disk**: 30 GB Standard SSD (`StandardSSD_LRS`).

### VM Bootstrapping (`cloud-init.yaml`)
- Updates package index and installs `python3`, `python3-venv`, `python3-pip`, `nginx`, `curl`, `git`.
- Creates dedicated non-root service account `healdeploy` (`/opt/healdeploy`).
- Initializes versioned release layout:
  - `/opt/healdeploy/releases/`
  - `/opt/healdeploy/current` (symlink target for active build)
  - `/opt/healdeploy/stable_release.txt` (recovery anchor)
- Configures Nginx reverse proxy on port 80 forwarding to `127.0.0.1:8000`.
- Deploys `healdeploy.service` systemd unit template pointing to `/opt/healdeploy/current/.venv/bin/gunicorn` and `app.app:create_app()`. (Registered via daemon-reload; started after Phase 4 deploys release 1).

---

## 5. Jenkins CI/CD Pipeline (Phase 4)

Jenkins runs in Docker (`jenkins/Dockerfile`, based on `jenkins/jenkins:lts-jdk17`) with
Python, Git, Azure CLI, OpenSSH, and Terraform 1.16.6. Azure authentication uses the
Jenkins credential `azure-healdeploy-sp`; its secret is not stored in the repository.

### Pipeline stages

1. **Checkout**: clone the GitHub `main` branch.
2. **Test**: create an isolated virtual environment and run pytest with JUnit results.
3. **Terraform Validate**: `fmt -check`, `init -backend=false`, and `validate`.
4. **Package**: create `build/healdeploy-<release>.tar.gz` containing the application and
   deployment helpers.
5. **Deploy and Verify**: upload the bundle to a private Azure Blob container, generate a
   short-lived read-only SAS, invoke Azure Run Command on the existing VM, verify the
   checksum and required files, run `deploy.sh`, and archive health artifacts.

The job uses Poll SCM and `disableConcurrentBuilds()`. A failed health policy keeps the Jenkins
build failed while the existing rollback procedure restores the previous stable release.

### Starting Jenkins

```powershell
docker build -t healdeploy-jenkins:phase4 jenkins/

# Generate a local admin password (gitignored)
$password = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
Set-Content -Path jenkins\.admin_password -Value $password -Encoding ascii -NoNewline

docker run -d --name healdeploy-jenkins --restart unless-stopped `
  -p 8080:8080 -p 50000:50000 `
  -v healdeploy-jenkins-home:/var/jenkins_home `
  -v "${env:USERPROFILE}\.ssh\healdeploy_rsa:/run/secrets/healdeploy_rsa:ro" `
  -e "JENKINS_ADMIN_PASSWORD=$password" `
  -e "JAVA_OPTS=-Djenkins.install.runSetupWizard=false" `
  healdeploy-jenkins:phase4
```

Open http://localhost:8080/ and sign in as `admin` with the password stored in
`jenkins/.admin_password`. The `healdeploy` job is created automatically.

### Self-healing deployment model

- Releases live in `/opt/healdeploy/releases/<release-id>/`, each with its own `.venv`.
- `/opt/healdeploy/current` is a symlink to the active release.
- `/opt/healdeploy/stable_release.txt` records the last release that passed the health policy.
- `deploy.sh` builds and activates a release, restarts `healdeploy.service`, and runs
  `health_check.py`.
- `health_policy.json` requires 9 of 10 successful probes, a p95 latency below 500 ms, a
  15-second startup grace, and 3-second probe intervals.
- If validation fails, `rollback.sh` restores the stable release, restarts the service, and
  re-runs the health policy.
- A failed release keeps the Jenkins build FAILURE even when recovery succeeds.
  `incident_report.json` records detection, rollback, recovery, and final verification
  timestamps.
- Releases are pruned to the latest five; the active and stable releases are never removed.

### Phase 4 verification

| Check | Result |
|---|---|
| Jenkins job `healdeploy` | Created from `https://github.com/Aaron-B-Mampilly/healdeploy.git` (`main`) |
| Builds #1-#6 | SUCCESS; Build #6 was the stable release used for the Phase 6 evaluation (`jenkins-6-5ff39f4`, `v1.0.6`) |
| Fault evaluation | 9/9 fault builds failed and recovered; see Phase 6 evaluation below |
| Public `/health` after Build #6 | `{"status": "healthy", "version": "v1.0.6"}` |
| Manual fault-500 release | Health policy failed; rollback restored the prior stable release; recovery verified |
| Terraform validation in Jenkins | `fmt -check`, `init -backend=false`, and `validate` passed |

### Phase 6 evaluation

Three synthetic fault branches were evaluated through Jenkins: `fault-500` (HTTP 500),
`fault-startup` (application fails to start), and `fault-slow` (health p95 exceeds 500ms).
Nine runs (three per fault) all produced FAILURE builds, and all nine rollbacks restored
and verified `jenkins-6-5ff39f4` (`v1.0.6`). Median total recovery was 85.1s for startup,
93.0s for HTTP 500, and 102.6s for slow health. A manual no-rollback baseline measured
121s under a fixed 120s observation window.

See `evaluation/phase6_report.md`, `evaluation/evaluation_results.json`, and
`evaluation/baseline_result.json` for the full results.

---

## 6. Prerequisites

- **Python**: 3.10.x (verified with 3.10.11)
- **Terraform**: 1.16.6+ (AzureRM provider `~> 4.0`)
- **Azure CLI**: 2.91.0+ (logged in via `az login`)
- **Git**: 2.x
- **Docker Desktop** (for containerized local testing)

---

## 7. Development Setup & Virtual Environment

Clone the repository and initialize the isolated virtual environment:

### Windows (CMD / PowerShell)
```bat
# Clone repository
git clone https://github.com/Aaron-B-Mampilly/healdeploy.git
cd healdeploy

# Activate virtual environment
.venv\Scripts\activate

# Install / update dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Linux / macOS / WSL
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (will include Gunicorn)
pip install -r requirements.txt
```

---

## 8. Running the Application Locally

```bat
# Set the version dynamically (Windows CMD)
set HEALDEPLOY_VERSION=v1.0.0

# Set the version dynamically (PowerShell)
$env:HEALDEPLOY_VERSION="v1.0.0"

# Run with Flask development server
python -m flask --app app.app run --port 5000
```
Navigate to:
- **Home Page**: [http://localhost:5000/](http://localhost:5000/)
- **Health Check**: [http://localhost:5000/health](http://localhost:5000/health)

---

## 9. Running the Automated Tests

All tests run offline without network or Azure dependencies using Flask's test client:

```bat
python -m pytest -v
```

---

## 10. Terraform Workflow & Safety Rules

All Terraform configuration lives in `terraform/`:

```bat
cd terraform

# 1. Format verification
terraform fmt -check -recursive

# 2. Initialize provider plugins
terraform init

# 3. Validate configuration syntax
terraform validate

# 4. Generate execution plan (DO NOT run apply without approval)
terraform plan
```

> [!CAUTION]
> **Provisioning Gate**: `terraform apply` must NEVER be run automatically. Always review the plan, region, VM SKU, and firewall rules before provisioning.
> 
> Stopping a VM halts compute billing, but storage (OS disk) and public IP continue to accrue charges. Use `terraform destroy` when resources are no longer needed.

---

## 11. Phase Implementation Boundaries

### Implemented & Validated:
- Phase 1: Environment, dependencies, `.venv`, Git repository.
- Phase 2: Flask app, `/health` endpoint, 25 pytest tests, Docker validation.
- Phase 3: Azure infrastructure provisioned (8 resources), SSH/NSG corrected, VM reachable, cloud-init and Nginx verified, Terraform converged with no pending changes.
- Phase 4: Jenkins in Docker, GitHub Poll SCM, versioned SSH deployment, health validation, and successful builds #1-#6; Build #6 was the stable release during the Phase 6 evaluation (`v1.0.6`).
- Phase 5: `deploy.sh`, `rollback.sh`, `health_check.py`, `health_policy.json`, incident reporting, and verified fault-500 rollback/recovery.
- Phase 6: `fault-500`, `fault-startup`, and `fault-slow` branches; nine Jenkins evaluation runs; 9/9 faulty builds failed and recovered; baseline and results in `evaluation/`.

### Deferred / Future Work:
- Production hardening: multi-node deployment, external health monitoring, secret management, and Jenkins high availability.
- Additional fault classes: network partitions, dependency failures, disk exhaustion, and load-induced latency.
- Load and concurrency testing with multiple simultaneous deployments.

---

## License & Academic Disclaimer

DevOps IA3 Academic Project â€” Developed for academic demonstration purposes.
