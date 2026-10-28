# HealDeploy

> **A Self-Healing CI/CD Pipeline with Automatic Rollback and Recovery Verification**

## Overview

HealDeploy automates the deployment of a Python Flask web application to Microsoft Azure using Terraform, Jenkins, and GitHub. Its core feature is a **self-healing deployment workflow**: after each release, the application is validated using health checks and configurable performance thresholds. If the release fails the health policy, the system automatically restores the previous stable release and verifies that recovery succeeded.

## Architecture

```
GitHub → Jenkins Pipeline → Terraform (Azure) → Flask App
                ↓
         Health Checks & Validation
                ↓
     PASS: Mark release stable
     FAIL: Rollback → Recovery Verification
```

## Technology Stack

| Component | Technology |
|---|---|
| Web Application | Python 3.10, Flask |
| CI/CD Pipeline | Jenkins (Docker container) |
| Infrastructure as Code | Terraform |
| Cloud Provider | Microsoft Azure |
| Version Control | GitHub |
| Testing | pytest, requests |

## Project Structure

```
healdeploy/
├── app/            # Flask web application
├── tests/          # pytest test suite
├── deploy/         # Deployment and rollback shell scripts
├── terraform/      # Azure infrastructure (Terraform)
├── evaluation/     # Health check and validation scripts
├── requirements.txt
├── .gitignore
├── .gitattributes
└── README.md
```

## Quick Start (Development)

```bash
# 1. Create and activate virtual environment
py -3.10 -m venv .venv
.venv\Scripts\activate        # Windows CMD
# source .venv/bin/activate   # Linux / macOS / WSL2

# 2. Install dependencies
python -m pip install -r requirements.txt

# 3. Run tests
pytest tests/
```

## Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Environment Setup & Repository Init | ✅ In Progress |
| 2 | Flask Application & Tests | ⏳ Planned |
| 3 | Terraform & Azure Provisioning | ⏳ Planned |
| 4 | Jenkins Pipeline | ⏳ Planned |
| 5 | Health Checks & Self-Healing Logic | ⏳ Planned |
| 6 | Evaluation & Documentation | ⏳ Planned |

## Security Notes

- Never commit `.env`, `terraform.tfvars`, `*.pem`, or any credentials.
- Terraform state files (`*.tfstate`) are excluded from version control.
- Azure service-principal secrets must be stored as Jenkins credentials or environment secrets only.

## License

Academic project — DevOps IA3. Not for production use.
