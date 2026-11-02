# Badminton Local — k3d Bootstrap & Argo CD GitOps

Phiên bản hạ tầng local **1.0.0** cho hệ thống Badminton Manager V2, xây dựng theo kiến trúc phân tách ranh giới của MaintAI:
- `terraform/platform/`: Quản lý hạ tầng AWS EKS / RDS / VPC Production.
- `terraform/local/`: Terraform module khởi tạo cụm k3d local và tích hợp GitOps.
- `local/`: Cấu hình cluster k3d, tool pins, contract, settings, và receipts.
- `localdev/`: Bộ công cụ tự động hóa CLI (init, up, secrets, build, import, bootstrap, migrate, status).

---

## 1. Phân chia trách nhiệm giữa các Repository

| Nơi sở hữu | Trách nhiệm |
|---|---|
| `badminton-infras` (repo này) | Khởi tạo cụm `k3d-badminton-local`, kubeconfig riêng (`local/.local/kubeconfig`), namespaces (`badminton`, `argocd`), Kubernetes Secrets, bootstrap Argo CD, thực thi DB migration jobs. |
| `../badminton-gitops` | Khai báo trạng thái mong muốn (Desired State) trong Kubernetes: PostgreSQL datastore (`environments/local/platform`) và các microservices / frontend workloads (`environments/local/apps`) kéo image từ GHCR. |
| `../badminton-system` | Mã nguồn ứng dụng (Booking Core, AI Service, API Gateway, Web Frontend, Admin Frontend, Prisma migrations, Alembic migrations). CI tự động đóng gói và đẩy image lên GitHub Container Registry (`ghcr.io/chiendz11`). |

---

## 2. Chuẩn bị môi trường

Yêu cầu trên máy tính cá nhân:
- **Docker Engine**: `>= 24.0` (đang chạy: `sudo systemctl start docker`)
- **k3d**: `v5.9.0`
- **kubectl**: Tương thích Kubernetes `1.35` / `1.36`
- **Python**: `>= 3.11`
- **Terraform**: `>= 1.5.0`

---

## 3. Khởi chạy nhanh (Runbook)

### Cách 1: Sử dụng Terraform 1-Click (Khuyên dùng — Local Staging kéo từ GHCR)

Hệ thống tự động kéo các Docker images Public từ `ghcr.io/chiendz11/badminton-...:latest` do CI/CD phát hành:

```bash
# 1. Khởi tạo cụm k3d, nạp secrets và bootstrap Argo CD
cd terraform/local
terraform init
terraform apply -auto-approve

# 2. Quay lại thư mục gốc chạy migration và nạp seed data
cd ../..
make local-migrate

# 3. Kiểm tra trạng thái các Pods
make local-status
```

### Cách 2: Chế độ Phát triển Offline (Inner-Loop Dev)

Dành cho khi bạn đang sửa code dở dang trên máy và muốn kiểm thử ngay mà không cần commit/push lên GitHub:

```bash
# 1. Khởi tạo môi trường ảo và cụm k3d
make local-init
make local-up
make local-secrets

# 2. Build và nạp image trực tiếp từ mã nguồn local vào k3d cache
make local-build
make local-import

# 3. Bootstrap Argo CD và chạy migrations
make local-bootstrap-argocd
make local-migrate
make local-status
```

---

## 4. Các cổng dịch vụ Local

| Dịch vụ | Cổng Host Loopback | Cổng Container / NodePort | Mô tả |
|---|---|---|---|
| **API Gateway** | `http://127.0.0.1:18081` | NodePort `30081` / Port `8081` | REST Gateway điều phối Booking & AI |
| **Web Frontend** | `http://127.0.0.1:18082` | NodePort `30082` / Port `80` | Giao diện đặt sân cho người dùng |
| **Admin Frontend**| `http://127.0.0.1:18083` | NodePort `30083` / Port `80` | Giao diện quản trị sân cầu lông |
| **Argo CD UI** | `https://127.0.0.1:19445` | NodePort `30443` / Port `443` | Giao diện điều khiển GitOps Argo CD |
| **PostgreSQL** | `127.0.0.1:15432` | NodePort `30432` / Port `5432` | CSDL Booking (`booking`) & AI (`ai`) |
