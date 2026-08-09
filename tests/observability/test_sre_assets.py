from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_METRICS = {
    "http_request_duration_seconds",
    "http_requests_total",
    "document_processing_duration_seconds",
    "document_processing_failures_total",
    "ocr_confidence_score",
    "upload_rejections_total",
    "security_access_denied_total",
    "rate_limit_triggered_total",
    "release_gate_failures_total",
    "test_flake_rate",
    "critical_path_pass_rate",
}

REQUIRED_DASHBOARDS = {
    "service-health.json",
    "release-readiness.json",
    "security-events.json",
    "test-quality.json",
}

REQUIRED_RUNBOOKS = {
    "docs/sre-runbooks/document-processing-latency.md",
    "docs/sre-runbooks/ocr-failure-spike.md",
    "docs/sre-runbooks/release-gate-failure.md",
    "docs/sre-runbooks/security/idor-attempts-spike.md",
    "docs/sre-runbooks/security/secret-detected-in-ci.md",
}

REQUIRED_LOG_FIELDS = {
    "correlation_id",
    "user_id",
    "document_id",
    "job_id",
    "service_name",
    "event_type",
    "status",
    "latency_ms",
    "error_code",
}


def test_required_metrics_are_defined() -> None:
    metrics_source = (ROOT / "packages/observability/python/securedox_observability/metrics.py").read_text()

    missing = [metric for metric in REQUIRED_METRICS if f'"{metric}"' not in metrics_source]

    assert not missing


def test_structured_log_context_fields_are_defined() -> None:
    logging_source = (ROOT / "apps/api/app/core/logging.py").read_text()

    missing = [field for field in REQUIRED_LOG_FIELDS if field not in logging_source]

    assert not missing


def test_grafana_dashboards_parse_and_have_panels() -> None:
    dashboard_dir = ROOT / "observability/grafana/dashboards"

    assert REQUIRED_DASHBOARDS == {path.name for path in dashboard_dir.glob("*.json")}
    for dashboard_path in dashboard_dir.glob("*.json"):
        dashboard = json.loads(dashboard_path.read_text())
        assert dashboard["uid"]
        assert dashboard["title"]
        assert dashboard["panels"]


def test_alerts_link_to_existing_runbooks() -> None:
    alerts = (ROOT / "observability/prometheus/alerts.yml").read_text()

    for runbook in REQUIRED_RUNBOOKS:
        assert runbook in alerts
        assert (ROOT / runbook).exists()


def test_runbooks_include_failure_injection_drills() -> None:
    for runbook in REQUIRED_RUNBOOKS:
        text = (ROOT / runbook).read_text()
        assert "Failure Injection Drill" in text
        assert "correlation_id" in text or "release-readiness" in text or "Gitleaks" in text


def test_prometheus_and_grafana_are_wired_into_compose() -> None:
    compose = (ROOT / "infra/docker/docker-compose.yml").read_text()

    assert "prometheus:" in compose
    assert "grafana:" in compose
    assert "observability/prometheus/prometheus.yml" in compose
    assert "observability/grafana/dashboards" in compose


def test_failure_injection_scenarios_are_testable() -> None:
    manifest = json.loads((ROOT / "tests/observability/failure-injection-scenarios.json").read_text())
    metrics_source = (ROOT / "packages/observability/python/securedox_observability/metrics.py").read_text()

    assert manifest["scenarios"]
    for scenario in manifest["scenarios"]:
        assert scenario["id"]
        assert scenario["injection"]
        assert (ROOT / scenario["runbook"]).exists()
        assert scenario["expected_signals"]
        for signal in scenario["expected_signals"]:
            assert signal in metrics_source
