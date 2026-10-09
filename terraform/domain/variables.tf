variable "aws_region" { type = string }
variable "zone_name" { type = string }
variable "public_domain_name" { type = string }
variable "admin_domain_name" { type = string }
variable "existing_zone_id" {
  type    = string
  default = null
}
variable "wait_for_certificate_validation" {
  type    = bool
  default = true
}
