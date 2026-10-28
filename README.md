# HealDeploy

> **A Self-Healing CI/CD Pipeline with Automatic Rollback and Recovery Verification**

[![Phase 2: Complete](https://img.shields.io/badge/Phase%202-Completed-brightgreen.svg)]()
[![Python 3.10](https://img.shields.io/badge/Python-3.10-blue.svg)]()
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask%203.1.3-black.svg)]()
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
| **Phase 3** | Terraform & Azure Provisioning | ⏳ Planned | Azure Resource Group, VNet, Subnet, NSG, and Linux VM with systemd + Nginx setup. |
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
- **Containerization (`Dockerfile`)**: Multi-stage/production-ready Dockerfile based on `python:3.10-slim` running Gunicorn with a non-root security user.

---

## 4. Prerequisites

- **Python**: 3.10.x (verified with 3.10.11)
- **Git**: 2.x
- **Docker Desktop** (optional for containerized validation)
- **PowerShell / Windows Command Prompt** or Linux shell

---

## 5. Development Setup & Virtual Environment

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

## 6. Running the Application Locally

### Using Flask Development Server (Windows / Linux)
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

## 7. Running the Automated Tests

All tests run offline without network or Azure dependencies using Flask's test client:

```bat
# Run full test suite with verbose output
python -m pytest -v

# Run specific test modules
python -m pytest tests/test_app.py -v
python -m pytest tests/test_recovery.py -v
```

### Test Coverage Summary:
- **`tests/test_app.py`**:
  - `TestHomePage`: HTTP 200, HTML content type, project title presence, version string reflection, health status badge.
  - `TestHealthEndpoint`: HTTP 200, application/json content type, JSON validation, `status` and `version` fields.
  - `TestAppFactory`: Factory instantiation, test configuration injection, environment variable override.
  - `TestErrorHandling`: 404 responses on non-existent routes.
- **`tests/test_recovery.py`**:
  - Application-level recovery signal validation and simulated version rollbacks.

---

## 8. Docker Container Validation

A containerized build is provided for local packaging validation:

```bash
# Build the Docker image
docker build -t healdeploy:phase2 .

# Run the container mapping internal port 8000 to local port 8080
docker run --rm -p 8080:8000 -e HEALDEPLOY_VERSION=v1.0.0 healdeploy:phase2
```

Validate via HTTP:
```bash
curl http://localhost:8080/health
# Output: {"status":"healthy","version":"v1.0.0"}
```

---

## 9. Example `/health` Endpoint Response

When healthy, the endpoint returns **HTTP 200 OK**:

```json
{
  "status": "healthy",
  "version": "v1.0.0"
}
```

During deployment validation (Phase 5), the Jenkins pipeline evaluates this response against health thresholds to decide whether to promote or roll back.

---

## 10. Phase 2 Scope & Limitations

### Implemented in Phase 2:
- Modular Flask application with `create_app` factory.
- Configurable application versioning via `HEALDEPLOY_VERSION`.
- Responsive health dashboard and JSON `/health` endpoint.
- 25 automated pytest tests passing cleanly.
- `requirements.txt` configured with platform markers.
- Containerized `Dockerfile` with non-root security.

### Intentionally Deferred to Later Phases:
- Azure infrastructure provisioning (VM, NSG, VNet) is part of **Phase 3**.
- Jenkins CI/CD pipeline definition (`Jenkinsfile`) is part of **Phase 4**.
- Automated rollback scripts, health check polling scripts, and recovery validation logic are part of **Phase 5**.
- Fault injection and evaluation metrics are part of **Phase 6**.

---

## License & Academic Disclaimer

DevOps IA3 Academic Project — Developed for academic demonstration purposes.
