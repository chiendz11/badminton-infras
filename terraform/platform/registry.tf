resource "aws_ecr_repository" "services" {
  for_each             = local.ecr_services
  name                 = "${local.name}/${each.key}"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
}
# Do not expire tagged images: old GitOps digests must remain recoverable.
resource "aws_ecr_lifecycle_policy" "services" {
  for_each   = aws_ecr_repository.services
  repository = each.value.name
  policy     = jsonencode({ rules = [{ rulePriority = 1, description = "Expire untagged build leftovers", selection = { tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 30 }, action = { type = "expire" } }] })
}
