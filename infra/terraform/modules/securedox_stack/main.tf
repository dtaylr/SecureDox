locals {
  service_names = ["api", "worker", "web", "nginx", "postgres", "redis", "prometheus", "grafana"]
  deployment_plan = {
    environment           = var.environment
    api_replicas          = var.api_replicas
    worker_replicas       = var.worker_replicas
    image_tag             = var.image_tag
    enable_public_ingress = var.enable_public_ingress
    allowed_cidr_blocks   = var.allowed_cidr_blocks
    services              = local.service_names
    security_controls = {
      tls_required              = var.environment != "local"
      public_ingress_restricted = !var.enable_public_ingress || length(var.allowed_cidr_blocks) > 0
      container_scanning        = true
      release_gates_required    = true
    }
  }
}

resource "terraform_data" "deployment_plan" {
  input = local.deployment_plan
}
