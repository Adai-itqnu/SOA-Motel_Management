# SOA Motel Management System

Hệ thống quản lý nhà trọ sử dụng kiến trúc SOA (Service-Oriented Architecture) với Consul Service Discovery và Nginx API Gateway.

## Kiến trúc

- **auth-service**: Service xác thực và quản lý người dùng (Port 5001)
- **room-service**: Service quản lý phòng trọ (Port 5002)
- **frontend**: Frontend service (Port 5000)
- **nginx**: API Gateway với Consul Template (Port 80)
- **mongodb**: Database MongoDB (Port 27017)
- **consul**: Service Discovery và Configuration (Port 8500)

## Yêu cầu

- Docker và Docker Compose
- Windows/Linux/Mac

## Cấu trúc thư mục

```
SOA-Motel_Management/
├── docker-compose.yml          # Docker Compose configuration
├── nginx/                      # Nginx với Consul Template
│   ├── Dockerfile
│   ├── entrypoint.sh
│   └── templates/
│       └── nginx.conf.tmpl     # Nginx template với Consul
├── services/
│   ├── auth-service/           # Authentication service
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── model.py
│   │   ├── service_registry.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── room-service/           # Room management service
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── model.py
│   │   ├── service_registry.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── frontend/              # Frontend service
└── README.md
```

## Cách chạy ứng dụng

### 1. Khởi động toàn bộ hệ thống

```bash
# Di chuyển vào thư mục dự án
cd F:\SOA-Motel_Management

# Build và khởi động tất cả services
docker-compose up --build
```

### 2. Chạy ở chế độ background (detached)

```bash
docker-compose up -d --build
```

### 3. Xem logs

```bash
# Xem logs tất cả services
docker-compose logs -f

# Xem logs của một service cụ thể
docker-compose logs -f auth-service
docker-compose logs -f room-service
docker-compose logs -f nginx
docker-compose logs -f consul
```

### 4. Dừng ứng dụng

```bash
# Dừng tất cả services
docker-compose down

# Dừng và xóa volumes (xóa dữ liệu)
docker-compose down -v
```

### 5. Khởi động lại một service cụ thể

```bash
docker-compose restart auth-service
docker-compose restart room-service
docker-compose restart nginx
```

## Truy cập các services

- **Frontend**: http://localhost
- **API Gateway**: http://localhost/api/auth, http://localhost/api/rooms
- **Consul UI**: http://localhost:8500/ui
- **Auth Service trực tiếp**: http://localhost:5001
- **Room Service trực tiếp**: http://localhost:5002

## Kiểm tra Service Discovery

1. Mở Consul UI: http://localhost:8500/ui
2. Vào tab "Services" để xem các services đã đăng ký
3. Kiểm tra health checks của từng service

## API Endpoints

### Auth Service (`/api/auth`)

- `POST /api/auth/register` - Đăng ký tài khoản
- `POST /api/auth/login` - Đăng nhập
- `GET /api/auth/verify` - Verify token (cần Authorization header)
- `GET /api/auth/me` - Lấy thông tin user hiện tại (cần Authorization header)
- `PUT /api/auth/change-password` - Đổi mật khẩu (cần Authorization header)
- `GET /api/auth/users` - Lấy danh sách users (chỉ admin)

### Room Service (`/api/rooms`)

- `GET /api/rooms` - Lấy danh sách phòng (có thể filter theo status, search)
- `GET /api/rooms/<room_id>` - Lấy chi tiết phòng
- `POST /api/rooms` - Tạo phòng mới (chỉ admin, cần Authorization header)
- `PUT /api/rooms/<room_id>` - Cập nhật phòng (chỉ admin, cần Authorization header)
- `DELETE /api/rooms/<room_id>` - Xóa phòng (chỉ admin, cần Authorization header)
- `GET /api/rooms/stats` - Lấy thống kê phòng (cần Authorization header)
- `GET /api/rooms/available` - Lấy danh sách phòng trống

## Cấu hình

### Environment Variables

Các biến môi trường có thể được cấu hình trong `docker-compose.yml`:

- `MONGO_URI`: MongoDB connection string
- `JWT_SECRET`: Secret key cho JWT
- `CONSUL_HOST`: Consul host (mặc định: consul)
- `CONSUL_PORT`: Consul port (mặc định: 8500)
- `SERVICE_PORT`: Port của service

### Consul Template

Nginx sử dụng Consul Template để tự động cập nhật cấu hình khi services thay đổi. Template file: `nginx/templates/nginx.conf.tmpl`

## Troubleshooting

### Service không đăng ký với Consul

1. Kiểm tra Consul đã chạy: `docker-compose logs consul`
2. Kiểm tra service logs: `docker-compose logs auth-service`
3. Kiểm tra network: `docker network inspect soa-motel_management_motel-network`

### Nginx không route được request

1. Kiểm tra Consul có services: http://localhost:8500/ui
2. Kiểm tra nginx logs: `docker-compose logs nginx`
3. Kiểm tra consul-template: `docker exec nginx-gateway ps aux | grep consul-template`

### MongoDB connection error

1. Kiểm tra MongoDB đã chạy: `docker-compose ps mongodb`
2. Kiểm tra MONGO_URI trong docker-compose.yml
3. Kiểm tra network connectivity

## Development

### Thêm service mới

1. Tạo thư mục service mới trong `services/`
2. Tạo các file: `app.py`, `config.py`, `model.py`, `service_registry.py`, `Dockerfile`, `requirements.txt`
3. Thêm service vào `docker-compose.yml`
4. Thêm upstream trong `nginx/templates/nginx.conf.tmpl`

## License

MIT
