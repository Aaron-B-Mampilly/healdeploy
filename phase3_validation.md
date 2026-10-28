# Phase 3 Validation Report — Terraform and Azure Infrastructure

**Project:** HealDeploy  
**Date:** 29 October 2026 (IST)  
**Status:** Infrastructure provisioned and verified. Application release deployment remains Phase 4 work.

---

## 1. Scope

This report records the verification of the already-provisioned Azure infrastructure and the
SSH/network correction performed after the previous handoff. No resources were recreated.
The only infrastructure change applied in this phase was an in-place update to the SSH source
address on the existing Network Security Group.

---

## 2. Azure Context

| Item | Value |
|---|---|
| Subscription | Azure for Students (`12a10260-24c6-4c16-a86e-b77fbfef0438`) |
| State | Enabled |
| Region | `eastasia` (East Asia) |
| Resource group | `rg-healdeploy-eastasia` |
| VM | `vm-healdeploy-prod` |
| VM size | `Standard_D2s_v4` (2 vCPU, 8 GiB RAM) |
| Public IP | `20.205.103.245` (Standard SKU, static) |
| Provisioning state | `Provisioning succeeded` |
| Power state | `VM running` |

Azure CLI and Terraform were used from the existing installation paths; no tools were
reinstalled and no broad SKU/region scans were performed.

---

## 3. SSH Source-Address Correction

### 3.1 Problem

The NSG allowed SSH from `157.51.60.5/32`, which was no longer the developer's address.
Public IP echo services (`api.ipify.org`, `ifconfig.me`, `icanhazip.com`,
`checkip.amazonaws.com`) reported `106.76.191.209`.

After updating the rule to `106.76.191.209/32`, TCP port 22 was still unreachable while
TCP port 80 to the same VM worked. The effective NSG rules correctly allowed SSH from
`106.76.191.209/32`, and the VM was listening on `0.0.0.0:22`.

### 3.2 Root cause

The ISP uses more than one IPv4 egress address. The address Azure actually receives from this
machine was determined from the Nginx access log on the VM:

```
106.76.185.171 - - [...] "GET / HTTP/1.1" 502 ...
```

Repeated requests from this machine consistently appeared as `106.76.185.171`, not
`106.76.191.209`. The NSG rule was therefore pinned to the address Azure actually sees.

> Operational note: this ISP may change or rotate the egress address. If SSH stops working,
> re-check the source address from the VM's Nginx access log and update
> `allowed_ssh_cidr` in `terraform/terraform.tfvars`, then re-plan and apply.

### 3.3 Change applied

`terraform/terraform.tfvars`:

```hcl
allowed_ssh_cidr = "106.76.185.171/32"
```

Fresh plan before apply:

```
Plan: 0 to add, 1 to change, 0 to destroy.
  # azurerm_network_security_group.nsg will be updated in-place
```

Apply result:

```
Apply complete! Resources: 0 added, 1 changed, 0 destroyed.
```

No VM replacement, deletion, or unrelated change was proposed or applied.

### 3.4 Verified NSG rules

| Rule | Priority | Port | Source | Access |
|---|---:|---:|---|---|
| `allow-http-inbound` | 100 | 80 | `*` | Allow |
| `allow-ssh-restricted` | 110 | 22 | `106.76.185.171/32` | Allow |

Effective NSG rules on `nic-healdeploy-vm` confirmed the same values. Port 8000 is not
exposed.

---

## 4. SSH Connectivity

- Local private key: `%USERPROFILE%\.ssh\healdeploy_rsa`
- Local public key matches the key configured in `terraform.tfvars` exactly.
- Server host keys were obtained authoritatively through the Azure VM Run Command control
  plane and independently compared with `ssh-keyscan` output. The fingerprints matched:

| Key type | SHA-256 fingerprint |
|---|---|
| ED25519 | `SHA256:i9N/JDG7eMOnCzxpJUoVf7QB82jXb9VFdVXhXeU6rlo` |
| RSA | `SHA256:IK+6DV8j+nK78cgg3fdiWDAqCYoIFOnkJgMEsjq8N7I` |

- Login succeeded as `azureuser@vm-healdeploy-prod`.
- The Windows OpenSSH 9.5 client reported a KEX warning with `ssh-keyscan`; connecting with
  the Git for Windows OpenSSH 10.0 client succeeded without issue.

---

## 5. In-VM Bootstrap Verification

| Check | Result | Notes |
|---|---|---|
| `cloud-init status --long` | `done` | `extended_status: degraded done` due to a schema warning (see below) |
| `nginx -t` | Pass | Configuration syntax OK |
| `systemctl status nginx` | Active (running) | Enabled and serving on port 80 |
| `id healdeploy` | Pass | `uid=998(healdeploy) gid=998(healdeploy)` |
| `getent passwd healdeploy` | Pass | Home corrected to `/opt/healdeploy` |
| `/opt/healdeploy/releases/` | Present, empty | Expected before the first Phase 4 release |
| `/opt/healdeploy/shared/` | Present | Created by cloud-init |
| `/opt/healdeploy/stable_release.txt` | Present, empty | Expected before the first release |
| `healdeploy.service` unit | Registered | `disabled` / `inactive` — expected until Phase 4 deploys a release |
| sshd | Active, enabled | Listening on `0.0.0.0:22` and `[::]:22` |
| `ufw` | Inactive | No host firewall conflict |
| iptables | Default ACCEPT | No host firewall conflict |

### 5.1 cloud-init schema warning

The live instance reported:

```
users.1: Additional properties are not allowed ('home' was unexpected)
```

The cloud-init user key is `homedir`, not `home`. This did not prevent the bootstrap commands
from completing, but it made the schema validation fail. The source file was corrected:

```yaml
    homedir: /opt/healdeploy
```

The corrected file was uploaded to the VM and validated with
`cloud-init schema -c /tmp/cloud-init-fixed.yaml`, which returned:

```
Valid schema /tmp/cloud-init-fixed.yaml
```

Because cloud-init runs only at first boot, the existing instance's stored first-boot
configuration still contains the old key and continues to show the warning. The live user's
home was corrected with `usermod -d /opt/healdeploy healdeploy`.

`terraform/main.tf` now ignores `custom_data` drift so that future edits to the bootstrap file
do not replace an already-provisioned VM:

```hcl
lifecycle {
  ignore_changes = [custom_data]
}
```

---

## 6. Public HTTP Verification

| URL | Result | Interpretation |
|---|---|---|
| `http://20.205.103.245/` | HTTP 502 Bad Gateway | Nginx is reachable; Gunicorn/application is not deployed yet |
| `http://20.205.103.245/health` | HTTP 502 Bad Gateway | Same as above; expected before Phase 4 |

Nginx access logs confirmed requests from this machine reached the VM. The 502 responses are
not an infrastructure failure; they are the expected state before the first release is
installed under `/opt/healdeploy/current`.

---

## 7. Terraform Validation

| Check | Result |
|---|---|
| `terraform fmt -check -recursive` | Pass |
| `terraform validate` | Pass |
| `terraform plan` after apply | `No changes. Your infrastructure matches the configuration.` |
| Resources managed | 8 |
| Resources added/changed/destroyed during final verification | 0 / 0 / 0 |

Terraform state and the provider lock file were preserved. Plan artifacts were deleted and
`*.tfplan` was added to `.gitignore`.

---

## 8. Security and Cost Notes

- SSH is restricted to a single `/32` source address.
- HTTP is intentionally public on port 80.
- Gunicorn port 8000 remains private (`127.0.0.1:8000`).
- Password authentication is disabled; only the configured SSH public key is accepted.
- Private keys, `terraform.tfvars`, and Terraform state are not committed to Git.
- The VM is running and incurring compute charges (earlier estimate: roughly USD 2.50/day).
  It can be deallocated when not in use; deallocation stops compute billing but storage and
  networking charges can continue.

---

## 9. Phase 3 Acceptance Criteria

| Criterion | Status |
|---|---|
| SSH rule corrected to the address Azure actually receives | Pass |
| SSH connectivity verified | Pass |
| Server host key verified against Azure control-plane data | Pass |
| cloud-init bootstrap executed | Pass (schema warning corrected in source) |
| Nginx installed, configured, and running | Pass |
| `healdeploy` service account exists | Pass |
| Release directories and stable-release record exist | Pass |
| Application service registered | Pass (inactive by design) |
| Public HTTP path reaches Nginx | Pass (502 until first release) |
| Terraform fmt/validate/plan clean | Pass |

**Conclusion:** Phase 3 infrastructure verification is complete. The VM is reachable, Nginx is
serving, the service account and release layout exist, and Terraform is converged with no
pending changes. The next step is Phase 4: deploy the first release through Jenkins.
