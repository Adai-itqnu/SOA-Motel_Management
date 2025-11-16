# Hướng dẫn chạy nhanh

## Bước 1: Mở terminal và di chuyển vào thư mục dự án

```bash
cd F:\SOA-Motel_Management
```

## Bước 2: Build và khởi động tất cả services

```bash
docker-compose up --build
```

Lần đầu tiên sẽ mất vài phút để download images và build containers.

## Bước 3: Kiểm tra services đã chạy

Mở trình duyệt và truy cập:

- **Frontend**: http://localhost
- **Consul UI** (để xem services): http://localhost:8500/ui
- **API Auth**: http://localhost/api/auth/register
- **API Rooms**: http://localhost/api/rooms

## Bước 4: Kiểm tra logs (nếu cần)

Mở terminal mới và chạy:

```bash
# Xem logs tất cả
docker-compose logs -f

# Hoặc xem logs của service cụ thể
docker-compose logs -f auth-service
docker-compose logs -f room-service
docker-compose logs -f nginx
```

## Bước 5: Dừng ứng dụng (khi cần)

Nhấn `Ctrl+C` trong terminal đang chạy docker-compose, hoặc:

```bash
docker-compose down
```

## Lưu ý

- Đảm bảo port 80, 5000, 5001, 5002, 27017, 8500 không bị sử dụng bởi ứng dụng khác
- Nếu có lỗi, kiểm tra logs để xem chi tiết
- Consul UI giúp bạn xem các services đã đăng ký và health status

## Test API

### Đăng ký user đầu tiên (sẽ là admin)

```bash
curl -X POST http://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123",
    "email": "admin@example.com",
    "name": "Admin User",
    "phone": "0123456789"
  }'
```

### Đăng nhập

```bash
curl -X POST http://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "admin123"
  }'
```

Lưu token từ response để dùng cho các API cần authentication.

### Lấy danh sách phòng

```bash
curl http://localhost/api/rooms
```
