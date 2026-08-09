# Platform Review Notes

This folder points reviewers to the platform layer without requiring them to
run a cluster.

## What To Review

- Docker Compose hardening: `infra/docker/docker-compose.yml`
- Nginx load balancer: `infra/docker/nginx.conf`
- Terraform module and envs: `infra/terraform`
- Ansible playbooks: `infra/ansible`
- Minikube manifests: `infra/k8s/minikube`
- Platform CI: `.github/workflows/platform-iac.yml`
- Architecture tests: `tests/architecture/test_platform_assets.py`

## Fast Checks

```bash
make test-platform
node --experimental-strip-types scripts/agents/impacted-tests.ts --file infra/docker/nginx.conf
```
