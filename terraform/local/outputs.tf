output "cluster_name" {
  description = "Name of the local k3d Kubernetes cluster"
  value       = var.cluster_name
}

output "kubeconfig_path" {
  description = "Path to the private cluster kubeconfig"
  value       = "${path.module}/../../local/.local/kubeconfig"
}

output "api_gateway_url" {
  description = "URL for the API Gateway endpoint"
  value       = "http://127.0.0.1:18081"
}

output "web_ui_url" {
  description = "URL for the Badminton Web User Interface"
  value       = "http://127.0.0.1:18082"
}

output "admin_ui_url" {
  description = "URL for the Badminton Admin Interface"
  value       = "http://127.0.0.1:18083"
}

output "argocd_url" {
  description = "URL for Argo CD UI"
  value       = "https://127.0.0.1:19445"
}

