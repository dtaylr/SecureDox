module "securedox_stack" {
  source = "../../modules/securedox_stack"

  environment           = "local"
  api_replicas          = 1
  worker_replicas       = 1
  enable_public_ingress = false
  allowed_cidr_blocks   = ["127.0.0.1/32"]
  image_tag             = "local"
}
