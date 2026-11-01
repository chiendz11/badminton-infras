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
| `badminton-infras` (repo này) | Khởi tạo cụm `k3d-badminton-local`, kubeconfig riêng (`local/.local/kubeconfig`), namespaces (`badminton`, `argocd`), Kubernetes Secrets, bootstrap Argo CD, build và import local container images từ app source, thực thi DB migration jobs. |
| `../badminton-gitops` | Khai báo trạng thái mong muốn (Desired State) trong Kubernetes: PostgreSQL datastore (`environments/local/platform`) và các microservices / frontend workloads (`environments/local/apps`). |
| `../badminton-system` | Mã nguồn ứng dụng (Booking Core, AI Service, API Gateway, Web Frontend, Admin Frontend, Prisma migrations, Alembic migrations). |

---

## 2. Chuẩn bị môi trường

Yêu cầu trên máy tính cá nhân:
- **Docker Engine**: `>= 24.0`
- **k3d**: `v5.9.0`
- **kubectl**: Tương thích Kubernetes `1.35` / `1.36`
- **Python**: `>= 3.11`
- **Terraform** (nếu dùng Terraform wrapper): `>= 1.5.0`

---

## 3. Khởi chạy nhanh (Runbook)

### Cách 1: Sử dụng Terraform (1-Click Startup)

```bash
cd terraform/local
terraform init
terraform apply -auto-approve
```

### Cách 2: Sử dụng Makefile / Python CLI

Từ thư mục gốc `badminton-infras`:

```bash
# 1. Khởi tạo môi trường ảo và private settings
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
make local-init

# 2. Khởi tạo cụm k3d badminton-local và secrets
make local-up
make local-secrets

# 3. Build Docker images từ source badminton-system
make local-build

# 4. Import images vào cụm k3d (không cần đẩy lên registry ngoài)
make local-import

# 5. Bootstrap Argo CD và các Applications
make local-bootstrap-argocd

# 6. Chạy Database Migrations và Seed data
make local-migrate

# 7. Kiểm tra trạng thái hệ thống
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

