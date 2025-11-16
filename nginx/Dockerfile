FROM nginx:alpine

# Cài đặt consul-template và netcat
RUN apk add --no-cache curl unzip netcat-openbsd && \
    curl -L https://releases.hashicorp.com/consul-template/0.36.0/consul-template_0.36.0_linux_amd64.zip -o /tmp/consul-template.zip && \
    unzip /tmp/consul-template.zip -d /usr/local/bin && \
    rm /tmp/consul-template.zip && \
    chmod +x /usr/local/bin/consul-template

# Xóa default nginx config để tránh conflict
RUN rm -f /etc/nginx/conf.d/default.conf

# Copy nginx config template
COPY templates/nginx.conf.tmpl /etc/nginx/templates/nginx.conf.tmpl

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose port
EXPOSE 80

# Start consul-template và nginx
ENTRYPOINT ["/entrypoint.sh"]

