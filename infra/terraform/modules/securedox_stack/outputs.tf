output "environment" {
  description = "Environment name."
  value       = var.environment
}

output "deployment_plan" {
  description = "Normalized platform deployment plan."
  value       = terraform_data.deployment_plan.output
}

output "service_names" {
  description = "Service inventory managed by this stack."
  value       = local.service_names
}

output "recommended_release_gates" {
  description = "Release gates required before this environment can be promoted."
  value       = ["security-gates", "contract-tests", "db-tests", "observability-tests", "release-readiness"]
}
