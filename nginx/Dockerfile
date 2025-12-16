FROM nginx:alpine

# Install curl, consul-template and dos2unix
RUN apk add --no-cache curl bash dos2unix
RUN wget -O /tmp/consul-template.zip https://releases.hashicorp.com/consul-template/0.33.0/consul-template_0.33.0_linux_amd64.zip && \
    unzip /tmp/consul-template.zip -d /usr/local/bin/ && \
    rm /tmp/consul-template.zip

# Create directories
RUN mkdir -p /etc/nginx/templates

# Copy template file
COPY templates/nginx.conf.tmpl /etc/nginx/templates/nginx.conf.tmpl

# Copy entrypoint script and convert line endings
COPY entrypoint.sh /entrypoint.sh
RUN dos2unix /entrypoint.sh && chmod +x /entrypoint.sh

# Expose port
EXPOSE 80

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
