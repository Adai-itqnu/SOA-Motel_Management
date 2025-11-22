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
max_wait=60
wait_count=0
while [ $wait_count -lt $max_wait ]; do
  # Kiểm tra auth-service - kiểm tra response không phải là array rỗng
  auth_response=$(curl -s http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/v1/health/service/auth-service?passing)
  auth_registered=0
  if [ -n "$auth_response" ] && [ "$auth_response" != "[]" ]; then
    # Kiểm tra có ServiceID trong response
    if echo "$auth_response" | grep -q '"ServiceID"'; then
      auth_registered=1
    fi
  fi
  
  # Kiểm tra room-service
  room_response=$(curl -s http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/v1/health/service/room-service?passing)
  room_registered=0
  if [ -n "$room_response" ] && [ "$room_response" != "[]" ]; then
    if echo "$room_response" | grep -q '"ServiceID"'; then
      room_registered=1
    fi
  fi
  
  # Kiểm tra tenant-service
  tenant_response=$(curl -s http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/v1/health/service/tenant-service?passing)
  tenant_registered=0
  if [ -n "$tenant_response" ] && [ "$tenant_response" != "[]" ]; then
    if echo "$tenant_response" | grep -q '"ServiceID"'; then
      tenant_registered=1
    fi
  fi
  
  # Kiểm tra report-service
  report_response=$(curl -s http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/v1/health/service/report-service?passing)
  report_registered=0
  if [ -n "$report_response" ] && [ "$report_response" != "[]" ]; then
    if echo "$report_response" | grep -q '"ServiceID"'; then
      report_registered=1
    fi
  fi
  
  if [ "$auth_registered" -eq 1 ] && [ "$room_registered" -eq 1 ] && [ "$tenant_registered" -eq 1 ] && [ "$report_registered" -eq 1 ]; then
    echo "✓ All services registered with Consul"
    break
  fi
  
  wait_count=$((wait_count + 1))
  if [ $((wait_count % 5)) -eq 0 ]; then
    echo "Waiting for services... (${wait_count}/${max_wait}) - auth: $auth_registered, room: $room_registered, tenant: $tenant_registered, report: $report_registered"
  fi
  sleep 2
done

if [ $wait_count -eq $max_wait ]; then
  echo "WARNING: Services may not be fully registered. Continuing anyway..."
  echo "You can check Consul UI at http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/ui"
fi

# Generate nginx config lần đầu từ template
echo "Generating initial nginx config..."
consul-template \
  -consul-addr=${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500} \
  -template="/etc/nginx/templates/nginx.conf.tmpl:/etc/nginx/nginx.conf" \
  -once \
  -log-level=info

# Kiểm tra config file đã được tạo
if [ ! -f /etc/nginx/nginx.conf ]; then
  echo "ERROR: nginx.conf not generated from Consul Template!"
  echo "Please ensure:"
  echo "  1. Consul is running and accessible"
  echo "  2. Services (auth-service, room-service, tenant-service, report-service) are registered with Consul"
  echo "  3. Check Consul UI at http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/ui"
  exit 1
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

