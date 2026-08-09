variable "environment" {
  description = "Deployment environment name."
  type        = string
}

variable "api_replicas" {
  description = "Desired API replica count."
  type        = number
  default     = 2

  validation {
    condition     = var.api_replicas >= 1 && var.api_replicas <= 10
    error_message = "api_replicas must be between 1 and 10."
  }
}

variable "worker_replicas" {
  description = "Desired worker replica count."
  type        = number
  default     = 2

  validation {
    condition     = var.worker_replicas >= 1 && var.worker_replicas <= 20
    error_message = "worker_replicas must be between 1 and 20."
  }
}

variable "enable_public_ingress" {
  description = "Whether ingress should be internet-facing."
  type        = bool
  default     = false
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to reach ingress."
  type        = list(string)
  default     = ["127.0.0.1/32"]
}

variable "image_tag" {
  description = "Container image tag to deploy."
  type        = string
  default     = "local"
}
