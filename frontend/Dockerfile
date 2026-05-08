# Multi-stage Dockerfile for the RepoLens frontend
# Build: docker build -t repolens-ui frontend/
# Run:   docker run -p 80:80 repolens-ui

# Stage 1: Build the Angular app
FROM node:22-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npx ng build --configuration production

# Stage 2: Serve with nginx
FROM nginx:alpine AS runtime

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Custom nginx config for Angular SPA routing
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html

RUN echo 'server { \
    listen 80; \
    server_name _; \
    root /usr/share/nginx/html; \
    index index.html; \
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    location /api/ { \
        proxy_pass http://api:8000/; \
        proxy_http_version 1.1; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_set_header Host $host; \
        proxy_buffering off; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -q --spider http://localhost:80/ || exit 1
