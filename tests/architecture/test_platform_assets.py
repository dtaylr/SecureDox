from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_nginx_load_balancer_controls() -> None:
    nginx = read("infra/docker/nginx.conf")

    for expected in [
        "proxy_set_header X-Request-ID",
        "proxy_set_header X-Correlation-ID",
        "limit_req_zone",
        "client_max_body_size 10m",
        "proxy_read_timeout",
        "X-Content-Type-Options",
        "Content-Security-Policy",
        "location /health",
        "location /ready",
    ]:
        assert expected in nginx


def test_docker_compose_hardening_controls() -> None:
    compose = read("infra/docker/docker-compose.yml")

    for expected in [
        "no-new-privileges:true",
        "cap_drop",
        "read_only: true",
        "healthcheck",
        "networks:",
        "prometheus:",
        "grafana:",
    ]:
        assert expected in compose


def test_terraform_has_modules_environments_variables_and_outputs() -> None:
    required = [
        "infra/terraform/modules/securedox_stack/main.tf",
        "infra/terraform/modules/securedox_stack/variables.tf",
        "infra/terraform/modules/securedox_stack/outputs.tf",
        "infra/terraform/envs/local/main.tf",
        "infra/terraform/envs/staging/main.tf",
    ]

    for path in required:
        assert (ROOT / path).exists()

    assert 'source = "../../modules/securedox_stack"' in read("infra/terraform/envs/local/main.tf")
    assert "terraform_data" in read("infra/terraform/modules/securedox_stack/main.tf")


def test_ansible_roles_are_idempotent_and_documented() -> None:
    required = [
        "infra/ansible/playbooks/site.yml",
        "infra/ansible/playbooks/check.yml",
        "infra/ansible/roles/linux-hardening/tasks/main.yml",
        "infra/ansible/roles/docker-host/tasks/main.yml",
        "infra/ansible/roles/monitoring-agent/tasks/main.yml",
        "infra/ansible/README.md",
    ]

    for path in required:
        assert (ROOT / path).exists()

    assert "state: present" in read("infra/ansible/roles/linux-hardening/tasks/main.yml")
    assert "restart_policy: unless-stopped" in read(
        "infra/ansible/roles/monitoring-agent/tasks/main.yml"
    )


def test_kubernetes_manifests_have_operational_controls() -> None:
    k8s = "\n".join(path.read_text() for path in (ROOT / "infra/k8s/minikube/base").glob("*.yaml"))

    for expected in [
        "kind: Deployment",
        "kind: Service",
        "kind: Ingress",
        "kind: ConfigMap",
        "kind: Secret",
        "readinessProbe",
        "livenessProbe",
        "kind: HorizontalPodAutoscaler",
        "RollingUpdate",
        "allowPrivilegeEscalation: false",
    ]:
        assert expected in k8s


def test_iac_scans_run_in_ci() -> None:
    workflow = read(".github/workflows/platform-iac.yml")

    for expected in ["make terraform-validate", "make ansible-check", "make iac-scan", "make checkov"]:
        assert expected in workflow
