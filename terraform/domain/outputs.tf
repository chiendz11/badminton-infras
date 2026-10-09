output "route53_zone_id" { value = local.zone_id }
output "public_domain_name" { value = var.public_domain_name }
output "admin_domain_name" { value = var.admin_domain_name }
output "public_certificate_arn" { value = aws_acm_certificate.public.arn }
output "name_servers" { value = var.existing_zone_id == null ? aws_route53_zone.public[0].name_servers : [] }
