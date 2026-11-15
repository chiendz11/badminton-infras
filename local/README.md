# Badminton Local — k3d Bootstrap & Argo CD GitOps

Phiên bản hạ tầng local cho hệ thống **Badminton Manager V2**, đồng bộ theo mô hình **Pure Declarative GitOps + Argo CD Image Updater v1.5.0** của MaintAI:
- `terraform/bootstrap`, `terraform/domain`, `terraform/platform`, `terraform/argocd`: 4 state roots AWS Production.
- `terraform/local/`: Terraform module khởi tạo cụm `k3d` local và bootstrap Argo CD GitOps.
- `local/`: Cấu hình cluster `k3d`, `platform.lock.json`, `app-source.lock.json`, `contract.json`, `settings.example.json`, `LocalStack`, và unit tests (`local/tests/`).
- `localdev/`: CLI Python (`init`, `up`, `secrets`, `build`, `import-images`, `bootstrap-argocd`, `image-updater-pat`, `migrate`, `status`, `delete`).

---

## 1. Phân chia trách nhiệm giữa 3 Repository

| Repository | Trách nhiệm |
|---|---|
| `badminton-infras` (repo này) | Khởi tạo cụm `k3d-badminton-local`, kubeconfig riêng (`local/.local/kubeconfig`), namespaces (`badminton`, `argocd`, `observability`, `external-secrets`, `ingress-nginx`), LocalStack + `ClusterSecretStore/aws-secrets-manager`, Secrets Manager seeds, bootstrap Argo CD, secret `argocd-image-updater-git-creds` (`make local-image-updater-pat`), và chạy DB migrations. |
| `../badminton-gitops` | Pure Declarative Kustomize (`bootstrap/local` -> `applications/local`): Local PostgreSQL/Mongo/Redis/RabbitMQ, Ingress + NetworkPolicies, `external-secrets` / `ingress-nginx` / `argocd-image-updater` addons, `ImageUpdater` CRD `badminton-local`, và toàn bộ `environments/local/apps`. |
| `../badminton-system` (`38b4a74cea88d69c271b3a4608b5e38754797b86`) | Mã nguồn ứng dụng + Dockerfile + migrations. CI đóng gói và đẩy image tag bất biến `sha-<40>` lên GHCR (`ghcr.io/chiendz11/badminton-*`). |

---

## 2. Yêu cầu môi trường

- **Docker Engine**: `>= 24.0`
- **k3d**: `v5.9.0`
- **kubectl**: tương thích Kubernetes `1.35` / `1.36` (Kustomize tích hợp `>= 5.8`)
- **Python**: `>= 3.12`
- **Terraform**: `>= 1.15.6, < 1.16.0` (`.terraform-version` = `1.15.6`)

---

## 3. Khởi chạy nhanh (Runbook)

### Cách 1: Terraform 1-Click + GitOps PR Automation (GHCR `sha-<40>`)

```bash
# 1. Khởi tạo cụm k3d, LocalStack, ClusterSecretStore, secrets và bootstrap Argo CD
terraform -chdir=terraform/local init
terraform -chdir=terraform/local apply -auto-approve

# 2. Nạp Fine-grained GitHub PAT vào LocalStack Secrets Manager (ESO sync -> argocd/argocd-image-updater-git-creds)
make local-image-updater-pat PAT_FILE=../PAT.txt

# 3. Chạy migrations & kiểm tra trạng thái
make local-migrate
make local-status
```

### Cách 2: Phát triển Offline (Inner-Loop Dev)

```bash
make local-init
make local-up
make local-secrets
make local-build
make local-import
make local-bootstrap-argocd
make local-migrate
make local-status
```

---

## 4. Điểm truy cập dịch vụ Local

### Ingress Hostnames (`/etc/hosts`)
Ánh xạ `172.24.0.2 web.badminton.local admin.badminton.local api.badminton.local`:
- **Web Frontend**: `http://web.badminton.local`
- **Admin Frontend**: `http://admin.badminton.local`
- **API Gateway**: `http://api.badminton.local/health/ready`

### Host Loopback NodePorts
| Dịch vụ | Host Loopback | Container / NodePort | Mô tả |
|---|---|---|---|
| **Web Frontend (HTTPS Ingress)** | `https://web.badminton.local` | Ingress HTTPS `443 -> 30444` (yêu cầu `/etc/hosts` trỏ `127.0.0.1`) | Web người dùng (same-origin `/api` + `Secure` refresh cookie) |
| **Admin Frontend (HTTPS Ingress)** | `https://admin.badminton.local` | Ingress HTTPS `443 -> 30444` (yêu cầu `/etc/hosts` trỏ `127.0.0.1`) | Web quản trị (same-origin `/api` + `Secure` refresh cookie) |
| **Mailpit UI (HTTPS Ingress)** | `https://mailpit.badminton.local` | Ingress HTTPS `443 -> 30444` (yêu cầu `/etc/hosts` trỏ `127.0.0.1`) | Hộp thư local bắt email xác thực từ `identity-service` |
| **API Gateway** | `http://127.0.0.1:18081` | NodePort `30081` / `8081` | REST Gateway điều phối (legacy direct port) |
| **Web Frontend (Direct)** | `http://127.0.0.1:18082` | NodePort `30082` / `80` | Web người dùng (legacy direct port) |
| **Admin Frontend (Direct)** | `http://127.0.0.1:18083` | NodePort `30083` / `80` | Web quản trị (legacy direct port) |
| **Argo CD UI** | `https://127.0.0.1:19445` | NodePort `30443` / `443` | Argo CD UI |
| **PostgreSQL** | `127.0.0.1:15432` | NodePort `30432` / `5432` | CSDL Booking & AI |

---

## 5. Offline Validation & Unit Tests

```bash
python3 scripts/source_policy.py
terraform fmt -check -recursive terraform/
python3 -m localdev.checks --app-root ../badminton-system
python3 -m unittest discover -s local/tests -p 'test_*.py' -v
```

Xem thêm đối chiếu Local vs Cloud tại [`docs/LOCAL_VS_AWS_CLOUD_PARITY.md`](../docs/LOCAL_VS_AWS_CLOUD_PARITY.md).
