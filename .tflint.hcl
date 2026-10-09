config { format = "compact" }
plugin "aws" {
  enabled = true
  version = "0.38.0"
  source = "github.com/terraform-linters/tflint-ruleset-aws"
}
rule "terraform_required_version" { enabled = true }
rule "terraform_documented_variables" { enabled = false }
rule "terraform_documented_outputs" { enabled = false }
