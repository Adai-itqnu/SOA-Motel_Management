# SOA Motel Management System

Hệ thống quản lý nhà trọ theo kiến trúc Microservices (SOA).

## 🚀 Chạy nhanh

### Yêu cầu
- Docker Desktop
- Docker Compose

### Khởi động

```bash
# Clone project
git clone <repository-url>
cd SOA-Motel_Management

# Copy file cấu hình
cp .env.example .env

# Khởi động tất cả services
docker-compose up -d

# Xem logs
docker-compose logs -f
```

### Truy cập
- **Frontend**: http://localhost
- **Consul UI**: http://localhost:8500
- **API Gateway**: http://localhost/api

## 📁 Cấu trúc dự án

```
SOA-Motel_Management/
├── frontend/               # Static frontend (HTML, CSS, JS)
│   ├── auth/              # Đăng nhập, đăng ký
│   ├── admin/             # Giao diện admin
│   ├── tenant/            # Giao diện người thuê
│   └── assets/            # CSS, JS, Images
│
├── services/              # Backend Microservices
│   ├── auth-service/      # Xác thực (Port 5001)
│   ├── room-service/      # Quản lý phòng (Port 5002)
│   ├── tenant-service/    # Quản lý người thuê (Port 5003)
│   ├── report-service/    # Báo cáo (Port 5004)
│   ├── booking-service/   # Đặt phòng (Port 5005)
│   ├── contract-service/  # Hợp đồng (Port 5006)
│   ├── bill-service/      # Hóa đơn (Port 5007)
│   ├── payment-service/   # Thanh toán VNPay (Port 5008)
│   └── notification-service/ # Thông báo (Port 5010)
│
├── nginx/                 # API Gateway + Load Balancer
├── docs/                  # Documentation
├── docker-compose.yml     # Docker Compose config
└── .env.example           # Environment variables template
```

## 🛠 Services

| Service | Port | Mô tả |
|---------|------|-------|
| MongoDB | 27017 | Database |
| Consul | 8500 | Service Discovery |
| Nginx | 80 | API Gateway + Frontend |
| auth-service | 5001 | Authentication/Authorization |
| room-service | 5002 | Room Management |
| tenant-service | 5003 | Tenant Management |
| report-service | 5004 | Reports/Statistics |
| booking-service | 5005 | Booking Management |
| contract-service | 5006 | Contract Management |
| bill-service | 5007 | Bill Management |
| payment-service | 5008 | VNPay Payment |
| notification-service | 5010 | Notifications |

## 📝 Tài khoản test

Sau khi khởi động, đăng ký tài khoản mới hoặc sử dụng API để tạo admin:

```bash
# Đăng ký user mới qua API
curl -X POST http://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456","name":"Admin","email":"admin@test.com","phone":"0901234567"}'
```

## 🔧 Commands hữu ích

```bash
# Xem status
docker-compose ps

# Restart một service
docker-compose restart auth-service

# Rebuild và restart
docker-compose up -d --build

# Dừng tất cả
docker-compose down

# Xóa volumes (⚠️ Xóa dữ liệu)
docker-compose down -v
```

## 📚 Documentation

Xem thêm tài liệu trong thư mục `docs/`:
- [API Documentation](docs/API_DOCUMENTATION.md)
- [Database Schema](docs/DATABASE_SCHEMA.md)
- [SOA Compliance](docs/SOA_COMPLIANCE.md)
