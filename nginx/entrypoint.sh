#!/bin/sh

# Wait for Consul to be ready
echo "Waiting for Consul to be ready..."
until wget -q --spider http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/v1/status/leader; do
  echo "Consul is unavailable - sleeping"
  sleep 2
done

echo "Consul is ready"

# Wait for services to register with Consul
echo "Waiting for services to register with Consul..."
max_wait=60
wait_count=0
while [ $wait_count -lt $max_wait ]; do
  # Check auth-service
  auth_response=$(curl -s http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/v1/health/service/auth-service?passing)
  auth_registered=0
  if [ -n "$auth_response" ] && [ "$auth_response" != "[]" ]; then
    if echo "$auth_response" | grep -q '"ServiceID"'; then
      auth_registered=1
    fi
  fi
  
  # Check room-service
  room_response=$(curl -s http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/v1/health/service/room-service?passing)
  room_registered=0
  if [ -n "$room_response" ] && [ "$room_response" != "[]" ]; then
    if echo "$room_response" | grep -q '"ServiceID"'; then
      room_registered=1
    fi
  fi
  
  # Check user-service
  user_response=$(curl -s http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/v1/health/service/user-service?passing)
  user_registered=0
  if [ -n "$user_response" ] && [ "$user_response" != "[]" ]; then
    if echo "$user_response" | grep -q '"ServiceID"'; then
      user_registered=1
    fi
  fi
  
  if [ "$auth_registered" -eq 1 ] && [ "$room_registered" -eq 1 ] && [ "$user_registered" -eq 1 ]; then
    echo "All required services registered with Consul (auth, room, user)"
    break
  fi
  
  wait_count=$((wait_count + 1))
  if [ $((wait_count % 5)) -eq 0 ]; then
    echo "Waiting for services... (${wait_count}/${max_wait}) - auth: $auth_registered, room: $room_registered, user: $user_registered"
  fi
  sleep 2
done

if [ $wait_count -eq $max_wait ]; then
  echo "WARNING: Some services may not be registered. Continuing anyway..."
  echo "Check Consul UI at http://${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500}/ui"
fi

# Generate nginx config from template
echo "Generating nginx config from Consul Template..."
consul-template \
  -consul-addr=${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500} \
  -template="/etc/nginx/templates/nginx.conf.tmpl:/etc/nginx/nginx.conf" \
  -once \
  -log-level=info

# Check config file was generated
if [ ! -f /etc/nginx/nginx.conf ]; then
  echo "ERROR: nginx.conf not generated!"
  exit 1
fi

echo "Generated nginx.conf:"
cat /etc/nginx/nginx.conf

# Test nginx config
nginx -t

# Run consul-template in background to watch changes
echo "Starting consul-template watcher for dynamic updates..."
consul-template \
  -consul-addr=${CONSUL_HOST:-consul}:${CONSUL_PORT:-8500} \
  -template="/etc/nginx/templates/nginx.conf.tmpl:/etc/nginx/nginx.conf:nginx -s reload" \
  -log-level=warn &

# Run nginx in foreground
echo "Starting nginx..."
exec nginx -g "daemon off;"
