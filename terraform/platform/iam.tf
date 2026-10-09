data "aws_iam_policy_document" "irsa_trust" {
  for_each = local.service_accounts

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [module.eks.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:sub"
      values   = ["system:serviceaccount:${each.value.namespace}:${each.value.name}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${replace(module.eks.cluster_oidc_issuer_url, "https://", "")}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "service_account" {
  for_each           = local.service_accounts
  name               = "${local.name}-${replace(each.key, "_", "-")}"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust[each.key].json
}


data "aws_iam_policy_document" "external_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
    resources = [for secret in aws_secretsmanager_secret.application : secret.arn]
  }
}
data "aws_iam_policy_document" "external_dns" {
  statement {
    actions   = ["route53:ChangeResourceRecordSets", "route53:ListResourceRecordSets", "route53:ListTagsForResource"]
    resources = ["arn:aws:route53:::hostedzone/${local.route53_zone_id}"]
  }
  statement {
    actions   = ["route53:ListHostedZones", "route53:ListHostedZonesByName"]
    resources = ["*"]
  }
}
resource "aws_iam_role_policy" "external_secrets" {
  name   = "read-project-secrets"
  role   = aws_iam_role.service_account["external_secrets"].id
  policy = data.aws_iam_policy_document.external_secrets.json
}
resource "aws_iam_role_policy" "external_dns" {
  name   = "manage-project-zone"
  role   = aws_iam_role.service_account["external_dns"].id
  policy = data.aws_iam_policy_document.external_dns.json
}
resource "aws_iam_role_policy" "load_balancer" {
  name   = "aws-load-balancer-controller"
  role   = aws_iam_role.service_account["aws_load_balancer_controller"].id
  policy = file("${path.module}/policies/aws-load-balancer-controller.json")
}
resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.service_account["ebs_csi"].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}
data "aws_iam_policy_document" "publisher_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.terraform_remote_state.bootstrap.outputs.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.app_repository}:environment:production"]
    }
  }
}
resource "aws_iam_role" "app_publisher" {
  name               = "${local.name}-app-publisher"
  assume_role_policy = data.aws_iam_policy_document.publisher_trust.json
}
data "aws_iam_policy_document" "publisher" {
  statement {
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }
  statement {
    actions   = ["ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload", "ecr:GetDownloadUrlForLayer", "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart", "ecr:BatchGetImage", "ecr:DescribeImages"]
    resources = [for repo in aws_ecr_repository.services : repo.arn]
  }
}
resource "aws_iam_role_policy" "app_publisher" {
  name   = "publish-project-images"
  role   = aws_iam_role.app_publisher.id
  policy = data.aws_iam_policy_document.publisher.json
}
data "aws_iam_policy_document" "gitops_verifier_trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.terraform_remote_state.bootstrap.outputs.github_oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.gitops_repository}:environment:production-automation"]
    }
  }
}
resource "aws_iam_role" "gitops_verifier" {
  name               = "${local.name}-gitops-release-verifier"
  assume_role_policy = data.aws_iam_policy_document.gitops_verifier_trust.json
}
resource "aws_iam_role_policy" "gitops_verifier" {
  name = "inspect-project-images"
  role = aws_iam_role.gitops_verifier.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
      { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:DescribeImages", "ecr:BatchCheckLayerAvailability"], Resource = [for repo in aws_ecr_repository.services : repo.arn] }
    ]
  })
}
