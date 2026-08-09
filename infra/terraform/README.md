# SecureDox Terraform

This Terraform tree demonstrates module structure, variables, outputs,
environment separation, and idempotent plans without requiring cloud
credentials.

## Commands

```bash
terraform -chdir=infra/terraform/envs/local fmt -recursive
terraform -chdir=infra/terraform/envs/local init -backend=false
terraform -chdir=infra/terraform/envs/local validate

terraform -chdir=infra/terraform/envs/staging fmt -recursive
terraform -chdir=infra/terraform/envs/staging init -backend=false
terraform -chdir=infra/terraform/envs/staging validate
```

Run IaC scanning:

```bash
make iac-scan
make checkov
```
