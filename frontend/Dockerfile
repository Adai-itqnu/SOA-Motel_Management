# Use nginx:alpine to serve static files
FROM nginx:alpine

# Copy frontend files
COPY . /usr/share/nginx/html

# Remove Dockerfile and nginx.conf from html folder
RUN rm -f /usr/share/nginx/html/Dockerfile /usr/share/nginx/html/nginx.conf

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 3000
EXPOSE 3000

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
