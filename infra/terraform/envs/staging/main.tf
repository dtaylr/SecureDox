module "securedox_stack" {
  source = "../../modules/securedox_stack"

  environment           = "staging"
  api_replicas          = 2
  worker_replicas       = 2
  enable_public_ingress = false
  allowed_cidr_blocks   = ["10.0.0.0/8"]
  image_tag             = var.image_tag
}
