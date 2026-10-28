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
       │ (Push / Tag)
       ▼
Jenkins Pipeline (Docker)
       │ (Trigger Terraform & Remote Exec)
       ▼
Azure Linux Virtual Machine (Nginx + Gunicorn + Flask in virtualenv)
       │
       ▼
Deployment Health Check & Policy Evaluation
       ├── PASS ──► Release Promoted to Stable
       └── FAIL ──► Automated Rollback ──► Recovery Verification
```

### Phase Implementation Status

| Phase | Description | Status | Scope & Deliverables |
|:---|:---|:---:|:---|
| **Phase 1** | Environment Setup & Repo Initialization | ✅ Completed | Tools verified (Python 3.10, Git, Terraform, Azure CLI, Docker), directory layout, virtualenv initialized. |
| **Phase 2** | Flask Application, Tests & Docker Validation | ✅ Completed | Application factory (`app.app`), home dashboard, `/health` endpoint, 25 unit/integration tests, Dockerfile, cross-platform dependencies. |
| **Phase 3** | Terraform Infrastructure Provisioning & Verification | ✅ Completed | 8 Azure resources provisioned in `eastasia`; VM running; SSH/NSG corrected; Nginx and cloud-init verified. See `phase3_validation.md`. |
| **Phase 4** | Jenkins CI/CD Pipeline | ⏳ Planned | Multi-stage Jenkinsfile for linting, testing, packaging, and zero-downtime deployment. |
| **Phase 5** | Health Validation & Self-Healing Logic | ⏳ Planned | Automated health probe scripts, rollback triggers, and recovery verification. |
| **Phase 6** | Failure Injection, Evaluation & Documentation | ⏳ Planned | Synthetic bad release testing, rollback verification logs, demonstration metrics. |

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
   - **Port 22 (SSH)**: Inbound allow strictly restricted to the developer source IP (`allowed_ssh_cidr`, currently `106.76.185.171/32`). This is the address Azure actually receives, which can differ from public IP echo services on some ISPs.
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

## 5. Prerequisites

- **Python**: 3.10.x (verified with 3.10.11)
- **Terraform**: 1.16.6+ (AzureRM provider `~> 4.0`)
- **Azure CLI**: 2.91.0+ (logged in via `az login`)
- **Git**: 2.x
- **Docker Desktop** (for containerized local testing)

---

## 6. Development Setup & Virtual Environment

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

## 7. Running the Application Locally

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

## 8. Running the Automated Tests

All tests run offline without network or Azure dependencies using Flask's test client:

```bat
python -m pytest -v
```

---

## 9. Terraform Workflow & Safety Rules

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

## 10. Phase Implementation Boundaries

### Implemented & Validated:
- Phase 1: Environment, dependencies, `.venv`, Git repository.
- Phase 2: Flask app, `/health` endpoint, 25 pytest tests, Docker validation.
- Phase 3: Azure infrastructure provisioned (8 resources), SSH/NSG corrected, VM reachable, cloud-init and Nginx verified, Terraform converged with no pending changes.

### Deferred to Future Phases:
- First application release and Jenkins CI/CD pipeline definition (`Jenkinsfile`): **Phase 4**.
- Automated rollback scripts, health check polling scripts, and recovery validation logic: **Phase 5**.
- Fault injection and evaluation metrics: **Phase 6**.

---

## License & Academic Disclaimer

DevOps IA3 Academic Project — Developed for academic demonstration purposes.
