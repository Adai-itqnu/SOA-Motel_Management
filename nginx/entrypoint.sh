#!/bin/sh

# Chờ Consul sẵn sàng
echo "Waiting for Consul to be ready..."
until nc -z ${CONSUL_HOST:-consul} ${CONSUL_PORT:-8500}; do
  echo "Consul is unavailable - sleeping"
  sleep 2
done

echo "Consul is ready"

# Chờ services đăng ký với Consul
echo "Waiting for services to register with Consul..."
sleep 5

# Generate nginx config lần đầu từ template
echo "Generating initial nginx config..."
consul-template \
  -consul-addr=${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500} \
  -template="/etc/nginx/templates/nginx.conf.tmpl:/etc/nginx/nginx.conf" \
  -once \
  -log-level=info

# Kiểm tra config file đã được tạo
if [ ! -f /etc/nginx/nginx.conf ]; then
  echo "WARNING: nginx.conf not generated from template! Creating fallback config..."
  # Tạo config fallback đơn giản
  cat > /etc/nginx/nginx.conf <<EOF
events {
    worker_connections 1024;
}

http {
    upstream frontend_service {
        server frontend:5000;
    }

    upstream auth_service {
        server auth-service:5001;
    }

    upstream room_service {
        server room-service:5002;
    }

    server {
        listen 80;
        server_name localhost;

        location / {
            proxy_pass http://frontend_service;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        }

        location /api/auth {
            proxy_pass http://auth_service;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        }

        location /api/rooms {
            proxy_pass http://room_service;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        }

        location /health {
            return 200 "healthy\n";
            add_header Content-Type text/plain;
        }
    }
}
EOF
fi

# Test nginx config
nginx -t

# Chạy consul-template ở background để watch changes
echo "Starting consul-template watcher..."
consul-template \
  -consul-addr=${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500} \
  -template="/etc/nginx/templates/nginx.conf.tmpl:/etc/nginx/nginx.conf:nginx -s reload" \
  -log-level=info &

# Lưu PID của consul-template
CONSUL_TEMPLATE_PID=$!

# Chạy nginx ở foreground
echo "Starting nginx..."
exec nginx -g "daemon off;"

