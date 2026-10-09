resource "aws_secretsmanager_secret" "application" {
  for_each                = local.secret_names
  name                    = "badminton/prod/${each.key}"
  description             = "Operator-populated Badminton secret; Terraform does not own value"
  recovery_window_in_days = 30
}
