resource "aws_route53_zone" "public" {
  count = var.existing_zone_id == null ? 1 : 0
  name  = var.zone_name
}
locals { zone_id = var.existing_zone_id != null ? var.existing_zone_id : aws_route53_zone.public[0].zone_id }
resource "aws_acm_certificate" "public" {
  domain_name               = var.public_domain_name
  subject_alternative_names = [var.admin_domain_name]
  validation_method         = "DNS"
  lifecycle { create_before_destroy = true }
}
resource "aws_route53_record" "validation" {
  for_each        = { for dvo in aws_acm_certificate.public.domain_validation_options : dvo.domain_name => dvo }
  zone_id         = local.zone_id
  name            = each.value.resource_record_name
  type            = each.value.resource_record_type
  records         = [each.value.resource_record_value]
  ttl             = 60
  allow_overwrite = true
}
resource "aws_acm_certificate_validation" "public" {
  count                   = var.wait_for_certificate_validation ? 1 : 0
  certificate_arn         = aws_acm_certificate.public.arn
  validation_record_fqdns = [for record in aws_route53_record.validation : record.fqdn]
}
