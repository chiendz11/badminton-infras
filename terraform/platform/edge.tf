locals {
  public_domain_name     = data.terraform_remote_state.domain.outputs.public_domain_name
  admin_domain_name      = data.terraform_remote_state.domain.outputs.admin_domain_name
  public_certificate_arn = data.terraform_remote_state.domain.outputs.public_certificate_arn
  route53_zone_id        = data.terraform_remote_state.domain.outputs.route53_zone_id
}
