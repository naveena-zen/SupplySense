# ── BUILD STAGE ──
FROM node:20-slim AS builder
WORKDIR /app

# Copy package descriptors and install packages
COPY package*.json ./
RUN npm install

# Copy source code and build production assets
COPY . .
RUN npm run build

# ── SERVE STAGE ──
FROM nginx:alpine

# Copy built HTML/CSS/JS assets to Nginx default serving root
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
