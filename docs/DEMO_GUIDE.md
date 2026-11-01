# Hướng dẫn Bật Demo Local Hệ thống Badminton Manager V2 (k3d + Argo CD GitOps)

Tài liệu này hướng dẫn chi tiết cách khởi động, kiểm tra và trình diễn (demo) hệ thống **Badminton Manager V2** theo chuẩn kiến trúc 2 repository của MaintAI (`badminton-infras` và `badminton-gitops`), kết hợp với mã nguồn ứng dụng `badminton-system`.

---

## 1. Luồng vận hành Demo Local

```text
[badminton-system (App Repo)]
       │
       ▼ (1. Build local container images)
[Docker Engine trên Laptop]
       │
       ▼ (2. Import trực tiếp vào k3d - Không cần ECR/Docker Hub)
[k3d Cluster: badminton-local]
       │
       ▼ (3. Argo CD đồng bộ Desired State)
[badminton-gitops (GitOps Repo)]
       ├── environments/local/platform -> CSDL PostgreSQL (booking & ai)
       └── environments/local/apps     -> Booking Core, AI Service, API Gateway, Web & Admin UI
```

---

## 2. Các bước triển khai

### Bước 1: Khởi tạo Cụm và Hạ tầng Local

Đứng tại thư mục `badminton-infras`:

```bash
cd /home/chienqt/Dev/newBTL/badminton-infras

# Cài đặt virtual environment và dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Khởi tạo private config và secrets
.venv/bin/python -m localdev init

# Tạo cụm k3d badminton-local và apply secrets
.venv/bin/python -m localdev up
.venv/bin/python -m localdev secrets
```

### Bước 2: Build & Import Application Container Images

```bash
# Build tất cả 5 service đã triển khai (Booking, AI, Gateway, Web, Admin) + Migration tool
.venv/bin/python -m localdev build

# Import các images đã build vào cụm k3d
.venv/bin/python -m localdev import-images
```

### Bước 3: Cài đặt và Kết nối Argo CD GitOps

```bash
# Cài đặt Argo CD và cấu hình 2 Application: badminton-local-platform & badminton-local-apps
.venv/bin/python -m localdev bootstrap-argocd
```

### Bước 4: Chạy Database Migration & Seed Data

```bash
.venv/bin/python -m localdev migrate
```
Lệnh trên sẽ chạy tuần tự:
1. `booking-core`: chạy Prisma migrations và khởi tạo dữ liệu mẫu (sân, giờ đặt, người dùng demo).
2. `ai-service`: chạy Alembic migrations và script khởi tạo `app.migrate`.

### Bước 5: Kiểm tra trạng thái hệ thống

```bash
.venv/bin/python -m localdev status
```

---

## 3. Trải nghiệm Demo trên Trình duyệt

Sau khi hoàn tất, mở trình duyệt và truy cập các đường dẫn sau trên máy:

1. **Giao diện Người dùng đặt sân (Web Frontend)**:
   - URL: [http://127.0.0.1:18082](http://127.0.0.1:18082)
   - Chức năng: Đặt sân cầu lông trực tuyến, xem lịch trống và gợi ý AI.

2. **Giao diện Quản trị viên (Admin Frontend)**:
   - URL: [http://127.0.0.1:18083](http://127.0.0.1:18083)
   - Chức năng: Quản lý sân, giá thuê, slot giờ, xác nhận đơn đặt.

3. **API Gateway Health Check**:
   - URL: `curl http://127.0.0.1:18081/health/ready`
   - Phản hồi: `{"status":"ok"}`

4. **Argo CD UI GitOps**:
   - URL: [https://127.0.0.1:19445](https://127.0.0.1:19445)
   - Quản lý đồng bộ trạng thái tài nguyên Kubernetes theo GitOps.

